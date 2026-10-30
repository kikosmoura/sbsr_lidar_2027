"""Seções de largura completa, sequências no ramo e partições de influência."""
from __future__ import annotations

import math

import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import substring

from .spatial_units import frame, polygonal, support_fields, tile_codes


def line_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [p for g in geometry.geoms for p in line_parts(g)]
    return []


def transverse_section(axis, position, polygon, half_window):
    before = axis.interpolate(max(0., position-half_window))
    after = axis.interpolate(min(axis.length, position+half_window))
    direction = np.array([after.x-before.x, after.y-before.y])
    if np.linalg.norm(direction) <= 1e-10:
        return LineString(), 0
    normal = np.array([-direction[1], direction[0]])/np.linalg.norm(direction)
    center = axis.interpolate(position)
    x0, y0, x1, y1 = polygon.bounds
    reach = math.hypot(x1-x0, y1-y0)+1.
    point = np.array([center.x, center.y])
    intersection = LineString([point-reach*normal, point+reach*normal]).intersection(polygon)
    components = line_parts(intersection)
    attached = [g for g in components if g.distance(center) < 1e-6]
    if len(attached) != 1:
        return LineString(), len(components)
    # Não somar largura de outro braço separado, mesmo na mesma parte.
    return attached[0], len(components)


def branch_stations(config, branch, polygon, observed, crown, uncertain, *, domain_cut=False):
    axis = branch['geometry']
    n = math.ceil(axis.length/config.segmentation.station_spacing_m)
    if n > config.segmentation.maximum_stations_per_part:
        raise ValueError('Estações excedem orçamento do piloto')
    rows = []
    for i in range(n):
        start = i*config.segmentation.station_spacing_m
        end = min(axis.length, start+config.segmentation.station_spacing_m)
        position = (start+end)/2
        section, pieces = transverse_section(axis, position, polygon, config.segmentation.tangent_half_window_m)
        width = section.length
        observed_width = section.intersection(observed).length
        candidate_width = section.intersection(crown).length
        uncertain_width = section.intersection(uncertain).length
        observable = width > 0 and observed_width/width >= config.support.minimum_observed_fraction
        cover = candidate_width/observed_width if observed_width > 0 else None
        threshold = config.segmentation.section_cover_threshold
        present = (cover > 0 if threshold == 0 else cover >= threshold) if observable else None
        state = 'unknown_support' if present is None else ('candidate_present' if present else 'candidate_gap')
        center = axis.interpolate(position)
        rows.append({'station_id': f"{branch['branch_id']}_E{i:06d}",
            'part_id': branch['part_id'], 'branch_id': branch['branch_id'], 'station_index': i,
            'start_m': start, 'end_m': end, 'position_m': position, 'interval_length_m': end-start,
            'x': center.x, 'y': center.y, 'section_width_m': width, 'observed_width_m': observed_width,
            'fraction_width_observed': observed_width/width if width > 0 else None,
            'candidate_width_m': candidate_width, 'fraction_observed_width_candidate': cover,
            'classification_uncertain_width_m': uncertain_width, 'line_components_in_part': pieces,
            'full_section_observable': observable, 'state': state, 'domain_cut': domain_cut,
            'mask_validated': False, 'geometry': section})
    return rows


def branch_sequences(stations, branch):
    """Run-length encoding ANTES dos cortes de escala, incluindo desconhecidos."""
    groups = []
    for station in stations:
        if groups and groups[-1]['state'] == station['state']:
            groups[-1]['last'] = station['station_index']
            groups[-1]['end_m'] = station['end_m']
        else:
            groups.append({'state': station['state'], 'first': station['station_index'],
                           'last': station['station_index'], 'start_m': station['start_m'],
                           'end_m': station['end_m']})
    rows = []
    gap_index = 0
    for i, group in enumerate(groups):
        state = group['state']
        is_gap = state == 'candidate_gap'
        if is_gap:
            gap_index += 1
        left = 'axis_endpoint' if i == 0 else ('unknown_support' if groups[i-1]['state'] == 'unknown_support' else '')
        right = 'axis_endpoint' if i == len(groups)-1 else ('unknown_support' if groups[i+1]['state'] == 'unknown_support' else '')
        rows.append({'sequence_id': f"{branch['branch_id']}_Q{i:05d}",
            'gap_id': f"{branch['branch_id']}_GAP{gap_index:04d}" if is_gap else None,
            'part_id': branch['part_id'], 'branch_id': branch['branch_id'],
            **{k: v for k, v in group.items() if k not in ['first', 'last']},
            'length_m': group['end_m']-group['start_m'],
            'left_censored': bool(left), 'right_censored': bool(right),
            'left_censor_reason': left, 'right_censor_reason': right,
            'domain_truncated': bool(stations[0]['domain_cut']),
            'gap_semantics': 'candidate_no_crown_conditional_on_unvalidated_mask' if is_gap else state,
            'geometry': substring(branch['geometry'], group['start_m'], group['end_m'])})
    return rows


def station_influence(stations, polygon):
    """Voronoi de pontos de estação, por parte; sem buffers estreitos ou por folha."""
    if not stations:
        return []
    if len(stations) == 1:
        return [polygon]
    xy = np.array([[s['x'], s['y']] for s in stations])
    tree = cKDTree(xy)
    cells = shapely.voronoi_polygons(MultiPoint(xy), extend_to=polygon.envelope)
    result = [Polygon() for _ in stations]
    assigned = set()
    for cell in cells.geoms:
        point = cell.representative_point()
        index = int(tree.query([point.x, point.y])[1])
        if index in assigned:
            raise ValueError('Atribuição de Voronoi de estação não é unívoca')
        assigned.add(index)
        result[index] = polygonal(cell.intersection(polygon))
    if len(assigned) != len(stations):
        raise ValueError('Estações não possuem correspondência completa com regiões')
    return result


def longitudinal_units(config, domain, branch, polygon, observed, crown, uncertain, scales):
    stations = branch_stations(config, branch, polygon, observed, crown, uncertain,
                              domain_cut=not domain.metadata['measurement_is_official_polygon'])
    sequences = branch_sequences(stations, branch)
    influences = station_influence(stations, polygon)
    by_scale = {}
    gap_links = []
    neighbors = []
    station_cells = [{k: s[k] for k in ['station_id', 'branch_id', 'part_id', 'start_m', 'end_m', 'position_m']}
                     | {'geometry': geom} for s, geom in zip(stations, influences)]
    for scale in scales:
        # Mantém estações/gaps independentes dos segmentos; cada região pertence
        # ao segmento cujo intervalo contém o centro da estação.
        n = math.ceil(branch['length_m']/scale)
        rows, lines = [], []
        for i in range(n):
            start, end = i*scale, min((i+1)*scale, branch['length_m'])
            selected = [k for k, s in enumerate(stations) if start <= s['position_m'] < end]
            geom = polygonal(shapely.union_all([influences[k] for k in selected]))
            observed_length = sum(max(0., min(end, s['end_m'])-max(start, s['start_m']))
                                  for s in stations if s['full_section_observable'])
            unit_id = f"{branch['branch_id']}_L{scale:g}_S{i:05d}"
            row = {'unit_id': unit_id, 'corridor_id': domain.corridor_id, 'family': 'longitudinal',
                'part_id': branch['part_id'], 'branch_id': branch['branch_id'],
                'nominal_size_m': scale, 'start_m': start, 'end_m': end, 'length_m': end-start,
                'short_remainder': end-start < scale-1e-8,
                'endpoint_region': i == 0 or i == n-1, 'domain_truncated': stations[0]['domain_cut'],
                'length_full_width_observable_m': observed_length,
                'fraction_length_full_width_observable': observed_length/(end-start),
                'axis_accepted_geometrically': True, 'mask_validated': False,
                **support_fields(geom, observed, uncertain, config), 'geometry': geom}
            row['eligible_longitudinal_observation'] = row['eligible_area_observation'] and observed_length/(end-start) >= config.support.minimum_observed_fraction
            row['tiles'] = tile_codes(geom, domain.nominal_tiles)
            rows.append(row)
            lines.append({**row, 'geometry': substring(branch['geometry'], start, end)})
            for sequence in sequences:
                if sequence['gap_id'] is None:
                    continue
                a, b = max(start, sequence['start_m']), min(end, sequence['end_m'])
                if b > a:
                    gap_links.append({'gap_id': sequence['gap_id'], 'unit_id': unit_id,
                        'branch_id': branch['branch_id'], 'scale_m': scale,
                        'intersection_start_m': a, 'intersection_end_m': b, 'intersection_length_m': b-a,
                        'full_gap_length_m': sequence['length_m'],
                        'cut_at_unit_left': a > sequence['start_m']+1e-8,
                        'cut_at_unit_right': b < sequence['end_m']-1e-8,
                        'branch_gap_left_censored': sequence['left_censored'],
                        'branch_gap_right_censored': sequence['right_censored']})
        for a, b in zip(rows, rows[1:]):
            shared_gaps = sorted({g['gap_id'] for g in gap_links if g['unit_id'] == a['unit_id']}
                                 & {g['gap_id'] for g in gap_links if g['unit_id'] == b['unit_id']})
            neighbors.append({'branch_id': branch['branch_id'], 'scale_m': scale,
                              'unit_left': a['unit_id'], 'unit_right': b['unit_id'],
                              'position_m': a['end_m'], 'shared_gap_ids': ','.join(shared_gaps)})
        by_scale[scale] = (frame(rows, config.grid.epsg), frame(lines, config.grid.epsg))
    return {'stations': stations, 'sequences': sequences, 'station_cells': station_cells,
            'units': by_scale, 'gap_links': gap_links, 'neighbors': neighbors}
