"""Auditar universos, fórmulas, listas/empates, pareamentos e ausência de inferência circular."""
import argparse
import itertools
import math
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from sbsr_lidar.config import load_config
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json


def manual_top(frame, fraction):
    ordered = frame.sort_values('rank_ordinal')
    k = math.ceil(len(ordered)*fraction)
    cutoff = ordered.iloc[k-1]
    tie = ordered.stratum.eq(cutoff.stratum)
    if cutoff.stratum_order == 1:
        tie &= ordered.score_for_ranking.eq(cutoff.score_for_ranking)
    exact = set(ordered.iloc[:k].unit_id)
    inclusive = exact | set(ordered.loc[tie].unit_id)
    return k, exact, inclusive, int(tie.sum())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/terreno_congelado_etapa04.yaml'))
    parser.add_argument('--reports', type=Path, default=Path('relatorios/etapa09'))
    args = parser.parse_args(); config = load_config(args.config)
    checks, summary = {}, {}
    for case in ['main', 'adversarial']:
        e = read_json(args.reports/f'execucao_{case}.json'); r = read_json(Path(e['report']))
        manifest = RunManifest.model_validate(read_json(Path(e['manifest'])))
        directory = Path(e['products_root'])
        tables = {p.stem: (gpd.read_parquet(p) if p.stem in ['universo_unidades', 'desacordos_espaciais'] else pd.read_parquet(p))
                  for p in directory.glob('*.parquet')}
        source = gpd.read_parquet(r['source_indicators']['parquet'])
        membership = tables['universo_unidades'].set_index('unit_id')
        ranks, agreement = tables['escores_rankings'], tables['concordancia_ablacao']
        checks[f'{case}:manifest_code_and_frozen_inputs'] = manifest.stage == '09' and manifest.status == 'completed' and manifest.code_sha256 == source_digest() and all(fingerprint(Path(p.path)) == p.model_dump() for p in manifest.inputs)
        checks[f'{case}:physical_indicators_geometry_preserved'] = (set(source.unit_id) == set(membership.index)
            and all(g.equals(membership.loc[u].geometry) for u, g in zip(source.unit_id, source.geometry))
            and all(np.allclose(pd.to_numeric(source[k]), pd.to_numeric(membership.loc[source.unit_id, k]), equal_nan=True) for k in ['I1', 'I4', 'I5', 'I6', 'I7', 'area_observed_m2']))
        csv = pd.read_csv(directory/'escores_rankings.csv')
        checks[f'{case}:CSV_Parquet_equivalence'] = csv.unit_id.tolist() == ranks.unit_id.tolist() and np.allclose(csv.score.to_numpy(dtype=float), ranks.score.to_numpy(dtype=float), equal_nan=True, rtol=0, atol=1e-12)
        formulas = same_universe = normalizers = rank_rules = no_height_imputation = zero_weight = duplicate = True
        for (family, scale), original in source.groupby(['family', 'nominal_size_m']):
            longitudinal = family == 'longitudinal'
            valid = original.eligible_B_plus_3D if longitudinal else original.eligible_A_plus_3D
            paired = original.loc[valid].sort_values('unit_id').set_index('unit_id')
            base_ok = original.eligible_B if longitudinal else original.eligible_A
            absence = set(original.loc[base_ok & original.area_canopy_m2.eq(0)].unit_id)
            if not len(paired): continue
            required = ['I1', 'I4', 'I6', 'I7']+(['I2', 'I3_local_over_observable_length'] if longitudinal else [])
            physical_ranks = {k: (paired[k].rank(method='average')-.5)/len(paired) for k in required}
            score_A = (1-physical_ranks['I1']+physical_ranks['I4'])/2
            subset = ranks.loc[(ranks.family == family) & (ranks.scale_m == scale)]
            for (scope, variant), g in subset.groupby(['scope', 'variant_id']):
                expected_ids = set(paired.index) | (absence if scope == 'joint_strata' else set())
                same_universe &= set(g.unit_id) == expected_ids and g.unit_id.is_unique
                canopy = g.loc[g.stratum == 'with_candidate_canopy'].set_index('unit_id').loc[paired.index]
                row = canopy.iloc[0]
                for variable in required:
                    normalizers &= np.allclose(canopy[f'R_{variable}'], physical_ranks[variable], atol=1e-12, rtol=0)
                normalizers &= canopy.normalizer_n.eq(len(paired)).all()
                if row.method == 'A': expected = score_A
                else:
                    height = 1-physical_ranks['I6']
                    if row.features == 'I6_I7':
                        dispersion = 1-physical_ranks['I7'] if row.orientation == 'Vplus' else physical_ranks['I7']
                        vertical = (height+dispersion)/2
                    else: vertical = height
                    expected = (1-row.vertical_weight)*score_A+row.vertical_weight*vertical
                formulas &= np.allclose(canopy.score, expected, atol=1e-12, rtol=0)
                rounded = pd.Series(np.round(expected, config.comparison.score_tie_decimals), index=paired.index)
                m = len(absence) if scope == 'joint_strata' else 0
                rank_rules &= np.allclose(canopy.rank_mean, rounded.rank(ascending=False, method='average')+m)
                ordered = pd.DataFrame({'unit_id': paired.index, 'value': rounded.to_numpy()}).sort_values(['value', 'unit_id'], ascending=[False, True])
                expected_order = dict(zip(ordered.unit_id, np.arange(1, len(ordered)+1)+m))
                rank_rules &= all(row.rank_ordinal == expected_order[row.Index] for row in canopy.itertuples())
                absent = g.loc[g.stratum == 'no_detected_canopy']
                no_height_imputation &= absent[['I6', 'I7', 'score', 'score_for_ranking']].isna().all().all()
                if len(absent):
                    no_height_imputation &= absent.rank_mean.eq((m+1)/2).all() and absent.rank_ordinal.max() <= m
                if row.method != 'A' and row.vertical_weight == 0:
                    zero_weight &= np.allclose(canopy.score, score_A)
            for (scope, weight), g in subset.loc[subset.features.isin(['I6_only', 'I6_duplicate'])].groupby(['scope', 'vertical_weight']):
                x = g.loc[g.features == 'I6_only'].set_index('unit_id').sort_index()
                y = g.loc[g.features == 'I6_duplicate'].set_index('unit_id').sort_index()
                duplicate &= x.index.equals(y.index) and np.allclose(x.score.to_numpy(dtype=float), y.score.to_numpy(dtype=float), equal_nan=True, atol=1e-12, rtol=0)
        checks[f'{case}:fixed_universe_for_every_method'] = bool(same_universe)
        checks[f'{case}:independent_score_formula_recalculation'] = bool(formulas)
        checks[f'{case}:fixed_rank_normalizers'] = bool(normalizers)
        checks[f'{case}:mean_ranks_and_operational_ID_ties'] = bool(rank_rules)
        checks[f'{case}:absence_stratum_has_no_fake_height_or_score'] = bool(no_height_imputation)
        checks[f'{case}:zero_weight_is_exact_A_control'] = bool(zero_weight)
        checks[f'{case}:duplicate_height_adds_no_artificial_information'] = bool(duplicate)
        top_ok = tie_ok = rho_ok = shift_ok = small_ok = top_members_ok = True
        for row in agreement.itertuples():
            common = (ranks.family == row.family) & (ranks.scale_m == row.scale_m) & (ranks.scope == row.scope)
            a = ranks.loc[common & ranks.variant_id.eq(row.baseline_id)]
            b = ranks.loc[common & ranks.variant_id.eq(row.variant_id)]
            k, x, xi, ta = manual_top(a, row.top_fraction)
            _, y, yi, tb = manual_top(b, row.top_fraction)
            members = tables['membros_top'].loc[lambda t: (t.family == row.family) & (t.scale_m == row.scale_m)
                & (t.scope == row.scope) & (t.variant_id == row.variant_id) & (t.top_fraction == row.top_fraction)]
            top_members_ok &= len(members) == row.n and members.unit_id.is_unique
            top_members_ok &= set(members.loc[members.top_baseline_exact].unit_id) == x
            top_members_ok &= set(members.loc[members.top_variant_exact].unit_id) == y
            top_members_ok &= set(members.loc[members.top_baseline_including_ties].unit_id) == xi
            top_members_ok &= set(members.loc[members.top_variant_including_ties].unit_id) == yi
            top_ok &= k == row.k and len(x) == len(y) == k and len(x & y) == row.top_intersection_n
            tie_ok &= ta == row.base_tie_at_cut_n and tb == row.variant_tie_at_cut_n and len(xi) == row.base_inclusive_n and len(yi) == row.variant_inclusive_n
            if k < config.comparison.minimum_top_k_for_jaccard:
                small_ok &= pd.isna(row.jaccard_exact) and pd.isna(row.jaccard_including_cut_ties)
            else:
                top_ok &= math.isclose(row.jaccard_exact, len(x & y)/len(x | y), abs_tol=1e-12)
                tie_ok &= math.isclose(row.jaccard_including_cut_ties, len(xi & yi)/len(xi | yi), abs_tol=1e-12)
            left = a.set_index('unit_id').sort_index().rank_mean
            right = b.set_index('unit_id').sort_index().rank_mean
            if len(left) < config.comparison.minimum_spearman_units or left.nunique() == 1 or right.nunique() == 1:
                rho_ok &= pd.isna(row.spearman_rho)
            else: rho_ok &= math.isclose(row.spearman_rho, left.corr(right), abs_tol=1e-12)
            shift_ok &= math.isclose(row.mean_absolute_rank_shift, (right-left).abs().mean(), abs_tol=1e-12)
        checks[f'{case}:exact_top_cardinality_and_Jaccard'] = bool(top_ok)
        checks[f'{case}:cutoff_ties_inclusive_sensitivity'] = bool(tie_ok)
        checks[f'{case}:small_lists_not_substantive_Jaccard'] = bool(small_ok)
        checks[f'{case}:Spearman_without_p_values'] = bool(rho_ok)
        checks[f'{case}:physical_rank_displacements'] = bool(shift_ok)
        checks[f'{case}:per_unit_top_membership_and_cut_ties'] = bool(top_members_ok)
        corr_ok = distribution_ok = True
        for row in tables['correlacoes_indicadores'].itertuples():
            g = source.loc[(source.family == row.family) & (source.nominal_size_m == row.scale_m)]
            g = g.loc[g.eligible_B_plus_3D if row.family == 'longitudinal' else g.eligible_A_plus_3D]
            x, y = pd.to_numeric(g[row.variable_x]), pd.to_numeric(g[row.variable_y])
            finite = x.notna() & y.notna(); x, y = x[finite], y[finite]
            corr_ok &= len(x) == row.n_pairs
            if len(x) < config.comparison.minimum_spearman_units or x.nunique() == 1 or y.nunique() == 1:
                corr_ok &= pd.isna(row.spearman_rho)
            else: corr_ok &= math.isclose(row.spearman_rho, x.rank().corr(y.rank()), abs_tol=1e-12)
        for row in tables['estatisticas_indicadores'].itertuples():
            g = source.loc[(source.family == row.family) & (source.nominal_size_m == row.scale_m)]
            use = g.eligible_A if row.scope == 'eligible_A_descriptors' else g.eligible_B_plus_3D if row.family == 'longitudinal' else g.eligible_A_plus_3D
            values = pd.to_numeric(g.loc[use, row.variable]).dropna()
            distribution_ok &= len(values) == row.n_finite and int(use.sum()) == row.n_universe
            if len(values): distribution_ok &= math.isclose(row.median, values.median(), abs_tol=1e-12)
        checks[f'{case}:physical_Spearman_correlations_from_source'] = bool(corr_ok)
        checks[f'{case}:separate_indicator_distributions'] = bool(distribution_ok)
        pairs = tables['pares_cobertura_semelhante']
        pair_ok = True
        for (family, scale), g in source.groupby(['family', 'nominal_size_m']):
            paired = g.loc[g.eligible_B_plus_3D if family == 'longitudinal' else g.eligible_A_plus_3D]
            expected = set()
            for a, b in itertools.combinations(paired.sort_values('unit_id').itertuples(), 2):
                delta = abs(a.I1-b.I1)
                ratio = max(a.area_observed_m2, b.area_observed_m2)/min(a.area_observed_m2, b.area_observed_m2)
                if delta <= config.comparison.similar_cover_tolerance+config.comparison.pair_boundary_epsilon and ratio <= config.comparison.maximum_observed_area_ratio+config.comparison.pair_boundary_epsilon:
                    expected.add((a.unit_id, b.unit_id))
            subset = pairs.loc[(pairs.family == family) & (pairs.scale_m == scale)]
            pair_ok &= set(zip(subset.unit_i, subset.unit_j)) == expected
            for pair in subset.itertuples():
                original = source.set_index('unit_id')
                pair_ok &= math.isclose(pair.absolute_P95_difference_m, abs(original.loc[pair.unit_i].I6-original.loc[pair.unit_j].I6), abs_tol=1e-12)
        checks[f'{case}:H1_all_eligible_pairs_and_source_heights'] = bool(pair_ok)
        controls = tables['controles']
        checks[f'{case}:no_fake_exchangeable_blocks_or_predictive_accuracy'] = not controls.surrogate_permutations_performed.any() and not controls.p_values_computed.any() and not r['predictive_models_trained'] and not r['accuracy_gain_claimed'] and r['reference_assessment']['independent_priority_references'] == 0
        checks[f'{case}:B_C_not_fabricated'] = not ranks.method.isin(['B', 'C']).any() and not tables['disponibilidade_metodos'].loc[lambda t: t.method.isin(['B', 'C'])].available.any()
        spatial = tables['desacordos_espaciais']
        originals = source.set_index('unit_id')
        checks[f'{case}:spatial_disagreements_use_original_geometry'] = all(row.geometry.equals(originals.loc[row.unit_id].geometry) for row in spatial.itertuples()) and spatial.crs.to_epsg() == config.grid.epsg
        cache = read_json(args.reports/f'cache_{case}.json')
        checks[f'{case}:cache_same_products'] = cache['cache_hit'] and cache['report'] == e['report']
        checks[f'{case}:no_optimization_or_mask_validation_claim'] = not r['mask_validated'] and r['score_protocol']['no_weight_optimization'] and r['score_protocol']['no_superiority_assumption']
        summary[case] = {'run_id': r['run_id'], 'cohorts': r['cohorts'], 'primary': r['primary_A_vs_A_plus_3D'],
            'H1': r['H1_matched_pairs'], 'rows': r['table_rows'], 'elapsed_seconds': r['elapsed_seconds'], 'peak_process_rss_mib': r['peak_process_rss_mib']}
    logs = [(args.reports/p).read_text() for p in ['testes_cientificos.log', 'downloader_regressao.log']]
    checks['test_logs_success'] = all(re.search(r'\d+ passed', log) and not re.search(r'\b\d+ (?:failed|errors?)\b', log) for log in logs)
    tests = {'scientific_passed': int(re.search(r'(\d+) passed', logs[0]).group(1)), 'downloader_passed': int(re.search(r'(\d+) passed', logs[1]).group(1))}
    result = {'ok': all(checks.values()), 'checks': {k: bool(v) for k, v in checks.items()}, 'summary': summary, 'tests': tests}
    atomic_write_json(args.reports/'verificacoes.json', result)
    print(f'{sum(checks.values())}/{len(checks)} verificações dos produtos reais passaram.')
    if not result['ok']:
        print([k for k, v in checks.items() if not v]); raise SystemExit(1)


if __name__ == '__main__': main()
