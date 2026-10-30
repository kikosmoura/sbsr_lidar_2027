from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from affine import Affine
from shapely.geometry import LineString, MultiPolygon, Polygon, box

from test_terrain import terrain_inputs
from test_reference import annotation_package
from sbsr_lidar.canopy import canopy_run
from sbsr_lidar.domain import Domain
from sbsr_lidar.indicator_metrics import area_metrics, height_metrics, longitudinal_metrics
from sbsr_lidar.indicator_run import compute_indicators, data_dictionary, indicators_run, support_geometries
from sbsr_lidar.indicator_support import RasterSupport, UnitAssigner
from sbsr_lidar.longitudinal import branch_sequences, branch_stations
from sbsr_lidar.segmentation import segmentation_run
from sbsr_lidar.spatial_units import regular_grid
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json
from sbsr_lidar.terrain import terrain_run


def support(canopy=1, observation=1, uncertainty=0):
    return RasterSupport(np.full((10, 10), observation, dtype='uint8'),
        np.full((10, 10), canopy, dtype='uint8'), np.full((10, 10), uncertainty, dtype='uint16'),
        np.ones((10, 10), dtype=bool), Affine(1, 0, 0, 0, -1, 10), 31983)


def patches(config, geometries):
    return gpd.GeoDataFrame({'patch_id': [f'P{i}' for i in range(len(geometries))],
        'touches_context_limit': [False]*len(geometries), 'touches_invalid_support': [False]*len(geometries),
        'crosses_measurement_boundary': [False]*len(geometries)}, geometry=geometries, crs=config.grid.epsg)


def returns(path, h=8., classification=3, n=100):
    x, y = np.meshgrid(np.arange(.25, 10, 1), np.arange(.25, 10, 1))
    heights = np.broadcast_to(h, (n,)).astype(float)
    d = pd.DataFrame({'x': x.ravel()[:n], 'y': y.ravel()[:n], 'h': heights,
        'classification': np.broadcast_to(classification, (n,)),
        'terrain_status': np.where(np.isfinite(heights), 0, 1),
        'qc_flags': np.where(heights > 80, 16, 0).astype('uint16'), 'z_absolute': np.full(n, 700.)})
    pq.write_table(pa.Table.from_pandas(d, preserve_index=False), path)
    return path


def setup_units(config, obs, canopy):
    p = box(0, 0, 10, 10)
    tiles = gpd.GeoDataFrame({'quadricula': ['3313-333']}, geometry=[p], crs=config.grid.epsg)
    d = Domain('main', 'SYN', p, p, p, tiles, {'measurement_is_official_polygon': True})
    g = regular_grid(config, d, obs, Polygon(), 10.)
    return d, {'grid_10': g}


def compute(config, tmp_path, raster=None, crown=None, observed=None, heights=8., cls=3, n=100, patch_frame=None):
    p = box(0, 0, 10, 10)
    raster = support() if raster is None else raster
    observed = p if observed is None else observed
    crown = p if crown is None else crown
    patch_frame = patches(config, [] if crown.is_empty else [crown]) if patch_frame is None else patch_frame
    d, groups = setup_units(config, observed, crown)
    return compute_indicators(config, d, groups, raster, observed, crown, patch_frame,
        returns(tmp_path/'h.parquet', heights, cls, n), pd.DataFrame(), pd.DataFrame(),
        {'scenario': 'baseline_h3'})


def test_known_area_constant_normalized_height_and_record_density(config, tmp_path):
    table, links, qc = compute(config, tmp_path)
    row = table.iloc[0]
    assert row.area_total_m2 == row.area_observed_m2 == row.area_canopy_m2 == 100
    assert row.I1 == 1 and row.I4 == 100 and row.n_patches == 1
    assert row.I5 == row.I6 == 8 and row.I7 == 0 # não z_absolute=700
    assert row.n_vegetation_records == 100 and row.density_vegetation_records_per_canopy_m2 == 1
    assert row.eligible_A and row.eligible_A_plus_3D
    assert pd.isna(row.I2) and row.longitudinal_missing_reason == 'unidade_em_grade'
    assert row.n_cells_observed_center == row.n_cells_canopy_center == 100
    assert links.intersection_area_m2.sum() == 100


def test_exact_linear_quantiles_not_cell_surface_or_height_zero(config, tmp_path):
    table, _, _ = compute(config, tmp_path, heights=np.arange(3., 103.))
    row = table.iloc[0]
    assert np.isclose(row.I5, 52.5) and np.isclose(row.I6, 97.05) and row.I7 == 49.5
    assert row.n_vegetation_height_extreme_warning > 0 # flag de alerta não é filtro inventado


def test_context_crown_crossing_border_only_intersection_counts(config, tmp_path):
    p = box(0, 0, 10, 10)
    crown = box(0, 0, 5, 10)
    raster = support(); raster.canopy[:, 5:] = 0
    table, links, _ = compute(config, tmp_path, raster=raster, crown=crown,
                              patch_frame=patches(config, [box(-10, 0, 5, 10)]))
    row = table.iloc[0]
    assert row.area_canopy_m2 == row.largest_patch_intersection_m2 == 50
    assert row.I1 == .5 and row.I4 == 100 and row.n_vegetation_records == 50
    assert links.intersection_area_m2.iloc[0] == 50


def test_partial_observation_reports_bounds_and_excludes_comparison(config, tmp_path):
    raster = support(); raster.observation[:, 5:] = 2; raster.canopy[:, 5:] = 255
    observed = box(0, 0, 5, 10)
    table, _, _ = compute(config, tmp_path, raster=raster, observed=observed, crown=observed)
    row = table.iloc[0]
    assert row.area_observed_m2 == row.area_canopy_m2 == 50 and row.I1 == 1 and row.I4 == 200
    assert row.fraction_observed == row.fraction_unobserved == .5
    assert row.canopy_total_fraction_lower_bound == .5 and row.canopy_total_fraction_upper_bound == 1
    assert row.height_support_sufficient and row.I6 == 8
    assert not row.eligible_A and not row.eligible_A_plus_3D
    assert row.exclusion_reason_A == 'fracao_observada_insuficiente'


def test_no_observation_has_null_coverage_height_and_fragmentation(config, tmp_path):
    table, _, _ = compute(config, tmp_path, raster=support(255, 2), crown=Polygon(), observed=Polygon(), n=0)
    row = table.iloc[0]
    assert pd.isna(row.I1) and pd.isna(row.I4) and pd.isna(row.I6)
    assert row.observation_state == 'sem_observacao' and row.height_missing_reason == 'sem_suporte_comum'
    assert row.canopy_total_fraction_lower_bound == 0 and row.canopy_total_fraction_upper_bound == 1


def test_observed_no_canopy_has_zero_coverage_but_no_fake_height(config, tmp_path):
    table, _, _ = compute(config, tmp_path, raster=support(0), crown=Polygon(), heights=0., cls=2)
    row = table.iloc[0]
    assert row.I1 == row.I4 == row.n_patches == 0
    assert pd.isna(row.I5) and pd.isna(row.I6) and pd.isna(row.I7)
    assert row.height_missing_reason == 'sem_vegetacao'
    assert row.canopy_height_stratum == 'sem_copa_detectada' and row.eligible_A and not row.eligible_A_plus_3D


def test_no_terrain_is_distinct_from_no_MDS_observation(config, tmp_path):
    table, _, _ = compute(config, tmp_path, raster=support(255, 3), crown=Polygon(), observed=Polygon(), n=0)
    row = table.iloc[0]
    assert row.observation_state == 'sem_suporte_terreno_ou_H'
    assert row.area_MDS_usable_m2 == 100 and row.area_observed_m2 == 0 and pd.isna(row.I1)


def test_semantic_uncertainty_stays_in_observed_denominator(config, tmp_path):
    table, _, _ = compute(config, tmp_path, raster=support(0, 1, 1), crown=Polygon(), heights=5., cls=1)
    row = table.iloc[0]
    assert row.area_classification_uncertain_m2 == row.area_observed_m2 == 100
    assert row.state == 'classificacao_incerta' and row.I1 == 0
    assert row.height_missing_reason == 'classificacao_incerta_sem_copa_detectada'


@pytest.mark.parametrize('area,n,reason', [(5., 100, 'area_copa_insuficiente'), (100., 49, 'retornos_vegetais_insuficientes')])
def test_insufficient_height_support_is_not_numeric_reliability(config, area, n, reason):
    a = {'area_observed_m2': 100., 'area_canopy_m2': area, 'eligible_A': True,
         'classification_uncertainty_present': False, 'exclusion_reason_A': None}
    result = height_metrics(np.full(n, 8.), a, config)
    assert result['height_missing_reason'] == reason and result['I6'] is None and not result['eligible_A_plus_3D']


def test_class3_kept_while_building_and_low_returns_do_not_enter_quantiles(config, tmp_path):
    classes = np.r_[np.full(50, 3), np.full(25, 6), np.full(25, 3)]
    heights = np.r_[np.full(50, 8.), np.full(25, 30.), np.full(25, 2.)]
    table, _, _ = compute(config, tmp_path, heights=heights, cls=classes)
    row = table.iloc[0]
    assert row.n_vegetation_records == 50 and row.I5 == row.I6 == 8


def test_boundary_points_have_single_owner_in_pixel_with_positive_area(config):
    g = gpd.GeoDataFrame({'unit_id': ['A', 'B']}, geometry=[box(0, 0, 5, 10), box(5, 0, 10, 10)], crs=31983)
    a = UnitAssigner(g, support())
    owners = a.assign(np.array([5., 2.]), np.array([5., 5.]))
    assert owners.tolist() == [1, 0] and a.boundary_ties == 1
    b = UnitAssigner(g.iloc[::-1], support())
    assert b.assign(np.array([5.]), np.array([5.])).tolist() == [1]


def test_multipart_same_context_patch_counted_once_and_touch_only_excluded(config):
    p = box(0, 0, 10, 10)
    component = MultiPolygon([box(0, 0, 2, 2), box(8, 8, 10, 10)])
    patch_frame = patches(config, [component, box(10, 0, 20, 10)])
    raster = support()
    a, links = area_metrics(p, p, patch_frame, support_geometries(raster, p, p), config)
    assert a['n_patches'] == 1 and a['area_canopy_m2'] == 8 and len(links) == 1


def test_longitudinal_gap_physical_lengths_and_censor_preserved(config):
    p = box(0, -5, 120, 5)
    b = {'branch_id': 'B', 'part_id': 'P', 'length_m': 120., 'geometry': LineString([(0, 0), (120, 0)])}
    crown = MultiPolygon([box(0, -5, 10, 5), box(90, -5, 120, 5)])
    s = branch_stations(config, b, p, p, crown, Polygon())
    q = branch_sequences(s, b)
    u = {'family': 'longitudinal', 'branch_id': 'B', 'start_m': 50., 'end_m': 100., 'axis_accepted_geometrically': True}
    r = longitudinal_metrics(u, pd.DataFrame(s), pd.DataFrame(q), {'eligible_A': True}, config)
    assert r['length_observable_m'] == 50 and r['I2'] == .8 and r['I3_local_m'] == 40
    assert r['I3_branch_m'] == 80 and r['I3_local_censored'] # corte local aos 50m
    s[55]['full_section_observable'] = False; s[55]['state'] = 'unknown_support'
    # Exigir 100% demonstra que a mesma geometria não autoriza métrica sem suporte.
    c = config.model_copy(update={'support': config.support.model_copy(update={'minimum_observed_fraction': 1.})})
    r = longitudinal_metrics(u, pd.DataFrame(s), pd.DataFrame(branch_sequences(s, b)), {'eligible_A': True}, c)
    assert r['I2'] is None and r['I3_local_m'] is None and r['length_unknown_m'] == 1
    assert r['associated_branch_gap_left_censored'] is True
    assert r['associated_gap_start_m'] == 56 and r['associated_gap_end_m'] == 90


def test_censored_branch_gap_not_reported_as_complete_length(config):
    p = box(0, -5, 120, 5)
    b = {'branch_id': 'B', 'part_id': 'P', 'length_m': 120., 'geometry': LineString([(0, 0), (120, 0)])}
    s = branch_stations(config, b, p, p, Polygon(), Polygon())
    q = branch_sequences(s, b)
    u = {'family': 'longitudinal', 'branch_id': 'B', 'start_m': 25., 'end_m': 50., 'axis_accepted_geometrically': True}
    r = longitudinal_metrics(u, pd.DataFrame(s), pd.DataFrame(q), {'eligible_A': True}, config)
    assert r['I2'] == 1 and r['I3_local_m'] == 25 and r['I3_branch_m'] is None
    assert r['branch_gap_missing_reason'] == 'lacuna_ramo_censurada'


def test_exact_quantile_pool_has_explicit_pilot_budget(config, tmp_path):
    c = config.model_copy(update={'indicators': config.indicators.model_copy(update={'maximum_stored_height_values': 1})})
    with pytest.raises(ValueError, match='orçamento de alturas'):
        compute(c, tmp_path)


def test_dictionary_covers_real_columns_and_explicit_estimands(config, tmp_path):
    table, _, _ = compute(config, tmp_path)
    dictionary = data_dictionary(table, config)
    assert set(dictionary['columns']) == set(table.columns)
    assert dictionary['columns']['I6']['formula'] == 'quantile(H,0.95,method=linear)'
    assert 'retornos' in dictionary['columns']['I7']['estimand']
    atomic_write_json(tmp_path/'dictionary.json', dictionary)


def test_end_to_end_frozen_IO_cache_and_stale_units_rejected(terrain_inputs, annotation_package):
    c = terrain_inputs
    sources = {case: terrain_run(c, case, requested_method='tin') for case in ['main', 'adversarial']}
    s = read_json(c.paths.state_file)
    s['etapas']['04']['status'] = 'concluida'
    s['etapas']['05'] = {'nome': 'ref', 'status': 'concluida', 'artefatos': []}
    s['terreno_altura_piloto'] = {'principal': sources['main'], 'adverso': sources['adversarial']}
    s['referencia_anotacao'] = {'package': str(annotation_package)}
    atomic_write_json(c.paths.state_file, s)
    atomic_write_json(annotation_package/'integridade_plano.json', {'files': {
        name: fingerprint(annotation_package/name) for name in ['amostras.gpkg', 'plano_referencia.json']}})
    m = canopy_run(c, 'main'); d = Path(m['products_root'])
    mask = {**m, 'analysis_version': 'baseline_h3', 'mask_context': str(d/'copa_baseline_h3_contexto.tif'),
        'mask_measurement': str(d/'copa_baseline_h3_medicao.tif'), 'valid_domain': str(d/'dominio_valido.tif'),
        'observation': str(d/'observabilidade.tif'), 'uncertainty': str(d/'incerteza_h3.tif'),
        'patches': str(d/'mascaras_manchas.gpkg'), 'observed_layer': 'suporte_observado',
        'measurement_layer': 'baseline_h3_medicao', 'context_layer': 'baseline_h3_contexto'}
    mr = read_json(Path(m['manifest']))
    atomic_write_json(c.paths.project_root/'docs/manifesto_etapa06.json', {'artifacts': [
        fingerprint(Path(p)) for p in [*mr['outputs'], m['manifest']]]})
    s = read_json(c.paths.state_file)
    s['etapas']['06'] = {'nome': 'mascara', 'status': 'concluida', 'artefatos': []}
    s['mascara_copa_piloto'] = {'principal': mask}
    atomic_write_json(c.paths.state_file, s)
    u = segmentation_run(c, 'main'); g = Path(u['products_root'])/'unidades_multiescala.gpkg'
    ur = read_json(Path(u['manifest']))
    atomic_write_json(c.paths.project_root/'docs/manifesto_etapa07.json', {'artifacts': [
        fingerprint(Path(p)) for p in [*ur['outputs'], u['manifest']]]})
    s = read_json(c.paths.state_file)
    s['etapas']['07'] = {'nome': 'unidades', 'status': 'concluida', 'artefatos': []}
    s['segmentacao_piloto'] = {'principal': {**u, 'geopackage': str(g),
        'B_unavailable_reason': 'non_unique_branched_axis', 'scales': {str(scale): {
            'grid_layer': f'grade_{scale}m', 'influence_layer': f'influencia_{scale}m'} for scale in [25, 50, 100]}}}
    atomic_write_json(c.paths.state_file, s)
    original = [fingerprint(p) for p in c.paths.data_root.rglob('*.laz')]
    labels = fingerprint(annotation_package/'trabalho/anotacoes.gpkg')
    result = indicators_run(c, 'main')
    table = gpd.read_parquet(Path(result['products_root'])/'indicadores.parquet')
    assert len(table) == 3 and table.crs.to_epsg() == 31983 and not table.eligible_B.any()
    assert table.I2.isna().all() and table.I3_local_m.isna().all()
    csv = pd.read_csv(Path(result['products_root'])/'indicadores.csv')
    assert csv.measurement_id.tolist() == table.measurement_id.tolist()
    assert not read_json(Path(result['report']))['rankings_computed']
    cached = indicators_run(c, 'main')
    assert cached['cache_hit'] and cached['report'] == result['report']
    assert [fingerprint(Path(p['path'])) for p in original] == original
    assert fingerprint(annotation_package/'trabalho/anotacoes.gpkg') == labels
    with g.open('ab') as handle:
        handle.write(b'changed-after-freeze')
    with pytest.raises(ValueError, match='Unidades congeladas mudaram'):
        indicators_run(c, 'main')
