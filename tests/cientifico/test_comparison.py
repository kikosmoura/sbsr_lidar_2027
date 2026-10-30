from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from scipy.stats import rankdata
from shapely.geometry import box

from test_reference import annotation_package
from sbsr_lidar.comparison_analysis import analyze_comparisons, common_membership, similar_cover_pairs
from sbsr_lidar.comparison_run import comparison_run
from sbsr_lidar.comparison_scores import (compare_rankings, descriptive_spearman, primary_variant,
    ranked_variant, rank_normalize, score_variants, top_selection, variant_id)
from sbsr_lidar.runtime import Run
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json


def sample_table(n=20, *, constant=False, corridor='SYN'):
    values = np.arange(n, dtype=float)
    frame = gpd.GeoDataFrame({'unit_id': [f'U{i:03d}' for i in range(n)], 'case': 'main',
        'corridor_id': corridor, 'family': 'grid', 'nominal_size_m': 50.,
        'area_total_m2': 100., 'area_observed_m2': 100., 'area_canopy_m2': 50.,
        'eligible_A': True, 'eligible_A_plus_3D': True, 'eligible_B': False, 'eligible_B_plus_3D': False,
        'I1': np.full(n, .5) if constant else (values+1)/(n+1),
        'I4': np.full(n, 1.) if constant else values+1,
        'I5': np.full(n, 8.) if constant else 8+values/3,
        'I6': np.full(n, 10.) if constant else 10+values,
        'I7': np.full(n, 2.) if constant else 2+values/2,
        'I2': np.full(n, np.nan), 'I3_local_over_observable_length': np.full(n, np.nan),
        'exclusion_reason_A': None, 'exclusion_reason_A_plus_3D': None,
        'longitudinal_missing_reason': 'unidade_em_grade'},
        geometry=[box(i*15, 0, i*15+10, 10) for i in range(n)], crs=31983)
    return frame


def simple_ranking(values, ids=None):
    values = np.asarray(values, dtype=float)
    ids = np.array(ids if ids is not None else [f'U{i:03d}' for i in range(len(values))])
    order = np.lexsort((ids, -values)); positions = np.empty(len(values), dtype=int)
    positions[order] = np.arange(1, len(values)+1)
    return pd.DataFrame({'unit_id': ids, 'stratum': 'with_candidate_canopy', 'stratum_order': 1,
        'score_for_ranking': values, 'rank_mean': rankdata(-values), 'rank_ordinal': positions})


def test_average_rank_normalization_ties_constant_and_monotonic_invariance():
    assert np.allclose(rank_normalize([1, 1, 3]), [1/3, 1/3, 5/6])
    assert np.array_equal(rank_normalize([7, 7, 7]), [.5, .5, .5])
    assert np.array_equal(rank_normalize([1, 2, 8]), rank_normalize([100, 400, 6400]))


@pytest.mark.parametrize('values', [[], [1, np.nan], [1, np.inf]])
def test_no_imputation_or_empty_normalizer(values):
    with pytest.raises(ValueError): rank_normalize(values)


def test_analytic_group_scores_orientation_and_accept_equivalence(config):
    table = sample_table(4)
    normal, variants = score_variants(table, config)
    by_id = {v['variant_id']: v for v in variants}
    assert np.allclose(by_id['A']['values'], .5)
    plus = by_id[primary_variant(config)]['values']
    assert np.allclose(plus, [.6875, .5625, .4375, .3125])
    minus = by_id[variant_id('A_plus_3D', 'I6_I7', 'Vminus', .5)]['values']
    assert np.allclose(minus, .5) # hipótese de equivalência é aceita pelo código
    for variant in variants:
        if variant['vertical_weight'] == 0:
            assert np.array_equal(variant['values'], by_id['A']['values'])


def test_duplicate_height_control_does_not_invent_increment(config):
    _, variants = score_variants(sample_table(), config)
    by_id = {v['variant_id']: v for v in variants}
    for weight in config.sensitivity.vertical_weights:
        a = by_id[variant_id('A_plus_3D', 'I6_only', 'height_only', weight)]['values']
        b = by_id[variant_id('A_plus_3D', 'I6_duplicate', 'duplicate_control', weight)]['values']
        assert np.array_equal(a, b)


def test_B_C_formula_uses_longitudinal_domain_and_separate_base(config):
    table = sample_table(4)
    table['I2'] = [.1, .2, .3, .4]
    table['I3_local_over_observable_length'] = [.4, .3, .2, .1]
    normal, variants = score_variants(table, config, longitudinal=True)
    by_id = {v['variant_id']: v for v in variants}
    assert np.allclose(by_id['B']['values'], (normal.S_A+normal.D_gap)/2)
    key = variant_id('C', 'I6_I7', 'Vplus', .5)
    expected = .5*by_id['B']['values']+.5*(1-normal.R_I6+1-normal.R_I7)/2
    assert np.allclose(by_id[key]['values'], expected)
    assert by_id[key]['baseline_id'] == 'B' and by_id[primary_variant(config)]['method'] == 'A_plus_3D'


def test_all_constant_indicators_create_no_artificial_rank_difference(config):
    table = sample_table(20, constant=True)
    normal, variants = score_variants(table, config)
    ranked = [ranked_variant(table, table.iloc[:0], v, normal, config, 'conditional_canopy') for v in variants]
    for rank in ranked:
        assert rank.rank_mean.eq(10.5).all() and rank.score.eq(.5).all()
    result, _, _ = compare_rankings(ranked[0], ranked[1], .3, config)
    assert result['same_ranks'] and result['mean_absolute_rank_shift'] == 0
    assert result['spearman_rho'] is None and result['spearman_missing_reason'] == 'variavel_constante'
    assert result['base_tie_at_cut_n'] == 20 and result['base_inclusive_n'] == 20


def test_top_cardinality_and_entire_cutoff_tie_and_ID_rule(config):
    a = simple_ranking([1]*10, ids=[f'U{i:03d}' for i in range(9, -1, -1)])
    selected = top_selection(a, .2)
    assert selected['k'] == 2 and selected['exact'] == {'U000', 'U001'}
    assert selected['inclusive'] == set(a.unit_id) and selected['tie_at_cut_n'] == 10
    assert selected['tie_crosses_cut']
    result, _, _ = compare_rankings(a, a, .2, config)
    assert result['jaccard_exact'] is None and result['jaccard_including_cut_ties'] is None
    assert result['same_exact_top']


def test_top_Jaccard_and_rank_shift_known_reversal(config):
    a, b = simple_ranking(np.arange(20.)), simple_ranking(np.arange(20.)[::-1])
    result, left, right = compare_rankings(a, b, .3, config)
    assert result['k'] == 6 and result['top_intersection_n'] == 0 and result['jaccard_exact'] == 0
    assert np.isclose(result['spearman_rho'], -1) and result['maximum_absolute_rank_shift'] == 19


def test_different_universes_are_rejected(config):
    a, b = simple_ranking([1, 2, 3]), simple_ranking([1, 2, 3], ['A', 'B', 'C'])
    with pytest.raises(ValueError, match='mesmo universo'): compare_rankings(a, b, .2, config)


def test_small_cohort_has_no_meaningful_correlation_or_Jaccard(config):
    a, b = simple_ranking([1, 2]), simple_ranking([2, 1])
    result, _, _ = compare_rankings(a, b, .3, config)
    assert result['spearman_rho'] is None and result['jaccard_exact'] is None and result['k'] == 1
    assert descriptive_spearman([1, 1, 3], [4, 4, 2])[0] == -1


def test_absence_is_superior_shared_stratum_with_null_height_score(config):
    cohort = sample_table(3)
    absent = sample_table(2); absent['unit_id'] = ['Z1', 'Z0']; absent['I6'] = np.nan; absent['I7'] = np.nan
    normal, variants = score_variants(cohort, config)
    a = ranked_variant(cohort, absent, variants[0], normal, config, 'joint_strata')
    b = ranked_variant(cohort, absent, variants[1], normal, config, 'joint_strata')
    no_canopy = a[a.stratum == 'no_detected_canopy']
    assert no_canopy.unit_id.tolist() == ['Z0', 'Z1'] and no_canopy.rank_mean.eq(1.5).all()
    assert no_canopy[['I6', 'I7', 'score']].isna().all().all()
    assert no_canopy.S_A.isna().all() # não incluir ausência no ajuste do normalizador
    assert a.iloc[2:].rank_mean.min() >= 3
    _, x, y = compare_rankings(a, b, .2, config)
    assert x['exact'] == y['exact'] == {'Z0'} and x['inclusive'] == y['inclusive'] == {'Z0', 'Z1'}


def test_similar_cover_pairs_area_ratio_boundary_and_no_independent_pair_claim(config):
    t = sample_table(3)
    t['I1'] = [.50, .55, .60]; t['area_observed_m2'] = [100., 200., 500.]
    pairs = similar_cover_pairs(t, config)
    assert len(pairs) == 1 and pairs[0]['unit_i'] == 'U000' and pairs[0]['unit_j'] == 'U001'
    assert pairs[0]['observed_area_ratio'] == 2 and pairs[0]['pairs_are_not_independent_replicates']
    assert pairs[0]['absolute_P95_difference_m'] == 1


def test_membership_support_exclusions_and_same_cohort_for_every_variant(config):
    t = sample_table(6)
    t.loc[0, ['eligible_A_plus_3D', 'area_canopy_m2']] = [False, 0.]
    t.loc[0, ['I6', 'I7']] = np.nan
    t.loc[1, 'eligible_A_plus_3D'] = False; t.loc[1, 'exclusion_reason_A_plus_3D'] = 'poucos_retornos'
    t.loc[2, ['eligible_A', 'eligible_A_plus_3D']] = False; t.loc[2, 'exclusion_reason_A'] = 'observacao_insuficiente'
    m = common_membership(t)
    assert m.comparison_role.tolist() == ['common_no_detected_canopy_stratum', 'A_only_descriptor', 'excluded', 'paired_canopy', 'paired_canopy', 'paired_canopy']
    outputs = analyze_comparisons(t, config, 'G_SYN')
    ranks = outputs['escores_rankings']
    for (scope, variant), g in ranks.groupby(['scope', 'variant_id']):
        assert set(g.unit_id) == ({'U003', 'U004', 'U005'} if scope == 'conditional_canopy' else {'U000', 'U003', 'U004', 'U005'})
    assert not outputs['disponibilidade_metodos'].loc[lambda d: d.method.isin(['B', 'C'])].available.any()


def test_ineligible_extreme_does_not_change_normalization_or_scores(config):
    a = sample_table()
    extra = sample_table(1); extra['unit_id'] = 'EXTREME'; extra['eligible_A'] = False; extra['eligible_A_plus_3D'] = False
    extra[['I1', 'I4', 'I6', 'I7']] = 1e20
    extra['exclusion_reason_A'] = 'observacao_insuficiente'
    b = gpd.GeoDataFrame(pd.concat([a, extra], ignore_index=True), crs=a.crs)
    x, y = (analyze_comparisons(t, config, 'G')['escores_rankings'] for t in [a, b])
    assert np.array_equal(x.score_for_ranking.to_numpy(), y.score_for_ranking.to_numpy())


def test_diagnostic_spatial_cells_do_not_fabricate_independent_blocks(config):
    out = analyze_comparisons(sample_table(30), config, 'ONE_GROUP')
    row = out['controles'].iloc[0]
    assert row.independent_corridor_groups_in_paired_cohort == 1
    assert not row.surrogate_permutations_performed and not row.p_values_computed and not row.predictive_models_trained


def test_empty_paired_cohort_yields_explicit_unavailability(config):
    table = sample_table(4); table['eligible_A_plus_3D'] = False
    table['exclusion_reason_A_plus_3D'] = 'retornos_insuficientes'
    out = analyze_comparisons(table, config, 'ONE_GROUP')
    assert out['escores_rankings'].empty and out['pares_cobertura_semelhante'].empty
    assert out['universos_comparacao'].A_only_descriptors.iloc[0] == 4


def test_pair_resource_guard_prevents_unbounded_work(config):
    c = config.model_copy(update={'comparison': config.comparison.model_copy(update={'maximum_pair_candidates': 2})})
    with pytest.raises(ValueError, match='orçamento'): similar_cover_pairs(sample_table(4), c)


def test_native_frozen_IO_cache_stale_source_and_labels_preserved(inputs, annotation_package):
    c = inputs
    folder = c.paths.output_root/'synthetic_stage08'; folder.mkdir(parents=True)
    run = Run(c.paths.runs_root, c.paths.state_file, 'synthetic-indicators', c.model_dump(mode='json'),
              [fingerprint(c.paths.protocol_file)], {}, '0'*64, stage='08')
    t = sample_table(20, corridor=c.pilot.corridor_id)
    t['scenario'] = 'baseline_h3'; t['canopy_run_id'] = 'SYN_CANOPY'; t['units_run_id'] = 'SYN_UNITS'
    t['indicator_run_id'] = run.run_id; t['protocol_version'] = c.protocol_version
    parquet, csv, dictionary = folder/'indicadores.parquet', folder/'indicadores.csv', folder/'dicionario.json'
    t.to_parquet(parquet, index=False)
    pd.DataFrame(t.drop(columns='geometry')).to_csv(csv, index=False)
    atomic_write_json(dictionary, {'synthetic': True})
    report = run.path/'indicadores.json'; atomic_write_json(report, {'case': 'main', 'synthetic': True})
    run.finish([report, parquet, csv, dictionary])
    entry = {'run_id': run.run_id, 'case': 'main', 'corridor_id': c.pilot.corridor_id,
        'manifest': str(run.path/'manifest.json'), 'report': str(report),
        'parquet': str(parquet), 'csv': str(csv), 'data_dictionary': str(dictionary)}
    atomic_write_json(c.paths.project_root/'docs/manifesto_etapa08.json', {'artifacts': [
        fingerprint(Path(p)) for p in [*run.manifest['outputs'], run.path/'manifest.json']]})
    pd.DataFrame({'corridor_id': [c.pilot.corridor_id], 'group_id': ['G_SYN'], 'fold': ['treino']}).to_csv(annotation_package/'grupos_reservados.csv', index=False)
    state = read_json(c.paths.state_file); state['etapas']['08'] = {'nome': 'indicadores', 'status': 'concluida', 'artefatos': []}
    state['indicadores_piloto'] = {'principal': entry}; state['referencia_anotacao'] = {'package': str(annotation_package)}
    atomic_write_json(c.paths.state_file, state)
    labels = fingerprint(annotation_package/'trabalho/anotacoes.gpkg'); before = fingerprint(parquet)
    result = comparison_run(c, 'main'); r = read_json(Path(result['report']))
    assert not r['predictive_models_trained'] and not r['accuracy_gain_claimed'] and not r['p_values_computed']
    scores = pd.read_parquet(Path(result['products_root'])/'escores_rankings.parquet')
    assert scores.variant_id.nunique() == 17 and not scores.method.isin(['B', 'C']).any()
    assert gpd.read_parquet(Path(result['products_root'])/'desacordos_espaciais.parquet').crs.to_epsg() == 31983
    cached = comparison_run(c, 'main')
    assert cached['cache_hit'] and cached['report'] == result['report']
    assert fingerprint(annotation_package/'trabalho/anotacoes.gpkg') == labels and fingerprint(parquet) == before
    with parquet.open('ab') as handle: handle.write(b'changed')
    with pytest.raises(ValueError, match='Indicadores congelados mudaram'): comparison_run(c, 'main')
