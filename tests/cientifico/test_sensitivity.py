"""Invariantes científicos: identidade amostral, denominadores e suporte."""
from dataclasses import replace
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from sbsr_lidar.config import load_config
from sbsr_lidar.sensitivity_scenarios import Scenario, scenarios, thinning_uniform, scenario_domain
from sbsr_lidar.sensitivity_analysis import stability, weighted_correlation, paired_comparison
from sbsr_lidar.domain import Domain
from sbsr_lidar.comparison_scores import rank_normalize
from sbsr_lidar.sensitivity_analysis import metrics
from sbsr_lidar.indicator_support import RasterSupport
from sbsr_lidar.sensitivity_analysis import area_support
from affine import Affine
from shapely.geometry import GeometryCollection, LineString, Point


@pytest.fixture
def config():
    from pathlib import Path
    return load_config(Path('configs/terreno_congelado_etapa04.yaml'))


def test_scenario_budget_and_domain_separation(config):
    specs = scenarios(config)
    assert len(specs) == 30
    assert sum(s.expansion_m > 0 for s in specs) == 2
    assert len({s.scenario_id for s in specs}) == 30
    assert {s.resolution_m for s in specs} == {.5, 1, 2}
    assert {s.height_m for s in specs} == {2, 3, 5}
    assert len([s for s in specs if s.axis == 'selected_interaction']) == 2


def test_thinning_is_identity_based_nested_and_chunk_invariant():
    tiles = np.array(['3313-333']*10000+['3313-361']*10000)
    indices = np.tile(np.arange(10000), 2)
    values = thinning_uniform(tiles, indices, 2027)
    order = np.random.default_rng(11).permutation(len(values))
    assert np.array_equal(values[order], thinning_uniform(tiles[order], indices[order], 2027))
    assert np.array_equal(values, np.r_[thinning_uniform(tiles[:713], indices[:713], 2027), thinning_uniform(tiles[713:], indices[713:], 2027)])
    assert np.all((values < .25) <= (values < .5))
    assert .23 < (values < .25).mean() < .27
    assert not np.array_equal(values[:10000], values[10000:])
    assert not np.array_equal(values, thinning_uniform(tiles, indices, 2028))


def test_context_and_measurement_expansion_are_different():
    tiles = gpd.GeoDataFrame({'quadricula': ['3313-333']}, geometry=[box(-100, -100, 200, 200)], crs=31983)
    p = box(0, 0, 10, 10)
    base = Domain('main', 'C', p, p, p.buffer(10), tiles, {})
    context = p.buffer(20).union(p.buffer(10).buffer(10))
    maximal = Domain('main', 'C', p, p, context, tiles, {})
    halo = scenario_domain(base, maximal, replace(Scenario(), halo_m=20))
    expanded = scenario_domain(base, maximal, replace(Scenario(), expansion_m=10))
    assert halo.measurement.equals(p)
    assert expanded.measurement.area > p.area
    assert expanded.context.difference(maximal.context).area < 1e-5


def test_stability_rejects_changed_universe(config):
    a = pd.DataFrame({'unit_id': ['a']}); b = pd.DataFrame({'unit_id': ['b']})
    with pytest.raises(ValueError, match='Universos'):
        stability([('one', 'x', a), ('two', 'x', b)], None, config, 'test')


def test_weighted_overlap_correlation_not_row_count():
    x, y, w = [0, 1, 1], [0, 1, 0], [100, 100, 1]
    assert weighted_correlation(x, y, w) > .98
    assert weighted_correlation([1, 1], [0, 1], [1, 1]) is None
    assert weighted_correlation([], [], []) is None


def test_pairwise_fixed_universe_no_imputation_and_decomposition(config):
    base = pd.DataFrame({'unit_id': ['a', 'b', 'c', 'd'], 'scale_m': [50]*4,
        'eligible_A_plus_3D': [True]*4, 'I1': [.1, .3, .5, .8], 'I4': [3, 2, 1, 1],
        'I6': [5., 10., 15., 20.], 'I7': [2., 4., 3., 1.],
        'density_vegetation_records_per_canopy_m2': [10.]*4, 'n_vegetation_records': [100]*4})
    candidate = base.copy(); candidate.loc[0, 'eligible_A_plus_3D'] = False
    candidate.loc[1, 'I6'] = 17.
    summary, changes = paired_comparison(base, candidate, config, Scenario(), 100.)
    row = summary.loc[summary.scale_m == 50].iloc[0]
    assert row['n'] == 3 and pd.isna(row.jaccard_exact)
    assert set(changes.unit_id) == {'b', 'c', 'd'}
    terms = ['score_contribution_'+k for k in ['I1', 'I4', 'I6', 'I7']]
    assert np.allclose(changes[terms].sum(axis=1), changes.score_difference)
    assert np.array_equal(rank_normalize([1, 1, 1]), [.5]*3)


def test_exact_common_support_filters_heights_without_relabeling_patches(config):
    config = config.model_copy(update={'support': config.support.model_copy(update={
        'minimum_unit_area_m2': .1, 'minimum_observed_fraction': .5,
        'minimum_canopy_area_m2': .1, 'minimum_vegetation_returns': 1})})
    p = box(0, 0, 4, 2)
    domain = Domain('main', 'C', p, p, p, None, {})
    patches = gpd.GeoDataFrame({'patch_id': ['one_context_component'],
        'touches_context_limit': [True], 'touches_invalid_support': [False],
        'crosses_measurement_boundary': [True]}, geometry=[p], crs=31983)
    support = RasterSupport(np.ones((2, 4), 'uint8'), np.ones((2, 4), 'uint8'),
        np.zeros((2, 4), 'uint16'), np.ones((2, 4), bool), Affine(1, 0, 0, 0, -1, 2), 31983)
    raw = pd.DataFrame({'x': [.5, 1.5, 2.5, 3.5], 'y': [.5]*4})
    product = {'observed': p, 'patches': patches, 'domain': domain, 'support': support,
        'inside': np.ones(4, bool), 'retained': np.ones(4, bool), 'candidate': np.ones(4, bool),
        'rr': np.ones(4, int), 'cc': np.arange(4), 'h': np.array([5., 50., 60., 8.]),
        'config': config, 'scenario': Scenario()}
    units = gpd.GeoDataFrame({'unit_id': ['a', 'b'], 'corridor_id': ['C']*2}, geometry=[box(0, 0, 2, 2), box(2, 0, 4, 2)], crs=31983)
    common = p.difference(box(1, 0, 3, 1))
    result = metrics(config, product, {50: (units, np.array([0, 0, 1, 1]))}, raw, common)
    assert np.array_equal(result.n_vegetation_records, [1, 1])
    assert np.array_equal(result.n_patches, [1, 1])
    assert np.allclose(result.area_observed_m2, [3, 3])
    assert np.allclose(result.I1, [1, 1]) and np.allclose(result.I4, [10000/3]*2)
    assert np.array_equal(result.I6, [5, 8])


def test_zero_area_contact_does_not_create_common_observed_surface():
    geometry = GeometryCollection([box(0, 0, 1, 1), LineString([(2, 0), (3, 0)]), Point(4, 0)])
    support = area_support(geometry)
    assert support.area == geometry.area == 1
    assert not support.intersects(Point(2.5, 0))
    assert not support.intersects(Point(4, 0))
