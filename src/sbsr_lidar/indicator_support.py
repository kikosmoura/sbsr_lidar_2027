"""Suporte congelado e agregação exata de retornos, com memória limitada."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyarrow.parquet as pq
import rasterio
import shapely
from rasterio.features import shapes
from shapely.geometry import box, shape

from .spatial_units import polygonal


@dataclass
class RasterSupport:
    observation: np.ndarray
    canopy: np.ndarray
    uncertainty: np.ndarray
    terrain_valid: np.ndarray
    transform: object
    epsg: int

    def indices(self, x, y):
        col = np.floor((x-self.transform.c)/self.transform.a).astype(np.int64)
        row = np.floor((self.transform.f-y)/(-self.transform.e)).astype(np.int64)
        inside = (col >= 0) & (row >= 0) & (row < self.observation.shape[0]) & (col < self.observation.shape[1])
        return np.clip(row, 0, self.observation.shape[0]-1), np.clip(col, 0, self.observation.shape[1]-1), inside

    def pixel(self, x, y):
        r, c, _ = self.indices(np.array([x]), np.array([y]))
        left = self.transform.c+int(c[0])*self.transform.a
        top = self.transform.f+int(r[0])*self.transform.e
        return box(left, top+self.transform.e, left+self.transform.a, top)

    def geometry(self, mask, measurement):
        pieces = [shape(g) for g, _ in shapes(mask.astype('uint8'), mask=mask, transform=self.transform)]
        return polygonal(shapely.union_all(pieces).intersection(measurement))


def read_support(mask, terrain_path):
    arrays = []
    profile = None
    for path in [mask['observation'], mask['mask_context'], mask['uncertainty'], terrain_path]:
        with rasterio.open(path) as ds:
            current = (ds.shape, ds.transform, ds.crs.to_epsg())
            if profile is not None and current != profile:
                raise ValueError('Rasters de suporte/máscara/terreno desalinhados')
            profile = current
            arrays.append(ds.read(1))
    obs, canopy, flags, terrain = arrays
    if not np.array_equal(obs == 1, canopy != 255):
        raise ValueError('Domínio da máscara congelada difere da observação')
    return RasterSupport(obs, canopy, flags, terrain == 0, profile[1], profile[2])


class UnitAssigner:
    """Um dono por ponto em cada família/escala, inclusive nas fronteiras."""
    def __init__(self, units, support):
        self.units = units.sort_values('unit_id').reset_index(drop=True)
        self.geometries = self.units.geometry.to_numpy()
        self.tree = shapely.STRtree(self.geometries)
        self.support = support
        self.boundary_ties = 0

    def assign(self, x, y, points=None):
        result = np.full(len(x), -1, dtype=np.int32)
        if not len(x) or not len(self.units):
            return result
        pairs = self.tree.query(shapely.points(x, y) if points is None else points, predicate='intersects')
        if not pairs.shape[1]:
            return result
        order = np.lexsort((pairs[1], pairs[0]))
        point_ids, owners = pairs[:, order]
        first = np.r_[True, point_ids[1:] != point_ids[:-1]]
        result[point_ids[first]] = owners[first]
        unique, counts = np.unique(point_ids, return_counts=True)
        tied = unique[counts > 1]
        self.boundary_ties += len(tied)
        # Preferir a maior interseção da unidade com o pixel semiaberto do ponto;
        # evita atribuir altura de uma célula de copa a unidade que apenas a toca.
        for p in tied:
            a = np.searchsorted(point_ids, p)
            b = np.searchsorted(point_ids, p, side='right')
            candidates = owners[a:b]
            pixel = self.support.pixel(x[p], y[p])
            areas = [self.geometries[c].intersection(pixel).area for c in candidates]
            result[p] = candidates[int(np.argmax(areas))]
        return result


POINT_COUNTS = ['n_mds_records', 'n_records_QC_usable', 'n_records_valid_H', 'n_records_common_valid_H',
                'n_candidate_class_valid_H', 'n_vegetation_records', 'n_height_extreme_warning',
                'n_vegetation_height_extreme_warning']
CELL_COUNTS = ['n_cells_center', 'n_cells_observed_center', 'n_cells_canopy_center',
               'n_cells_valid_terrain_center', 'n_cells_no_MDS_center', 'n_cells_no_terrain_or_H_center',
               'n_cells_only_QC_excluded_center', 'n_cells_no_context_center', 'n_cells_uncertain_center']


def aggregate_returns(config, height_path, groups, support, measurement, crown, event=lambda *a, **k: None, *, assignment_support=None, observation_geometry=None):
    pools = {}
    for name, units in groups.items():
        assigner = UnitAssigner(units, support if assignment_support is None else assignment_support)
        pools[name] = {'assigner': assigner,
            'counts': {c: np.zeros(len(units), dtype=np.int64) for c in POINT_COUNTS+CELL_COUNTS},
            'heights': [[] for _ in range(len(units))]}
    shapely.prepare(measurement)
    shapely.prepare(crown)
    if observation_geometry is not None:
        shapely.prepare(observation_geometry)
    total, in_measurement, retained_heights = 0, 0, 0
    columns = ['x', 'y', 'h', 'classification', 'terrain_status', 'qc_flags']
    for batch_index, batch in enumerate(pq.ParquetFile(height_path).iter_batches(
            batch_size=config.indicators.batch_records, columns=columns)):
        d = batch.to_pandas()
        total += len(d)
        selected = shapely.intersects_xy(measurement, d.x.to_numpy(), d.y.to_numpy())
        d = d.loc[selected]
        in_measurement += len(d)
        if d.empty:
            continue
        x, y, h = d.x.to_numpy(), d.y.to_numpy(), d.h.to_numpy()
        points = shapely.points(x, y)
        rr, cc, inside = support.indices(x, y)
        obs = inside & (support.observation[rr, cc] == 1)
        if observation_geometry is not None:
            obs &= shapely.intersects_xy(observation_geometry, x, y)
        qc = (d.qc_flags.to_numpy() & 2) == 0
        valid = qc & np.isfinite(h) & d.terrain_status.eq(0).to_numpy()
        candidate = valid & d.classification.isin(config.vegetation.classes).to_numpy() & (h >= config.vegetation.minimum_height_m)
        vegetation = candidate & obs & (support.canopy[rr, cc] == 1)
        vegetation &= shapely.intersects_xy(crown, x, y)
        extreme = (d.qc_flags.to_numpy() & 16) != 0
        masks = [np.ones(len(d), dtype=bool), qc, valid, valid & obs, candidate,
                 vegetation, extreme, vegetation & extreme]
        for name, pool in pools.items():
            owner = pool['assigner'].assign(x, y, points)
            for key, use in zip(POINT_COUNTS, masks):
                ids = owner[use & (owner >= 0)]
                pool['counts'][key] += np.bincount(ids, minlength=len(pool['assigner'].units))
            use = vegetation & (owner >= 0)
            retained_heights += int(use.sum())
            if retained_heights > config.indicators.maximum_stored_height_values:
                raise ValueError('Quantis exatos excedem orçamento de alturas; reduzir escopo do piloto')
            ids = owner[use]
            order = np.argsort(ids, kind='stable')
            ids, values = ids[order], h[use][order]
            boundaries = np.r_[0, np.flatnonzero(np.diff(ids))+1, len(ids)]
            for a, b in zip(boundaries, boundaries[1:]):
                if b > a:
                    pool['heights'][ids[a]].append(values[a:b].copy())
        if batch_index % 8 == 0:
            event('indicator_point_batch', batch=batch_index, records_read=total, measurement_records=in_measurement)
    # Contagens de células são por centro e distintas das áreas vetoriais exatas.
    rr, cc = np.indices(support.observation.shape)
    x = support.transform.c+(cc.ravel()+.5)*support.transform.a
    y = support.transform.f+(rr.ravel()+.5)*support.transform.e
    selected = shapely.intersects_xy(measurement, x, y)
    indices = np.flatnonzero(selected)
    for start in range(0, len(indices), config.indicators.batch_records):
        idx = indices[start:start+config.indicators.batch_records]
        xx, yy = x[idx], y[idx]
        o, c, u = (a.ravel()[idx] for a in [support.observation, support.canopy, support.uncertainty])
        common = np.ones(len(idx), dtype=bool) if observation_geometry is None else shapely.intersects_xy(observation_geometry, xx, yy)
        masks = [np.ones(len(idx), dtype=bool), (o == 1) & common, (c == 1) & common, support.terrain_valid.ravel()[idx],
                 o == 2, o == 3, o == 4, o == 255, (u != 65535) & ((u & 31) != 0)]
        points = shapely.points(xx, yy)
        for pool in pools.values():
            owner = pool['assigner'].assign(xx, yy, points)
            for key, use in zip(CELL_COUNTS, masks):
                pool['counts'][key] += np.bincount(owner[use & (owner >= 0)], minlength=len(pool['assigner'].units))
    for pool in pools.values():
        pool['heights'] = [np.concatenate(values) if values else np.empty(0, dtype='float64') for values in pool['heights']]
    return pools, {'source_records_read': total, 'records_in_exact_measurement': in_measurement,
        'stored_height_values_across_families_scales': retained_heights,
        'counts_are_records_not_unique_pulses_or_trees': True,
        'boundary_tie_rule': 'maximum_area_of_owning_half_open_raster_pixel_then_lexicographic_unit_id',
        'boundary_ties_including_cell_centers': {k: v['assigner'].boundary_ties for k, v in pools.items()}}
