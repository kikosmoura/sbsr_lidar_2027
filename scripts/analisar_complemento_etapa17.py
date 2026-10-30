"""Executar somente tabelas complementares sobre fontes imutáveis da etapa12."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from sbsr_lidar.config import load_config
from sbsr_lidar.crown_plan import crown_scenarios
from sbsr_lidar.complementary_analysis import matching_analysis, stability_analysis
from sbsr_lidar.storage import fingerprint, read_json, atomic_write_json


def native(x):
    if isinstance(x, dict): return {str(k): native(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [native(v) for v in x]
    if isinstance(x, np.generic): return native(x.item())
    if isinstance(x, float) and not np.isfinite(x): return None
    return x


class Sources:
    def __init__(self, manifest):
        self.inventory = {x['path']: x for x in manifest['artifacts']}
        self.used = {}

    def check(self, path, inventory=None):
        path = Path(path); expected = (inventory if inventory is not None else self.inventory).get(str(path))
        actual = fingerprint(path)
        if expected is None or actual != expected: raise ValueError(f'Fonte alterada ou não autenticada: {path}')
        self.used[str(path)] = actual
        return path


def describe_loss(eligibility):
    rows = []
    for scenario, frame in eligibility.groupby('scenario_id', sort=False):
        excluded = ~frame.paired_eligible
        obs = (frame.primary_on_pair_support__observation_below_minimum | frame.scenario_on_pair_support__observation_below_minimum)
        rows.append({'scenario_id': scenario, 'primary_units': len(frame), 'paired_eligible_units': int(frame.paired_eligible.sum()),
            'excluded_units': int(excluded.sum()), 'excluded_with_insufficient_observed_fraction': int((excluded & obs).sum()),
            'excluded_other_eligibility_only': int((excluded & ~obs).sum()),
            'fixed_cohort_units': int(frame.in_fixed_cohort.sum())})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/complemento_analitico_etapa17.yaml'))
    args = parser.parse_args(); project = Path(__file__).resolve().parents[1]
    spec = yaml.safe_load(args.config.read_text()); config = load_config(project/spec['scientific_config'])
    now = datetime.now(timezone.utc); run_id = now.strftime('%Y%m%dT%H%M%SZ')+'_'+hashlib.sha256(args.config.read_bytes()).hexdigest()[:10]
    out = project/spec['output_parent']/run_id; out.mkdir(parents=True, exist_ok=False)
    # Congelamento anterior aos novos cálculos, sem alegar pré-registro.
    shutil.copyfile(args.config, out/'regras_antes_calculo.yaml')
    shutil.copyfile(project/'docs/protocolo_complemento_etapa17.md', out/'protocolo_antes_calculo.md')
    atomic_write_json(out/'inicio.json', {'run_id': run_id, 'started_at': now.isoformat(), 'post_result_exploratory': True,
        'config': fingerprint(out/'regras_antes_calculo.yaml'), 'protocol': fingerprint(out/'protocolo_antes_calculo.md')})
    sources = Sources(read_json(project/spec['source_manifest']))
    source_report = project/spec['execution_report']; run = read_json(source_report)
    if run['run_id'] != spec['source_run_id']: raise ValueError('Execução fonte divergente')
    root = Path(run['products_root'])
    primary = gpd.read_parquet(sources.check(root/'coorte_selecionada.parquet'))
    primary = primary.loc[primary.role.eq(spec['role'])].sort_values('unit_id').reset_index(drop=True)
    if len(primary) != spec['expected_primary_units']: raise ValueError('Universo primário mudou')
    matching = matching_analysis(primary, spec['horizontal_matching'])
    old = pd.read_parquet(sources.check(root/'pares_cobertura_semelhante.parquet'))
    old = old.loc[old.case.eq('sample_'+spec['role']) & old.family.eq('grid') & old.scale_m.eq(50)]
    new = matching['old_pairs']
    if set(zip(new.unit_i, new.unit_j)) != set(zip(old.unit_i, old.unit_j)): raise ValueError('Pares antigos não reproduzidos')
    merged = new[['unit_i', 'unit_j', 'absolute_P95_difference_m', 'absolute_IQR_difference_m']].merge(old, on=['unit_i', 'unit_j'], suffixes=('_new', '_old'), validate='one_to_one')
    for col in ['absolute_P95_difference_m', 'absolute_IQR_difference_m']:
        if not np.allclose(merged[col+'_new'], merged[col+'_old'], rtol=0, atol=1e-12): raise ValueError('Diferenças antigas não reproduzidas')
    pairs = {}
    for scenario in [x.scenario_id for x in crown_scenarios()[1:]]:
        sides = [[], []]
        for cid, case in sorted(run['case_results'].items()):
            if case['role'] != spec['role']: continue
            base = Path(case['root']); seal = read_json(sources.check(base/'complete.json'))
            inventory = {x['path']: x for x in seal['outputs']}
            for i, name in enumerate(['principal_suporte_comum', 'cenario_suporte_comum']):
                path = sources.check(base/scenario/f'{name}.parquet', inventory)
                sides[i].append(gpd.read_parquet(path))
        pairs[scenario] = tuple(gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry='geometry', crs=primary.crs) for frames in sides)
    stability = stability_analysis(primary, pairs, config)
    existing = pd.read_parquet(sources.check(root/'sensibilidade_rankings_agrupada.parquet'))
    existing = existing.loc[existing.role.eq(spec['role'])].set_index('scenario_id')
    replay = stability['comparisons'].query("cohort == 'variable_pairwise'").set_index('scenario_id')
    for col in ['n', 'k', 'spearman_rho', 'jaccard_exact', 'jaccard_including_cut_ties', 'mean_absolute_rank_shift']:
        if not np.allclose(replay.loc[existing.index, col], existing[col], rtol=0, atol=1e-12, equal_nan=True): raise ValueError(f'Sensibilidade antiga divergente: {col}')
    for key in ['candidates', 'primary', 'disjoint', 'sensitivity', 'per_corridor']:
        matching[key].to_csv(out/f'complementaridade_{key}.csv', index=False)
    for key in ['comparisons', 'rankings', 'eligibility', 'fixed_membership', 'area']:
        stability[key].to_csv(out/f'estabilidade_{key}.csv', index=False)
    loss = describe_loss(stability['eligibility']); loss.to_csv(out/'perdas_elegibilidade.csv', index=False)
    fixed = stability['fixed_membership']; contribution = fixed.groupby('corridor_id').in_fixed_cohort.agg(['size', 'sum']).reset_index()
    contribution.columns = ['corridor_id', 'primary_units', 'fixed_units']; contribution['excluded_units'] = contribution.primary_units-contribution.fixed_units
    contribution.to_csv(out/'coorte_por_corredor.csv', index=False)
    fixed_results = stability['comparisons'].query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'method_on_pair_support'")
    intervals = {col: {'min': native(fixed_results[col].min()), 'max': native(fixed_results[col].max())} for col in ['spearman_rho', 'jaccard_exact', 'jaccard_including_cut_ties', 'mean_absolute_rank_shift']}
    support_results = stability['comparisons'].query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'support_only'")
    support_ranges = {col: {'min': native(support_results[col].min()), 'max': native(support_results[col].max())} for col in ['spearman_rho', 'jaccard_exact', 'mean_absolute_rank_shift']}
    lowest_retention = loss.sort_values(['paired_eligible_units', 'scenario_id']).iloc[0].to_dict()
    summary = {'analysis_version': spec['analysis_version'], 'run_id': run_id, 'source_run_id': run['run_id'],
        'post_result_exploratory': True, 'role': spec['role'], 'primary_units': len(primary),
        'old_538_pairs_reproduced': len(old) == 538, 'old_11_sensitivities_reproduced': len(replay) == 11,
        'matching': matching['summary'], 'strict_fixed_units': len(stability['fixed_ids']), 'strict_fixed_ids': stability['fixed_ids'],
        'strict_fixed_corridors': int((contribution.fixed_units > 0).sum()), 'fixed_A_plus_3D_method_ranges': intervals,
        'fixed_A_plus_3D_support_ranges': support_ranges, 'lowest_retention': lowest_retention,
        'fixed_primary_A_vs_A_plus_3D': stability['fixed_primary_ablation'],
        'fixed_cohort_missing_reason': stability['fixed_cohort_missing_reason'],
        'global_fixed_observation_geometry_measured': False, 'pairwise_equal_observation_support_inherited_from_authenticated_sources': True,
        'no_new_LAZ_processing': True, 'no_external_validation': True, 'p_values_computed': False, 'confidence_intervals_computed': False,
        'finished_at': datetime.now(timezone.utc).isoformat()}
    atomic_write_json(out/'resultados.json', native(summary))
    atomic_write_json(out/'proveniencia.json', {'source_manifest': fingerprint(project/spec['source_manifest']),
        'execution_report': fingerprint(source_report), 'authenticated_inputs': list(sources.used.values()),
        'code': [fingerprint(project/p) for p in ['src/sbsr_lidar/complementary_analysis.py', 'scripts/analisar_complemento_etapa17.py']],
        'python': sys.version, 'platform': platform.platform(), 'packages': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scipy', 'geopandas', 'shapely']}})
    atomic_write_json(project/'relatorios/etapa17/ultima_analise.json', {'run_id': run_id, 'output_root': str(out), 'results': fingerprint(out/'resultados.json')})
    print(json.dumps(native({'output': str(out), **summary}), ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
