"""Unidades vetoriais exatas; folhas são procedência, nunca fronteiras amostrais."""
from __future__ import annotations

import hashlib
import math

import geopandas as gpd
import shapely
from shapely.geometry import Polygon, box


def polygon_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return sorted([p for g in geometry.geoms for p in polygon_parts(g)],
                      key=lambda p: (*p.bounds, shapely.normalize(p).wkb_hex))
    return []


def polygonal(geometry):
    parts = polygon_parts(geometry)
    return shapely.union_all(parts) if parts else Polygon()


def stable_geometry_id(geometry):
    return hashlib.sha256(shapely.normalize(geometry).wkb).hexdigest()[:12]


def frame(rows, epsg, columns=()):
    if rows:
        return gpd.GeoDataFrame(rows, geometry='geometry', crs=epsg)
    return gpd.GeoDataFrame({c: [] for c in columns}, geometry=[], crs=epsg)


def support_fields(geometry, observed, uncertain, config):
    area = geometry.area
    observation = geometry.intersection(observed).area
    unknown = geometry.intersection(uncertain).area
    return {'area_effective_m2': area, 'area_observed_m2': observation,
            'fraction_observed': observation / area if area else None,
            'area_classification_uncertain_m2': unknown,
            'residual_below_minimum_area': area < config.support.minimum_unit_area_m2,
            'eligible_area_observation': area >= config.support.minimum_unit_area_m2
            and observation / area >= config.support.minimum_observed_fraction}


def tile_codes(geometry, tiles, tolerance=1e-8):
    return ','.join(sorted(str(row.quadricula) for row in tiles.itertuples()
                           if geometry.intersection(row.geometry).area > tolerance))


def regular_grid(config, domain, observed, uncertain, scale):
    rows = []
    total_cells = 0
    ox, oy = config.grid.origin_x, config.grid.origin_y
    for part_number, part in enumerate(polygon_parts(domain.measurement), 1):
        part_id = f'{domain.corridor_id}_P{part_number:03d}'
        x0, y0, x1, y1 = part.bounds
        ix0, iy0 = math.floor((x0-ox)/scale), math.floor((y0-oy)/scale)
        ix1, iy1 = math.ceil((x1-ox)/scale), math.ceil((y1-oy)/scale)
        total_cells += (ix1-ix0)*(iy1-iy0)
        if total_cells > config.segmentation.maximum_grid_cells_per_scale:
            raise ValueError('Grade excede orçamento de células do piloto')
        for ix in range(ix0, ix1):
            for iy in range(iy0, iy1):
                cell = box(ox+ix*scale, oy+iy*scale, ox+(ix+1)*scale, oy+(iy+1)*scale)
                for fragment, geom in enumerate(polygon_parts(part.intersection(cell)), 1):
                    if geom.area <= 0:
                        continue
                    rows.append({'unit_id': f'{part_id}_G{scale:g}_X{ix}_Y{iy}_F{fragment:02d}',
                        'corridor_id': domain.corridor_id, 'part_id': part_id, 'family': 'grid',
                        'branch_id': None, 'nominal_size_m': scale, 'grid_x': ix, 'grid_y': iy,
                        'fragment_number': fragment, 'nominal_area_m2': scale**2,
                        'fraction_of_nominal_cell': geom.area/scale**2,
                        'boundary_fragment': geom.area < scale**2-1e-8,
                        'tiles': tile_codes(geom, domain.nominal_tiles),
                        **support_fields(geom, observed, uncertain, config), 'geometry': geom})
    return frame(rows, config.grid.epsg, ['unit_id', 'part_id', 'nominal_size_m'])


def partition_check(units, target, tolerance):
    union = shapely.union_all(units.geometry.to_numpy()) if len(units) else Polygon()
    overlap = max(0., float(units.geometry.area.sum())-union.area)
    error = union.symmetric_difference(target).area
    valid = bool(units.geometry.is_valid.all())
    return {'ok': valid and overlap <= tolerance and error <= tolerance,
            'valid_geometries': valid, 'sum_area_m2': float(units.geometry.area.sum()),
            'target_area_m2': target.area, 'overlap_area_m2': overlap,
            'symmetric_difference_area_m2': error}


def support_correspondence(left, right, observed, *, family, scale_from, scale_to):
    rows = []
    if left.empty or right.empty:
        return rows
    for a in left.itertuples():
        for index in right.sindex.query(a.geometry, predicate='intersects'):
            b = right.iloc[index]
            if a.part_id != b.part_id:
                continue
            intersection = a.geometry.intersection(b.geometry)
            area = intersection.area
            if area <= 1e-9:
                continue
            oa = intersection.intersection(observed).area
            rows.append({'family': family, 'scale_from_m': scale_from, 'scale_to_m': scale_to,
                'unit_from': a.unit_id, 'unit_to': b.unit_id, 'part_id': a.part_id,
                'intersection_area_m2': area, 'observed_intersection_area_m2': oa,
                'fraction_from': area/a.geometry.area, 'fraction_to': area/b.geometry.area,
                'observed_fraction_from': oa/a.area_observed_m2 if a.area_observed_m2 > 0 else None,
                'observed_fraction_to': oa/b.area_observed_m2 if b.area_observed_m2 > 0 else None})
    return rows
