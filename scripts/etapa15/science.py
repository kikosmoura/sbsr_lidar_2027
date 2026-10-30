"""Conferência independente de escores, seleção e suportes dos dados preservados."""
from pathlib import Path
import hashlib
import math
import itertools

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import yaml

from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json
from etapa13.evidence import evaluate_recipe
from etapa13.verification import arithmetic
from etapa14.audit import verify_registry


def authenticate(project):
    """Documentos evoluem; resultados antigos são comparados às cópias autenticadas."""
    counts = {}; aliases = []
    for stage, previous in [('12', '13'), ('13', '14'), ('14', '15')]:
        manifest = read_json(project/f'docs/manifesto_etapa{stage}.json')
        for record in manifest['artifacts']:
            original = Path(record['path']); actual = original
            if original in [project/'docs/estado_projeto.json', project/'docs/decisoes_metodologicas.md']:
                actual = project/f'relatorios/etapa{previous}/entradas_etapa{stage}'/original.name
            if stage == '12' and original == project/'src/sbsr_lidar/crown_data.py':
                actual = project/'relatorios/etapa15/entradas_etapa12/crown_data.py'
            found = fingerprint(actual)
            if (found['bytes'], found['sha256']) != (record['bytes'], record['sha256']):
                raise ValueError(f'Histórico alterado: etapa{stage}: {original}')
            if actual != original: aliases.append({'stage': stage, 'original': record, 'snapshot': found})
        counts[stage] = len(manifest['artifacts'])
    return {'authenticated_by_stage': counts, 'historical_aliases': aliases}


def ranked(ids, values, decimals=12):
    ids = np.asarray(ids, dtype=str); values = np.asarray(values, dtype=float)
    if len(np.unique(ids)) != len(ids) or not np.isfinite(values).all(): raise ValueError('Universo inválido')
    rounded = np.round(values, decimals)
    order = np.lexsort((ids, -rounded)); positions = np.empty(len(ids), int); positions[order] = np.arange(1, len(ids)+1)
    return pd.DataFrame({'unit_id': ids, 'score': values, 'score_for_ranking': rounded,
        'rank_mean': pd.Series(-rounded).rank(method='average').to_numpy(), 'rank_ordinal': positions}).set_index('unit_id').sort_index()


def compare(a, b, fraction=.2):
    if not a.index.equals(b.index): raise ValueError('IDs de comparação diferentes')
    k = math.ceil(fraction*len(a)); x = a.rank_mean.to_numpy(); y = b.rank_mean.to_numpy()
    at = set(a.sort_values('rank_ordinal').head(k).index); bt = set(b.sort_values('rank_ordinal').head(k).index)
    return {'n': len(a), 'k': k, 'spearman_rho': float(np.corrcoef(x, y)[0, 1]),
        'jaccard_exact': len(at & bt)/len(at | bt), 'top_intersection_n': len(at & bt), 'top_union_n': len(at | bt),
        'mean_absolute_rank_shift': float(np.abs(x-y).mean()), 'maximum_absolute_rank_shift': float(np.abs(x-y).max())}


def recipes(frame):
    r = frame[['I1', 'I4', 'I6', 'I7']].rank(method='average').sub(.5).div(len(frame))
    a = (1-r.I1+r.I4)/2; h = 1-r.I6
    return a, {'Vplus': (h+1-r.I7)/2, 'Vminus': (h+r.I7)/2, 'height_only': h, 'duplicate_control': (h+h)/2}


def assert_number(actual, expected, label, tol=1e-12):
    if actual is None or expected is None or not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tol):
        raise ValueError(f'Divergência {label}: reproduzido={actual}, preservado={expected}')


def audit_science(project, out):
    history = authenticate(project)
    evidence = read_json(project/'artigo/dados/resultados_publicaveis.json')
    frames = {}
    for key, fp in evidence['sources'].items():
        path = Path(fp['path'])
        if fingerprint(path) != fp: raise ValueError(f'Fonte experimental alterada: {path}')
        frames[key] = pd.read_csv(path) if path.suffix == '.csv' else pd.read_parquet(path)
    reproduced = {}
    for key, record in evidence['metrics'].items():
        if 'recipe' in record:
            value = evaluate_recipe(frames[record['recipe']['source']], record['recipe'])
        elif 'json_pointer' in record:
            value = read_json(Path(record['source_fingerprint']['path']))
            for field in record['json_pointer'].strip('/').split('/'): value = value[field]
        else: continue
        assert_number(value, record['value'], key, 1e-8)
        reproduced[key] = value
    for key, record in evidence['metrics'].items():
        if key not in reproduced:
            value = arithmetic(record['expression'], reproduced)
            assert_number(value, record['value'], key, 1e-8); reproduced[key] = value
    registry = verify_registry(read_json(project/'artigo/dados/numeros_rastreaveis.json'))
    root = Path(evidence['sources']['coorte_selecionada']['path']).parent
    cohort = gpd.read_parquet(root/'coorte_selecionada.parquet')
    all50 = gpd.read_parquet(root/'todas_unidades_50m.parquet')
    config = yaml.safe_load((project/'configs/terreno_congelado_etapa04.yaml').read_text())
    design = yaml.safe_load((project/'configs/amostra_pycrown_exploratoria_v0_3_0.yaml').read_text())
    if cohort.unit_id.duplicated().any() or not cohort.eligible_A_plus_3D.all(): raise ValueError('Coorte inválida')
    expected = []
    for _, group in all50.groupby('corridor_id'):
        eligible = group.loc[group.eligible_A_plus_3D].copy()
        eligible['independent_hash'] = [hashlib.sha256(f'{design["seed"]}:{u}'.encode()).hexdigest() for u in eligible.unit_id]
        expected.extend(eligible.sort_values(['independent_hash', 'unit_id']).head(design['target_units_per_corridor']).unit_id)
    if set(expected) != set(cohort.unit_id): raise ValueError('Seleção depende de outra regra')
    development = cohort.loc[cohort.role.eq('development')]; evaluation = cohort.loc[cohort.role.eq('evaluation')]
    if set(development.block_id) & set(evaluation.block_id): raise ValueError('Papéis compartilham bloco')
    overlap = float(cohort.geometry.area.sum()-shapely.union_all(cohort.geometry.to_numpy()).area)
    if abs(overlap) > 1e-6: raise ValueError('Unidades selecionadas sobrepostas')
    stored_scores = frames['escores_rankings']; stored_comparisons = frames['concordancia_ablacao']
    comparisons = []; largest_score_error = 0.
    for role, data in [('evaluation', evaluation), ('development', development)]:
        data = data.sort_values('unit_id').reset_index(drop=True); base, vertical = recipes(data)
        base_rank = ranked(data.unit_id, base, config['comparison']['score_tie_decimals'])
        for orientation, vector in vertical.items():
            features = {'Vplus': 'I6_I7', 'Vminus': 'I6_I7', 'height_only': 'I6_only', 'duplicate_control': 'I6_duplicate'}[orientation]
            for w in sorted(set(config['sensitivity']['vertical_weights'])):
                key = f'A_plus_3D__{features}__{orientation}__w{w:g}'
                variant = ranked(data.unit_id, (1-w)*base+w*vector, config['comparison']['score_tie_decimals'])
                old = stored_scores.loc[stored_scores.case.eq('sample_'+role) & stored_scores.scope.eq('conditional_canopy') & stored_scores.variant_id.eq(key)].set_index('unit_id').sort_index()
                if not old.index.equals(variant.index): raise ValueError('Universo de escores diferente')
                for column in ['score', 'score_for_ranking', 'rank_mean', 'rank_ordinal']:
                    diff = float(np.max(np.abs(variant[column]-old[column])))
                    if diff > 1e-12: raise ValueError(f'Escore/rank alterado: {role}/{key}/{column}')
                    if column == 'score': largest_score_error = max(largest_score_error, diff)
                result = compare(base_rank, variant, config['comparison']['primary_top_fraction'])
                old_result = stored_comparisons.loc[stored_comparisons.case.eq('sample_'+role) & stored_comparisons.scope.eq('conditional_canopy') & stored_comparisons.variant_id.eq(key) & stored_comparisons.top_fraction.eq(.2)]
                if len(old_result) != 1: raise ValueError('Comparação ambígua')
                for col, val in result.items(): assert_number(val, old_result.iloc[0][col], f'{role}/{key}/{col}')
                comparisons.append({'role': role, 'variant': key, **result})
    # H1: reconstituir todos os pares a partir dos indicadores, sem usar a lista pronta.
    pairs = []
    for a, b in itertools.combinations(evaluation.sort_values('unit_id').itertuples(), 2):
        if abs(a.I1-b.I1) <= config['comparison']['similar_cover_tolerance']+1e-12 and max(a.area_observed_m2, b.area_observed_m2)/min(a.area_observed_m2, b.area_observed_m2) <= config['comparison']['maximum_observed_area_ratio']+1e-12:
            pairs.append((a.unit_id, b.unit_id, abs(a.I6-b.I6)))
    old_pairs = frames['pares_cobertura_semelhante']; old_pairs = old_pairs.loc[old_pairs.case.eq('sample_evaluation')]
    if {(a, b) for a, b, _ in pairs} != set(zip(old_pairs.unit_i, old_pairs.unit_j)): raise ValueError('Pares H1 diferentes')
    median = float(np.median([v for _, _, v in pairs])); assert_number(median, evidence['metrics']['pairs_absolute_P95_difference_m_median']['value'], 'H1 mediana')
    # Reconstrução das 22 sensibilidades agrupadas, relendo suportes físicos pareados.
    run = read_json(root/'result.json'); stability = frames['sensibilidade_rankings_agrupada']; sensitivity = []; support_error = 0.
    scenario_ids = stability.scenario_id.unique()
    frozen_ids = set(cohort.unit_id)
    for scenario in scenario_ids:
        left = []; right = []
        for cid, case in run['case_results'].items():
            folder = Path(case['root'])/scenario; seal = read_json(Path(case['root'])/'complete.json')
            hashes = {p['path']: p for p in seal['outputs']}
            for name, target in [('principal_suporte_comum', left), ('cenario_suporte_comum', right)]:
                path = folder/(name+'.parquet')
                if fingerprint(path) != hashes[str(path)]: raise ValueError('Suporte pareado alterado')
                target.append(gpd.read_parquet(path))
        a = pd.concat(left).set_index('unit_id').sort_index(); b = pd.concat(right).set_index('unit_id').sort_index()
        if not a.index.equals(b.index): raise ValueError('IDs físicos dos suportes diferentes')
        err = float(np.max(np.abs(a.area_observed_m2-b.area_observed_m2))); support_error = max(support_error, err)
        if err > 1e-7: raise ValueError('Área de suporte difere entre receitas')
        for role in ['evaluation', 'development']:
            ids = sorted(frozen_ids & set(a.index[a.role.eq(role) & a.eligible_A_plus_3D]) & set(b.index[b.role.eq(role) & b.eligible_A_plus_3D]))
            ranks = []
            for frame in [a.loc[ids].reset_index(), b.loc[ids].reset_index()]:
                base, vertical = recipes(frame); ranks.append(ranked(frame.unit_id, .5*base+.5*vertical['Vplus']))
            stats = compare(*ranks)
            old = stability.loc[stability.role.eq(role) & stability.scenario_id.eq(scenario)]
            if len(old) != 1: raise ValueError('Cenário agrupado ambíguo')
            for col, value in stats.items(): assert_number(value, old.iloc[0][col], f'{scenario}/{role}/{col}')
            sensitivity.append({'role': role, 'scenario_id': scenario, **stats})
    output = {'history': history, 'primary_source_files_verified': len(frames), 'stage13_metrics_reproduced': len(reproduced),
        'article_registry': registry, 'selected_units': len(cohort), 'evaluation_units': len(evaluation), 'development_units': len(development),
        'selection_by_hash_reproduced': True, 'role_blocks_disjoint': True, 'selected_units_overlap_area_m2': overlap,
        'independent_spatial_groups_certified': False, 'score_variants_reproduced': comparisons,
        'maximum_score_absolute_error': largest_score_error, 'H1_pairs': len(pairs), 'H1_median_absolute_P95_difference_m': median,
        'sensitivities_reproduced': sensitivity, 'maximum_common_observed_area_difference_m2': support_error,
        'tolerances': {'scores_ranks_statistics_absolute': 1e-12, 'metric_aggregations_absolute': 1e-8, 'overlap_area_m2': 1e-6, 'paired_area_m2': 1e-7},
        'p_values_computed': False, 'new_scientific_parameter_choices': False, 'external_accuracy_evaluated': False}
    atomic_write_json(out/'auditoria_cientifica.json', output)
    return output
