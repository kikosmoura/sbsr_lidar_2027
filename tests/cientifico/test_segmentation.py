from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, box

from test_terrain import terrain_inputs
from test_reference import annotation_package
from sbsr_lidar.canopy import canopy_run
from sbsr_lidar.corridor_axis import boundary_sites, extract_axis
from sbsr_lidar.domain import Domain
from sbsr_lidar.longitudinal import (branch_sequences, branch_stations, longitudinal_units,
                                    transverse_section)
from sbsr_lidar.segmentation import build_units, frozen_mask, segmentation_run
from sbsr_lidar.spatial_units import (partition_check, regular_grid, support_correspondence)
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json
from sbsr_lidar.terrain import terrain_run


def domain(config, geometry):
    tiles = gpd.GeoDataFrame({'quadricula': ['3313-333', '3313-324']},
        geometry=[box(-100, -100, 60, 300), box(60, -100, 400, 300)], crs=config.grid.epsg)
    return Domain('main', 'SYNTHETIC', geometry, geometry, geometry.buffer(10), tiles,
                  {'measurement_is_official_polygon': True})


def branch(axis):
    return {'branch_id': 'P001_R01', 'part_id': 'P001', 'length_m': axis.length, 'geometry': axis}


def test_curved_variable_width_grid_area_observation_and_stable_ids(config):
    polygon = LineString([(5, 5), (70, 5), (100, 40), (110, 100)]).buffer(8).union(box(50, -10, 80, 25))
    d = domain(config, polygon)
    observed = polygon.difference(box(40, -50, 50, 150))
    uncertain = polygon.intersection(box(0, 0, 20, 100))
    for scale in [25., 50., 100.]:
        units = regular_grid(config, d, observed, uncertain, scale)
        assert partition_check(units, polygon, 1e-6)['ok']
        assert np.isclose(units.area_observed_m2.sum(), observed.area)
        assert units.unit_id.tolist() == regular_grid(config, d, observed, uncertain, scale).unit_id.tolist()
        assert units.unit_id.is_unique
        assert units.fraction_observed.between(0, 1+1e-12).all()


def test_disconnected_fragments_in_same_grid_cell_remain_separate(config):
    polygon = shapely.union_all([box(0, 0, 100, 10), box(0, 40, 100, 50), box(90, 0, 100, 50)])
    d = domain(config, polygon)
    units = regular_grid(config, d, polygon, Polygon(), 50.)
    fragments = units.loc[(units.grid_x == 0) & (units.grid_y == 0)]
    assert len(fragments) == 2 and fragments.fragment_number.tolist() == [1, 2]
    assert not fragments.geometry.iloc[0].intersects(fragments.geometry.iloc[1])
    assert partition_check(units, polygon, 1e-6)['ok']


def test_multipart_residual_not_attached_to_distant_part(config):
    polygon = MultiPolygon([box(0, 0, 120, 10), box(200, 0, 202, 2)])
    layers, tables, summary = build_units(config, domain(config, polygon), polygon, Polygon(), Polygon())
    assert len(layers['partes']) == 2
    assert layers['partes'].axis_accepted.tolist() == [True, False]
    assert all(row.geometry.bounds[2] < 200 for row in layers['segmentos_50m'].itertuples())
    small = layers['grade_50m'].loc[lambda g: g.part_id.str.endswith('P002')]
    assert small.residual_below_minimum_area.all() and small.area_effective_m2.sum() == 4
    assert summary['grid_fallback_area_m2'] == 4


def test_bifurcation_is_reviewable_and_falls_back_to_grid(config):
    polygon = shapely.union_all([box(0, 0, 160, 12), box(74, 0, 86, 100)])
    layers, tables, summary = build_units(config, domain(config, polygon), polygon, Polygon(), Polygon())
    assert len(layers['juncoes']) > 0 and not layers['eixos_candidatos'].axis_accepted.any()
    assert not summary['longitudinal_geometry_available']
    assert layers['segmentos_50m'].empty
    assert summary['grid_fallback_area_m2'] == polygon.area
    assert all(qc['ok'] for qc in summary['partitions'].values())


def test_curved_narrow_axis_and_variable_width_are_retained(config):
    path = LineString([(0, 0), (60, 0), (100, 30), (130, 90)])
    polygon = path.buffer(5, cap_style='flat', join_style='round')
    rows, removed, junctions, review = extract_axis(polygon, 'P001', config.segmentation)
    assert review['axis_accepted'] and len(rows) == 1
    assert rows[0]['length_m'] > 150 and polygon.covers(rows[0]['geometry'])
    assert rows[0]['geometry'].hausdorff_distance(path) < 12
    varied = Polygon([(0, -4), (120, -7), (120, 7), (0, 4)])
    rows, _, _, review = extract_axis(varied, 'P002', config.segmentation)
    assert review['axis_accepted'] and rows[0]['aspect_ratio'] > 5


def test_full_width_sections_preserve_unknown_support(config):
    p = box(0, -5, 120, 5)
    b = branch(LineString([(0, 0), (120, 0)]))
    stations = branch_stations(config, b, p, box(0, -5, 120, 3), Polygon(), Polygon())
    assert all(s['state'] == 'unknown_support' for s in stations)
    assert all(np.isclose(s['fraction_width_observed'], .8) for s in stations)
    assert not any(q['gap_id'] for q in branch_sequences(stations, b))


def test_gaps_computed_before_cuts_with_local_censor_and_neighbor_links(config):
    p = box(0, -5, 120, 5)
    b = branch(LineString([(0, 0), (120, 0)]))
    crown = shapely.union_all([box(0, -5, 10, 5), box(90, -5, 120, 5)])
    result = longitudinal_units(config, domain(config, p), b, p, p, crown, Polygon(), [25., 50., 100.])
    gaps = [s for s in result['sequences'] if s['gap_id']]
    assert len(gaps) == 1 and gaps[0]['length_m'] == 80
    assert not gaps[0]['left_censored'] and not gaps[0]['right_censored']
    links = [g for g in result['gap_links'] if g['scale_m'] == 50]
    assert len(links) == 2 and sum(g['intersection_length_m'] for g in links) == 80
    assert all(g['full_gap_length_m'] == 80 for g in links)
    assert links[0]['cut_at_unit_right'] and links[1]['cut_at_unit_left']
    assert any(gaps[0]['gap_id'] in n['shared_gap_ids'] for n in result['neighbors'])
    for scale, (regions, lines) in result['units'].items():
        assert partition_check(regions, p, 1e-6)['ok']
        assert np.allclose(lines.geometry.length, lines.length_m)
        assert lines.iloc[-1].short_remainder and lines.length_m.sum() == 120
    regions25, _ = result['units'][25.]
    regions100, _ = result['units'][100.]
    mapping = pd.DataFrame(support_correspondence(regions25, regions100, p,
        family='longitudinal', scale_from=25., scale_to=100.))
    assert np.allclose(mapping.groupby('unit_from').fraction_from.sum(), 1)
    assert np.isclose(mapping.intersection_area_m2.sum(), p.area)


def test_unknown_interval_splits_gap_and_censors_both_sides(config):
    p = box(0, -5, 120, 5)
    b = branch(LineString([(0, 0), (120, 0)]))
    observed = p.difference(box(50, -10, 60, 10))
    sequences = branch_sequences(branch_stations(config, b, p, observed, Polygon(), Polygon()), b)
    assert [s['state'] for s in sequences] == ['candidate_gap', 'unknown_support', 'candidate_gap']
    assert sequences[0]['right_censor_reason'] == sequences[2]['left_censor_reason'] == 'unknown_support'
    assert sequences[0]['left_censor_reason'] == sequences[2]['right_censor_reason'] == 'axis_endpoint'
    assert sum(s['length_m'] for s in sequences) == b['length_m']


def test_zero_presence_threshold_requires_positive_canopy(config):
    c = config.model_copy(update={'segmentation': config.segmentation.model_copy(update={'section_cover_threshold': 0.})})
    p = box(0, -5, 30, 5)
    rows = branch_stations(c, branch(LineString([(0, 0), (30, 0)])), p, p, Polygon(), Polygon())
    assert all(s['state'] == 'candidate_gap' for s in rows)


def test_transverse_section_does_not_jump_to_distant_arm():
    polygon = shapely.union_all([box(0, -2, 100, 2), box(0, 20, 100, 24), box(95, -2, 100, 24)])
    section, pieces = transverse_section(LineString([(0, 0), (90, 0)]), 40, polygon, 1.)
    assert pieces == 2 and section.length == 4


def test_segment_crosses_tiles_and_keeps_true_short_remainder(config):
    polygon = box(0, -5, 120, 5)
    result = longitudinal_units(config, domain(config, polygon), branch(LineString([(0, 0), (120, 0)])),
                                polygon, polygon, Polygon(), Polygon(), [100.])
    regions, lines = result['units'][100.]
    assert lines.length_m.tolist() == [100., 20.]
    assert regions.iloc[0].tiles == '3313-324,3313-333'
    assert not lines.iloc[0].short_remainder and lines.iloc[1].short_remainder


def test_resource_limits_fail_without_unbounded_expansion(config):
    with pytest.raises(ValueError, match='orçamento'):
        boundary_sites(box(0, 0, 100, 100), 1., 10)
    c = config.model_copy(update={'segmentation': config.segmentation.model_copy(update={'maximum_grid_cells_per_scale': 1})})
    with pytest.raises(ValueError, match='orçamento'):
        regular_grid(c, domain(c, box(0, 0, 120, 10)), Polygon(), Polygon(), 25.)


def test_frozen_mask_native_io_cache_stale_inputs_and_preservation(terrain_inputs, annotation_package):
    c = terrain_inputs
    sources = {case: terrain_run(c, case, requested_method='tin') for case in ['main', 'adversarial']}
    state = read_json(c.paths.state_file)
    state['etapas']['04']['status'] = 'concluida'
    state['etapas']['05'] = {'nome': 'referencia', 'status': 'concluida', 'artefatos': []}
    state['terreno_altura_piloto'] = {'principal': sources['main'], 'adverso': sources['adversarial']}
    state['referencia_anotacao'] = {'package': str(annotation_package)}
    atomic_write_json(c.paths.state_file, state)
    atomic_write_json(annotation_package/'integridade_plano.json', {'files': {
        name: fingerprint(annotation_package/name) for name in ['amostras.gpkg', 'plano_referencia.json']}})
    canopy = canopy_run(c, 'main')
    r = read_json(Path(canopy['report']))
    d = Path(canopy['products_root'])
    selected = {**canopy, 'analysis_version': r['analysis_version'],
        'mask_context': str(d/'copa_baseline_h3_contexto.tif'), 'mask_measurement': str(d/'copa_baseline_h3_medicao.tif'),
        'valid_domain': str(d/'dominio_valido.tif'), 'observation': str(d/'observabilidade.tif'),
        'uncertainty': str(d/'incerteza_h3.tif'), 'patches': str(d/'mascaras_manchas.gpkg'),
        'observed_layer': 'suporte_observado', 'measurement_layer': 'baseline_h3_medicao'}
    old = read_json(Path(canopy['manifest']))
    aggregate = {'artifacts': [fingerprint(Path(p)) for p in [*old['outputs'], canopy['manifest']]]}
    atomic_write_json(c.paths.project_root/'docs/manifesto_etapa06.json', aggregate)
    state = read_json(c.paths.state_file)
    state['etapas']['06'] = {'nome': 'mascara', 'status': 'concluida', 'artefatos': []}
    state['mascara_copa_piloto'] = {'principal': selected}
    atomic_write_json(c.paths.state_file, state)
    before = [fingerprint(p) for p in c.paths.data_root.rglob('*.laz')]
    annotation_before = fingerprint(annotation_package/'trabalho/anotacoes.gpkg')
    result = segmentation_run(c, 'main')
    report = read_json(Path(result['report']))
    assert all(x['ok'] for x in report['summary']['partitions'].values())
    assert not report['summary']['longitudinal_geometry_available'] # 7x7 m square, no forced route
    gpkg = Path(result['products_root'])/'unidades_multiescala.gpkg'
    assert gpd.read_file(gpkg, layer='segmentos_50m').empty
    assert gpd.read_file(gpkg, layer='grade_50m').area_effective_m2.sum() == 49
    cached = segmentation_run(c, 'main')
    assert cached['cache_hit'] and cached['report'] == result['report']
    assert [fingerprint(Path(p['path'])) for p in before] == before
    assert fingerprint(annotation_package/'trabalho/anotacoes.gpkg') == annotation_before
    Path(selected['uncertainty']).write_bytes(b'corrupted-after-freeze')
    with pytest.raises(ValueError, match='máscara congelada mudou'):
        frozen_mask(c, read_json(c.paths.state_file), 'main')
