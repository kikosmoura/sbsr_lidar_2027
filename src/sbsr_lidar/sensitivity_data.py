"""Intermediários limitados ao ROI e máscaras nativas da etapa 10."""
from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import pandas as pd
import rasterio
import shapely

from .canopy_masks import observation_mask, observed_geometry, patch_layers
from .input_qc import grid_layout, write_raster
from .indicator_support import RasterSupport, UnitAssigner
from .spatial_units import regular_grid
from .terrain_inputs import check_header, load_ground, qc_mask, selected_indices
from .terrain_surface import Surface
from .storage import atomic_write_json, fingerprint, read_json


def extract_roi(config, domain, plan, directory, event):
    records = []
    total = 0
    for row in plan:
        if row['produto'] != 'MDS': continue
        code = row['quadricula']
        event('extract_MDS_ROI', tile=code)
        offset = 0
        with laspy.open(row['selected_laz'], read_evlrs=False) as reader:
            check_header(reader.header, config)
            for points in reader.chunk_iterator(config.resources.chunk_points):
                xyz = np.column_stack([points.x, points.y, points.z])
                idx = selected_indices(xyz, domain, code)
                if len(idx):
                    total += len(idx)
                    if total > config.robustness.maximum_roi_records:
                        raise ValueError('ROI excede limite de registros; reduzir domínio')
                    records.append(pd.DataFrame({'source_tile': code, 'source_point_index': offset+idx,
                        'x': xyz[idx, 0], 'y': xyz[idx, 1], 'z_absolute': xyz[idx, 2],
                        'classification': np.asarray(points.classification)[idx],
                        'return_number': np.asarray(points.return_number)[idx],
                        'number_of_returns': np.asarray(points.number_of_returns)[idx],
                        'qc_usable': qc_mask(points, config)[idx]}))
                offset += len(points)
    if not records: raise ValueError('ROI sem registros MDS')
    frame = pd.concat(records, ignore_index=True)
    if frame.duplicated(['source_tile', 'source_point_index']).any():
        raise ValueError('Identidades duplicadas após propriedade nominal')
    frame.to_parquet(directory/'registros_ROI.parquet', index=False, compression='zstd')
    ground, report = load_ground(config, domain, plan, event)
    pd.DataFrame(ground, columns=['x', 'y', 'z']).to_parquet(directory/'vertices_contexto_maximo.parquet', index=False)
    atomic_write_json(directory/'QC_ROI.json', dict(report, mds_roi_records=len(frame)))
    return frame, ground


def query_batched(surface, xy, radius, config, event):
    parts = {key: [] for key in ['tin', 'idw', 'tin_status', 'idw_status']}
    size = config.terrain.query_points
    for start in range(0, len(xy), size):
        result = surface.query(xy[start:start+size], radius)
        for key in parts: parts[key].append(result[key])
        if start % (size*10) == 0: event('surface_query', done=start, total=len(xy), radius=radius)
    return {key: np.concatenate(values) for key, values in parts.items()}


class Intermediates:
    def __init__(self, config, base, maximal, raw, ground_max, terrain_entry, directory, event):
        self.config, self.base, self.maximal = config, base, maximal
        self.raw, self.ground_max = raw, ground_max
        self.directory, self.event = directory, event
        self.ground10 = pd.read_parquet(Path(terrain_entry['products_root'])/'vertices_terreno.parquet').to_numpy()
        self.canonical_h = pd.read_parquet(Path(terrain_entry['products_root'])/'alturas_pontos.parquet')
        self.models, self.heights, self.center_valid = {}, {}, {}
        self.xy = raw[['x', 'y']].to_numpy()
        self.qc = raw.qc_usable.to_numpy()
        self.veg = raw.classification.isin(config.vegetation.classes).to_numpy()
        self.canonical_replay = None

    def model_key(self, domain, scenario):
        if scenario.expansion_m:
            return f'expansion_{scenario.expansion_m:g}'
        return f'halo_{scenario.halo_m:g}'

    def model(self, domain, scenario):
        key = self.model_key(domain, scenario)
        if key not in self.models:
            if key == 'halo_10': ground = self.ground10
            else:
                ground = self.ground10 if key == 'halo_0' else self.ground_max
                ground = ground[shapely.intersects_xy(domain.context, ground[:, 0], ground[:, 1])]
            if len(ground) > self.config.terrain.max_support_points: raise ValueError('Orçamento MDT excedido')
            self.event('build_surface', context_key=key, vertices=len(ground))
            self.models[key] = Surface(ground, self.config.terrain)
        return self.models[key]

    def point_heights(self, domain, scenario):
        key = (self.model_key(domain, scenario), scenario.radius_m)
        if key not in self.heights:
            path = self.directory/f'H_{key[0]}_r{key[1]:g}.parquet'
            checkpoint = path.with_suffix('.json')
            if path.is_file() and checkpoint.is_file() and read_json(checkpoint).get('output') == fingerprint(path):
                values = pd.read_parquet(path)
                result = {c: values[c].to_numpy() for c in values}
            else:
                result = query_batched(self.model(domain, scenario), self.xy, scenario.radius_m, self.config, self.event)
                for method in ['tin', 'idw']:
                    result[method] = self.raw.z_absolute.to_numpy()-result[method]
                    result[method][~self.qc] = np.nan
                    result[f'{method}_status'][~self.qc] = 6
                # Para o cenário congelado, usar exatamente os H já publicados (sem nova normalização).
                if key == ('halo_10', 5.):
                    index = pd.MultiIndex.from_frame(self.raw[['source_tile', 'source_point_index']])
                    old = self.canonical_h
                    dest = index.get_indexer(pd.MultiIndex.from_frame(old[['source_tile', 'source_point_index']]))
                    if np.any(dest < 0): raise ValueError('Registro canônico ausente do ROI máximo')
                    if not np.array_equal(self.raw.iloc[dest][['x', 'y', 'z_absolute']].to_numpy(), old[['x', 'y', 'z_absolute']].to_numpy()):
                        raise ValueError('Identidade canônica não reproduz XYZ')
                    finite = np.isfinite(old.h.to_numpy()) & np.isfinite(result['tin'][dest])
                    delta = float(np.max(np.abs(old.h.to_numpy()[finite]-result['tin'][dest][finite]))) if finite.any() else None
                    self.canonical_replay = {'records': len(old), 'maximum_recomputed_H_difference_m': delta,
                        'same_finite_H_support': bool(np.array_equal(np.isfinite(old.h), np.isfinite(result['tin'][dest]))),
                        'published_H_used_exactly': True}
                    if not self.canonical_replay['same_finite_H_support'] or delta is None or delta > 1e-6:
                        raise ValueError('Reconsulta do terreno congelado não reproduz alturas/suporte')
                    result['tin'][dest] = old.h.to_numpy()
                    result['tin_status'][dest] = old.terrain_status.to_numpy()
                    atomic_write_json(self.directory/'replay_alturas.json', self.canonical_replay)
                temporary = path.with_suffix('.parquet.tmp')
                pd.DataFrame(result).to_parquet(temporary, index=False, compression='zstd')
                temporary.replace(path)
                atomic_write_json(checkpoint, {'output': fingerprint(path)})
            self.heights[key] = result
        if self.canonical_replay is None and (self.directory/'replay_alturas.json').is_file():
            import json
            self.canonical_replay = json.loads((self.directory/'replay_alturas.json').read_text())
        values = self.heights[key]
        return values[scenario.method], values[f'{scenario.method}_status']

    def centers(self, domain, scenario, layout):
        key = (self.model_key(domain, scenario), scenario.radius_m, scenario.resolution_m)
        if key not in self.center_valid:
            rr, cc = np.where(layout.context_mask)
            xy = np.column_stack([layout.transform.c+(cc+.5)*layout.resolution,
                                  layout.transform.f-(rr+.5)*layout.resolution])
            value = query_batched(self.model(domain, scenario), xy, scenario.radius_m, self.config, self.event)
            self.center_valid[key] = {}
            for method in ['tin', 'idw']:
                valid = np.zeros(layout.shape, dtype=bool)
                valid[rr, cc] = value[f'{method}_status'] == 0
                self.center_valid[key][method] = valid
        return self.center_valid[key][scenario.method]


def native_mask(config, domain, scenario, intermediates, retained, mask_source, directory):
    local = config.model_copy(update={
        'grid': config.grid.model_copy(update={'resolution_m': scenario.resolution_m}),
        'vegetation': config.vegetation.model_copy(update={'minimum_height_m': scenario.height_m,
                                                         'connectivity': scenario.connectivity})})
    layout = grid_layout(local, domain)
    h, status = intermediates.point_heights(domain, scenario)
    x, y = intermediates.xy.T
    cc = np.floor((x-layout.transform.c)/layout.resolution).astype(np.int64)
    rr = np.floor((layout.transform.f-y)/layout.resolution).astype(np.int64)
    bounds = (cc >= 0) & (rr >= 0) & (cc < layout.width) & (rr < layout.height)
    cc, rr = np.clip(cc, 0, layout.width-1), np.clip(rr, 0, layout.height-1)
    inside = bounds & layout.context_mask[rr, cc] & shapely.intersects_xy(domain.context, x, y)
    sampled = retained if scenario.sampling_mode != 'height_only' else np.ones(len(h), dtype=bool)
    selected = inside & sampled
    valid_h = intermediates.qc & (status == 0) & np.isfinite(h)
    candidate = valid_h & intermediates.veg & (h >= scenario.height_m)
    counts = {}
    flat = rr*layout.width+cc
    for name, use in [('all', selected), ('usable', selected & intermediates.qc),
                      ('valid_h', selected & valid_h), ('candidate', selected & candidate)]:
        counts[name] = np.bincount(flat[use], minlength=layout.width*layout.height).reshape(layout.shape).astype('uint32')
    terrain = intermediates.centers(domain, scenario, layout)
    observation, valid = observation_mask(layout, counts, terrain)
    mask = np.full(layout.shape, 255, dtype='uint8'); mask[valid] = 0
    mask[valid & (counts['candidate'] >= config.vegetation.minimum_points_per_cell)] = 1
    if scenario.mask_version != 'baseline':
        with rasterio.open(Path(mask_source['products_root'])/'copa_refinada_h3_contexto.tif') as ds:
            if ds.transform != layout.transform or ds.shape != layout.shape: raise ValueError('Refino desalinhado')
            mask = ds.read(1)
        if not np.array_equal(mask != 255, valid): raise ValueError('Refino muda observabilidade')
        if scenario.mask_version == 'uncertainty_upper': mask[mask == 2] = 1
    observed = observed_geometry(layout, valid, domain)
    patches, _, _, summary = patch_layers(local, layout, domain, mask, 's10_'+scenario.scenario_id, scenario.height_m, valid)
    support = RasterSupport(observation, mask, np.zeros(layout.shape, dtype='uint16'), terrain, layout.transform, config.grid.epsg)
    write_raster(directory/'mascaras.tif', [observation, mask], layout, epsg=config.grid.epsg,
        dtype='uint8', nodata=255, descriptions=['observation_1_valid_2_no_MDS_3_no_H_4_QC', 'canopy_0_absence_1_candidate_2_uncertain'],
        tags={'stage': '10', 'meaning': 'native_point_occupancy_canopy_not_resampled', 'scenario': scenario.scenario_id})
    write_raster(directory/'contagens.tif', [counts[k] for k in ['all', 'usable', 'valid_h', 'candidate']],
        layout, epsg=config.grid.epsg, dtype='uint32', nodata=2**32-1,
        descriptions=['MDS_records', 'QC_usable', 'valid_H', 'candidate_records'], tags={'stage': '10'})
    patches.to_parquet(directory/'manchas_contexto.parquet', index=False)
    return {'config': local, 'domain': domain, 'scenario': scenario, 'support': support, 'observed': observed,
        'patches': patches, 'h': h, 'status': status, 'retained': retained, 'rr': rr, 'cc': cc, 'inside': inside,
        'candidate': candidate, 'counts': counts, 'summary': summary, 'directory': directory}


def unit_owners(config, domain, units_entry, raw, canonical_support, expansion=0.):
    result = {}
    for scale in [25, 50, 100]:
        if expansion:
            units = regular_grid(config, domain, domain.measurement, shapely.GeometryCollection(), scale)
            units.unit_id = units.unit_id+'__domain_plus_'+f'{expansion:g}'
        else:
            units = __import__('geopandas').read_file(units_entry['geopackage'], layer=f'grade_{scale}m')
        assigner = UnitAssigner(units, canonical_support)
        parts = []
        for start in range(0, len(raw), config.resources.chunk_points):
            values = raw.iloc[start:start+config.resources.chunk_points]
            parts.append(assigner.assign(values.x.to_numpy(), values.y.to_numpy()))
        result[scale] = (assigner.units, np.concatenate(parts))
    return result
