"""Etapa 07: unidades de suporte e geometria longitudinal, sem calcular rankings."""
from __future__ import annotations

import os
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import pyogrio
import rasterio
import shapely
from rasterio.features import shapes
from scipy.spatial import QhullError
from shapely.geometry import Polygon, shape

from .corridor_axis import extract_axis
from .doctor import existing_parent
from .domain import build_domain
from .environment import environment_snapshot, source_digest
from .longitudinal import longitudinal_units
from .preparation import _input_fingerprints
from .runtime import Run, exclusive_lock
from .spatial_units import (frame, partition_check, polygon_parts, polygonal, regular_grid,
                            support_correspondence, stable_geometry_id)
from .storage import atomic_write_json, cache_key, fingerprint, load_cache, read_json, save_cache


def frozen_mask(config, state, case):
    if state.get('etapas', {}).get('06', {}).get('status') != 'concluida':
        raise ValueError('Concluir etapa 06 antes de construir unidades')
    selected = state['mascara_copa_piloto']['principal' if case == 'main' else 'adverso']
    aggregate_path = config.paths.project_root/'docs/manifesto_etapa06.json'
    aggregate = read_json(aggregate_path)
    inventory = {p['path']: p for p in aggregate['artifacts']}
    parent = read_json(Path(selected['manifest']))
    parent_inputs = {p['path']: p for p in parent['inputs']}
    vector_inputs = _input_fingerprints(config)
    if any(parent_inputs.get(p['path']) != p for p in vector_inputs):
        raise ValueError('Vetores/protocolo mudaram desde a máscara congelada')
    paths = [Path(selected[k]) for k in ['manifest', 'report', 'mask_context', 'mask_measurement',
              'valid_domain', 'observation', 'uncertainty', 'patches']]
    records = [fingerprint(p) for p in paths]
    if any(inventory.get(p['path']) != p for p in records):
        raise ValueError('Produto da máscara congelada mudou; rever etapa 06 antes de segmentar')
    return selected, [*vector_inputs, *records, fingerprint(aggregate_path)]


def mask_geometry(path, predicate, polygon):
    with rasterio.open(path) as ds:
        values = ds.read(1)
        mask = predicate(values)
        parts = [shape(g) for g, _ in shapes(mask.astype('uint8'), mask=mask, transform=ds.transform)]
    return polygonal(shapely.union_all(parts).intersection(polygon))


def build_units(config, domain, observed, crown, uncertain, event=lambda *a, **k: None):
    scales = sorted(set([config.segmentation.length_m, *config.sensitivity.lengths_m]))
    grids = {s: regular_grid(config, domain, observed, uncertain, s) for s in scales}
    candidates, pruned, junctions, reviews, parts_rows = [], [], [], [], []
    accepted_parts = []
    station_rows, sequence_rows, influence_rows = [], [], []
    gap_links, neighbors = [], []
    regions_by_scale = {s: [] for s in scales}
    lines_by_scale = {s: [] for s in scales}
    for number, polygon in enumerate(polygon_parts(domain.measurement), 1):
        part_id = f'{domain.corridor_id}_P{number:03d}'
        try:
            branches, removed, joints, review = extract_axis(polygon, part_id, config.segmentation)
        except QhullError:
            branches, removed, joints = [], [], []
            review = {'part_id': part_id, 'axis_accepted': False,
                      'reason': 'Voronoi_degenerate_use_grid', 'retained_branches': 0,
                      'pruned_terminal_branches': 0, 'junctions': 0}
        reviews.append(review)
        candidates.extend(branches)
        pruned.extend({**r, 'part_id': part_id} for r in removed)
        junctions.extend(joints)
        parts_rows.append({'part_id': part_id, 'corridor_id': domain.corridor_id,
                           'axis_accepted': review['axis_accepted'], 'reason': review['reason'],
                           'area_m2': polygon.area, 'geometry': polygon})
        event('axis_review', **review)
        if not review['axis_accepted']:
            continue
        accepted_parts.append(polygon)
        products = longitudinal_units(config, domain, branches[0], polygon, observed, crown, uncertain, scales)
        station_rows.extend(products['stations'])
        sequence_rows.extend(products['sequences'])
        influence_rows.extend(products['station_cells'])
        gap_links.extend(products['gap_links'])
        neighbors.extend(products['neighbors'])
        for s, (regions, lines) in products['units'].items():
            regions_by_scale[s].extend(regions.to_dict('records'))
            lines_by_scale[s].extend(lines.to_dict('records'))
    epsg = config.grid.epsg
    regions = {s: frame(rows, epsg, ['unit_id', 'part_id', 'nominal_size_m']) for s, rows in regions_by_scale.items()}
    lines = {s: frame(rows, epsg, ['unit_id', 'part_id', 'start_m', 'end_m', 'length_m']) for s, rows in lines_by_scale.items()}
    valid_target = polygonal(shapely.union_all(accepted_parts))
    layers = {'partes': frame(parts_rows, epsg),
        'eixos_candidatos': frame(candidates, epsg, ['branch_id', 'part_id', 'axis_accepted']),
        'ramos_podados': frame(pruned, epsg, ['branch_id', 'part_id', 'reason']),
        'juncoes': frame(junctions, epsg, ['junction_id', 'part_id', 'degree']),
        'secoes': frame(station_rows, epsg, ['station_id', 'part_id', 'branch_id', 'state']),
        'sequencias_ramo': frame(sequence_rows, epsg, ['sequence_id', 'gap_id', 'branch_id', 'state']),
        'influencia_estacoes': frame(influence_rows, epsg, ['station_id', 'part_id', 'branch_id'])}
    junction_regions = []
    for part in parts_rows:
        zones = [j['geometry'].buffer(j['radius_m']).intersection(part['geometry'])
                 for j in junctions if j['part_id'] == part['part_id']]
        for zone in polygon_parts(shapely.union_all(zones)):
            junction_regions.append({'junction_region_id': part['part_id']+'_JZ'+stable_geometry_id(zone),
                'part_id': part['part_id'], 'role': 'diagnostic_only_part_excluded_from_longitudinal',
                'area_m2': zone.area, 'geometry': zone})
    layers['regioes_juncao'] = frame(junction_regions, epsg, ['junction_region_id', 'part_id', 'role'])
    partitions = {}
    correspondence = []
    for s in scales:
        layers[f'grade_{s:g}m'] = grids[s]
        layers[f'influencia_{s:g}m'] = regions[s]
        layers[f'segmentos_{s:g}m'] = lines[s]
        for family, units, target in [('grid', grids[s], domain.measurement), ('longitudinal', regions[s], valid_target)]:
            qc = partition_check(units, target, config.segmentation.area_tolerance_m2)
            partitions[f'{family}_{s:g}'] = qc
            if not qc['ok']:
                raise ValueError(f'Partição viola área/geometria: {family}/{s}: {qc}')
    for i, a in enumerate(scales):
        for b in scales[i+1:]:
            for family, units in [('grid', grids), ('longitudinal', regions)]:
                correspondence.extend(support_correspondence(units[a], units[b], observed,
                    family=family, scale_from=a, scale_to=b))
    # Grade e longitudinal também se relacionam por interseção, não pelo tamanho nominal.
    for s in scales:
        correspondence.extend(support_correspondence(grids[s], regions[s], observed,
            family='grid_to_longitudinal', scale_from=s, scale_to=s))
    gap_columns = ['gap_id', 'unit_id', 'branch_id', 'scale_m', 'intersection_start_m',
        'intersection_end_m', 'intersection_length_m', 'full_gap_length_m', 'cut_at_unit_left',
        'cut_at_unit_right', 'branch_gap_left_censored', 'branch_gap_right_censored']
    neighbor_columns = ['branch_id', 'scale_m', 'unit_left', 'unit_right', 'position_m', 'shared_gap_ids']
    correspondence_columns = ['family', 'scale_from_m', 'scale_to_m', 'unit_from', 'unit_to', 'part_id',
        'intersection_area_m2', 'observed_intersection_area_m2', 'fraction_from', 'fraction_to',
        'observed_fraction_from', 'observed_fraction_to']
    tables = {'ligacoes_lacunas': pd.DataFrame(gap_links, columns=gap_columns),
              'vizinhos_segmentos': pd.DataFrame(neighbors, columns=neighbor_columns),
              'correspondencia_suporte': pd.DataFrame(correspondence, columns=correspondence_columns)}
    summary = {'scales_m': scales, 'part_reviews': reviews, 'partitions': partitions,
        'axis_accepted_area_m2': valid_target.area,
        'grid_fallback_area_m2': domain.measurement.area-valid_target.area,
        'longitudinal_geometry_available': bool(accepted_parts),
        'mask_validated': False, 'B_requires_observation_and_defensible_axis': True,
        'grids': {f'{s:g}': {'units': len(g), 'eligible_area_observation': int(g.eligible_area_observation.sum()),
                    'small_area_residuals': int(g.residual_below_minimum_area.sum()),
                    'effective_area_m2': float(g.area_effective_m2.sum()),
                    'observed_area_m2': float(g.area_observed_m2.sum())} for s, g in grids.items()},
        'longitudinal': {f'{s:g}': {'units': len(g),
            'eligible_longitudinal_observation': int(g.eligible_longitudinal_observation.sum()) if len(g) else 0,
            'short_remainders': int(g.short_remainder.sum()) if len(g) else 0} for s, g in regions.items()},
        'stations': len(station_rows),
        'station_state_counts': {k: sum(s['state'] == k for s in station_rows)
                                for k in ['candidate_present', 'candidate_gap', 'unknown_support']},
        'candidate_gaps_before_segment_cuts': sum(s['gap_id'] is not None for s in sequence_rows),
        'support_correspondence_rows': len(correspondence), 'gap_links': len(gap_links)}
    return layers, tables, summary


def write_units(path, layers, tables):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.units_', suffix='.gpkg')
    os.close(fd)
    temporary = Path(name)
    temporary.unlink()
    linear = {'eixos_candidatos', 'ramos_podados', 'secoes', 'sequencias_ramo'}
    try:
        for name, layer in layers.items():
            kind = ('Point' if name == 'juncoes' else
                    'MultiLineString' if name in linear or name.startswith('segmentos_') else 'MultiPolygon')
            pyogrio.write_dataframe(layer, temporary, layer=name, geometry_type=kind,
                                    promote_to_multi=kind.startswith('Multi'))
        for name, table in tables.items():
            pyogrio.write_dataframe(table, temporary, layer=name)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def segmentation_run(config, case, *, use_cache=True):
    if not config.paths.mount_root.is_mount():
        raise ValueError('HD externo não montado')
    if psutil.virtual_memory().available/2**30 < config.resources.max_ram_gib:
        raise ValueError('RAM abaixo do orçamento')
    for path, minimum in [(config.paths.runs_root, config.resources.min_local_free_gib),
                          (config.paths.output_root, config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free/2**30 < minimum:
            raise ValueError('Espaço abaixo da reserva configurada')
    state = read_json(config.paths.state_file)
    selected, inputs = frozen_mask(config, state, case)
    domain = build_domain(config, case)
    with exclusive_lock(config.paths.runs_root/'.segmentation.lock'):
        environment = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
        snapshot = config.model_dump(mode='json')
        snapshot['execution'] = {'case': case, 'frozen_canopy_run_id': selected['run_id'],
            'analysis_version': selected['analysis_version'],
            'axis_acceptance_policy': 'single_open_elongated_chain_geometric_QC_not_independent_validation'}
        code = source_digest()
        command = f'segment:{case}'
        key = cache_key(command=command, config=snapshot, inputs=inputs, code=code, environment=environment)
        cache_root = config.paths.runs_root/'cache'
        run = Run(config.paths.runs_root, config.paths.state_file, command, snapshot, inputs, environment, code, stage='07')
        started = time.monotonic()

        def event(name, **details):
            run.event(name, **details)
            print(f'{name}: {details}', file=sys.stderr, flush=True)

        try:
            cached = load_cache(cache_root, key) if use_cache else None
            if cached:
                outputs = [Path(p['path']) for p in cached['outputs']]
                run.finish(outputs, cache_hit=True, source_run_id=cached['source_run_id'])
                report = read_json(outputs[0])
                return {'ok': True, 'case': case, 'run_id': run.run_id, 'cache_hit': True,
                        'manifest': str(run.path/'manifest.json'), 'report': str(outputs[0]),
                        'products_root': report['products_root']}
            directory = config.paths.output_root/'etapa07'/case/run.run_id
            directory.mkdir(parents=True, exist_ok=False)
            observed = polygonal(gpd.read_file(selected['patches'], layer=selected['observed_layer']).union_all())
            crown = polygonal(gpd.read_file(selected['patches'], layer=selected['measurement_layer']).union_all())
            uncertain = mask_geometry(selected['uncertainty'], lambda a: (a != 65535) & ((a & 31) != 0), domain.measurement)
            event('units_start', case=case, frozen_mask=selected['analysis_version'])
            layers, tables, summary = build_units(config, domain, observed, crown, uncertain, event)
            overlaps = []
            corridors = gpd.read_file(config.paths.corridors)
            for row in corridors.itertuples():
                identifier = str(getattr(row, config.pilot.corridor_field))
                if identifier == domain.corridor_id:
                    continue
                geom = polygonal(row.geometry.intersection(domain.measurement))
                if geom.area > 1e-8:
                    overlaps.append({'corridor_id': domain.corridor_id, 'other_corridor_id': identifier,
                                     'area_m2': geom.area, 'policy': 'separate_corridor_domains_no_pooling', 'geometry': geom})
            layers['sobreposicoes_corredores'] = frame(overlaps, config.grid.epsg,
                ['corridor_id', 'other_corridor_id', 'area_m2'])
            gpkg = directory/'unidades_multiescala.gpkg'
            write_units(gpkg, layers, tables)
            outputs = [gpkg]
            for name, table in tables.items():
                path = directory/f'{name}.csv'
                table.to_csv(path, index=False)
                outputs.append(path)
            if any(fingerprint(Path(p['path'])) != p for p in inputs):
                raise ValueError('Entrada mudou durante segmentação; produto não aprovado')
            report = run.path/'segmentacao.json'
            text = run.path/'segmentacao.md'
            result = {'stage': '07', 'run_id': run.run_id, 'case': case, 'ok': True,
                'domain': domain.metadata, 'frozen_mask': selected,
                'observed_area_m2': observed.area, 'uncertain_area_m2': uncertain.area,
                'geometry_method': 'boundary_Voronoi_single_terminal_prune_then_graph_chains',
                'region_method': 'nearest_station_Voronoi_clipped_per_accepted_part',
                'parameters': config.segmentation.model_dump(mode='json'),
                'section_minimum_observed_fraction': config.support.minimum_observed_fraction,
                'axis_review': 'computational_geometric_QC; maps_require_inspection_before_scientific_use',
                'summary': summary, 'intercorridor_overlaps': len(overlaps),
                'products_root': str(directory), 'products': [str(p) for p in outputs],
                'elapsed_seconds': time.monotonic()-started,
                'peak_process_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'limitations': [
                    'Exploratory units; frozen candidate crown mask remains unvalidated; no new human labels or accuracy.',
                    'Branched/broad/closed/short parts fail single-chain policy and remain grid; no arbitrary route chosen.',
                    f'One terminal pruning pass only: length<={config.segmentation.terminal_spur_maximum_m:g}m and <={config.segmentation.terminal_spur_radius_factor:g}*join_radius; removed lines retained with reason.',
                    'Accepted axes have geometric QC, not cadastral/functional route validation or independent human review.',
                    f'Full-width sections require >={100*config.support.minimum_observed_fraction:g}% observation; unknown stations never become crown gaps.',
                    'Gaps are sequences on the whole branch before segment cuts; endpoints/unknown support censor gaps.',
                    'Station-point Voronoi gives disjoint whole-width regions; segment spatial boundaries are discretized by station centers.',
                    'Influence-region endpoint caps remain in area; they do not extend measured axis length.',
                    'No linking of disconnected parts; junction-rich parts rejected for longitudinal comparison; grid includes them.',
                    'Intercorridor overlaps preserved and reported; domains are not pooled as independent replicates.',
                    'Cross-scale comparisons require intersection weights/common spatial support, not Jaccard of incompatible unit IDs.',
                    'No ecological gap interpretation, structural indicator scores, ranking, or municipal expansion performed.',
                ]}
            atomic_write_json(report, result)
            lines = [f'# Unidades multiescala — {domain.corridor_id}', '',
                     f'Execução `{run.run_id}`; máscara congelada `{selected["analysis_version"]}` não validada.', '',
                     '|Escala (m)|Grade|Segmentos|Segmentos com suporte longitudinal suficiente|', '|---|---:|---:|---:|']
            for scale in summary['scales_m']:
                g, longitudinal = summary['grids'][f'{scale:g}'], summary['longitudinal'][f'{scale:g}']
                lines.append(f'|{scale:g}|{g["units"]}|{longitudinal["units"]}|{longitudinal["eligible_longitudinal_observation"]}|')
            lines += ['', '## Critérios e limitações', '']+['- '+s for s in result['limitations']]
            text.write_text('\n'.join(lines)+'\n', encoding='utf-8')
            outputs = [report, text, *outputs]
            save_cache(cache_root, key, run.run_id, outputs)
            run.finish(outputs)
            return {'ok': True, 'case': case, 'run_id': run.run_id, 'cache_hit': False,
                    'manifest': str(run.path/'manifest.json'), 'report': str(report), 'products_root': str(directory)}
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt))
            raise
