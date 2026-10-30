"""Invariantes científicos: pareamento sem olhar H, perdas e suporte separados."""
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from sbsr_lidar.config import load_config
from sbsr_lidar.complementary_analysis import (horizontal_candidates, select_horizontal_pairs,
    disjoint_horizontal_pairs, strict_fixed_ids, stability_analysis, summarize_pairs)


def cohort(n=12):
    ids = [f'u{i:02d}' for i in range(n)]
    return gpd.GeoDataFrame({'unit_id': ids, 'corridor_id': ['c1']*n,
        'eligible_A_plus_3D': [True]*n, 'eligible_A': [True]*n,
        'I1': np.linspace(.1, .4, n), 'I4': np.linspace(1., 5., n),
        'I6': np.linspace(4., 30., n), 'I7': np.linspace(1., 8., n),
        'area_observed_m2': [100.]*n, 'area_total_m2': [100.]*n,
        'fraction_observed': [1.]*n, 'area_canopy_m2': [30.]*n,
        'n_vegetation_records': [100]*n, 'height_missing_reason': [None]*n,
        'exclusion_reason_A_plus_3D': [None]*n,
        'geometry': [box(i*20, 0, i*20+10, 10) for i in range(n)]}, crs=31983)


def primary_pairs(data):
    return select_horizontal_pairs(horizontal_candidates(data), .05, .1, scope='within_corridor')


def test_pair_selection_and_disjoint_matching_do_not_use_height():
    a = cohort(); b = a.copy(); b.I6 = a.I6.iloc[::-1].to_numpy()*100; b.I7 = 0.
    x, y = primary_pairs(a), primary_pairs(b)
    keys = ['unit_i', 'unit_j']
    pd.testing.assert_frame_equal(x[keys], y[keys])
    pd.testing.assert_frame_equal(disjoint_horizontal_pairs(x, .05, .1)[keys], disjoint_horizontal_pairs(y, .05, .1)[keys])


def test_matching_is_deterministic_and_never_reuses_a_unit():
    a = cohort(); x = disjoint_horizontal_pairs(primary_pairs(a), .05, .1)
    y = disjoint_horizontal_pairs(primary_pairs(a.sample(frac=1, random_state=31)), .05, .1)
    pd.testing.assert_frame_equal(x, y)
    ids = list(x.unit_i)+list(x.unit_j)
    assert len(ids) == len(set(ids))


def test_same_coverage_does_not_imply_same_fragmentation():
    a = cohort(); a.I1 = .3
    candidates = horizontal_candidates(a)
    old = select_horizontal_pairs(candidates, .05, None)
    strict = select_horizontal_pairs(candidates, .05, .1)
    assert len(strict) < len(old)
    assert strict.absolute_fragmentation_rank_difference.max() <= .1


def test_horizontal_match_can_show_vertical_difference_without_any_score():
    a = cohort(2); a.I1 = .3; a.I4 = 2.; a.I6 = [5., 20.]
    pairs = primary_pairs(a)
    assert len(pairs) == 1
    assert summarize_pairs(pairs, [5.])['P95_difference_median_m'] == 15.
    assert 'score' not in pairs.columns


def test_within_corridor_and_area_calipers_are_enforced():
    a = cohort(3); a.I1 = .3; a.I4 = 2.; a.corridor_id = ['a', 'a', 'b']; a.loc[1, 'area_observed_m2'] = 20.
    assert primary_pairs(a).empty
    assert len(select_horizontal_pairs(horizontal_candidates(a), .05, .1, scope='between_corridors')) == 1


def test_fixed_ids_use_all_scenarios_and_both_sides():
    p = cohort(); a = p.copy(); b = p.copy()
    a.loc[0, 'eligible_A_plus_3D'] = False; b.loc[1, 'eligible_A_plus_3D'] = False
    fixed = strict_fixed_ids(list(p.unit_id), {'s1': (a, p), 's2': (p, b)})
    assert fixed == list(p.unit_id.iloc[2:])


def test_empty_strict_cohort_is_reported_without_fallback():
    p = cohort(); a = p.copy(); a.eligible_A_plus_3D = False
    r = stability_analysis(p, {'s': (a, p)}, load_config(Path(__file__).resolve().parents[2]/'configs/terreno_congelado_etapa04.yaml'))
    assert r['fixed_ids'] == []
    assert r['rankings'].empty
    assert r['fixed_primary_ablation'] is None
    assert r['fixed_cohort_missing_reason'] == 'empty_strict_intersection_no_fallback'


def test_unrecorded_missing_unit_or_duplicate_is_an_error():
    p = cohort()
    with pytest.raises(ValueError, match='ausente'): strict_fixed_ids(list(p.unit_id), {'s': (p.iloc[1:], p)})
    with pytest.raises(ValueError, match='duplicados'): horizontal_candidates(pd.concat([p, p.iloc[:1]]))


def test_pair_support_disagreement_is_rejected():
    p = cohort(); b = p.copy(); b.loc[0, 'area_observed_m2'] = 99.
    with pytest.raises(ValueError, match='áreas observadas comuns'): stability_analysis(p, {'s': (p, b)}, load_config(Path(__file__).resolve().parents[2]/'configs/terreno_congelado_etapa04.yaml'))


def test_support_change_not_attributed_to_method_when_two_sides_equal():
    p = cohort(); b = p.copy(); b.I6 = b.I6.iloc[::-1].to_numpy(); b.I1 = b.I1.iloc[::-1].to_numpy()
    b.area_observed_m2 = 98.; b.fraction_observed = .98
    r = stability_analysis(p, {'s': (b, b)}, load_config(Path(__file__).resolve().parents[2]/'configs/terreno_congelado_etapa04.yaml'))['comparisons']
    method = r.query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'method_on_pair_support'").iloc[0]
    support = r.query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'support_only'").iloc[0]
    assert method.spearman_rho == pytest.approx(1.)
    assert method.same_exact_top
    assert method.jaccard_exact is None  # k=3: guarda original de listas pequenas.
    assert support.spearman_rho < .99


def test_fixed_cohort_reranks_every_comparison_on_the_same_universe():
    p = cohort(); a = p.copy(); a.loc[0, 'eligible_A_plus_3D'] = False
    result = stability_analysis(p, {'s1': (a, p), 's2': (p, p)}, load_config(Path(__file__).resolve().parents[2]/'configs/terreno_congelado_etapa04.yaml'))
    groups = result['rankings'].groupby(['scenario_id', 'measurement', 'analysis_method'])
    assert all(set(g.unit_id) == set(p.unit_id.iloc[1:]) for _, g in groups)
    assert all(set(g.rank_ordinal) == set(range(1, 12)) for _, g in groups)


def test_constant_scores_keep_ties_and_suppress_spearman():
    p = cohort(); p[['I1', 'I4', 'I6', 'I7']] = [.3, 2., 10., 4.]
    result = stability_analysis(p, {'s': (p, p)}, load_config(Path(__file__).resolve().parents[2]/'configs/terreno_congelado_etapa04.yaml'))['comparisons']
    assert result.spearman_rho.isna().all()
    assert result.same_exact_top.all()
    assert result.base_tie_at_cut_n.eq(12).all()
