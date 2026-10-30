"""Auditoria integral por blocos e mapas de ocupação XY; sem terreno/altura."""
from __future__ import annotations

import math
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
import rasterio
import shapely
from affine import Affine
from rasterio.features import geometry_mask

from .config import Config

COUNT_NODATA = np.iinfo(np.uint32).max


@dataclass
class GridLayout:
    width: int
    height: int
    transform: Affine
    resolution: float
    context_mask: np.ndarray
    measurement_mask: np.ndarray
    edge_mask: np.ndarray

    @property
    def shape(self):
        return self.height, self.width


def grid_layout(config: Config, domain) -> GridLayout:
    resolution = config.grid.resolution_m
    xmin, ymin, xmax, ymax = domain.context.bounds
    left = config.grid.origin_x + math.floor((xmin-config.grid.origin_x)/resolution)*resolution
    right = config.grid.origin_x + math.ceil((xmax-config.grid.origin_x)/resolution)*resolution
    bottom = config.grid.origin_y + math.floor((ymin-config.grid.origin_y)/resolution)*resolution
    top = config.grid.origin_y + math.ceil((ymax-config.grid.origin_y)/resolution)*resolution
    width = max(1, int(round((right-left)/resolution)))
    height = max(1, int(round((top-bottom)/resolution)))
    if width*height*64 > config.resources.max_ram_gib*2**30:
        raise ValueError("Grade de auditoria excede orçamento de memória")
    transform = Affine(resolution, 0, left, 0, -resolution, top)
    context_mask = geometry_mask([domain.context], (height, width), transform, invert=True)
    measurement_mask = geometry_mask([domain.measurement], (height, width), transform, invert=True) & context_mask
    inner = domain.measurement.buffer(-config.input_preparation.edge_width_m)
    inner_mask = np.zeros((height, width), dtype=bool) if inner.is_empty else geometry_mask([inner], (height, width), transform, invert=True)
    if not measurement_mask.any():
        raise ValueError("Nenhum centro de célula dentro da medição; revisar resolução/domínio")
    return GridLayout(width, height, transform, resolution, context_mask, measurement_mask, measurement_mask & ~inner_mask)


def write_raster(path: Path, bands: list[np.ndarray], layout: GridLayout, *, epsg: int,
                 dtype: str, nodata, descriptions: list[str], tags: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tif")
        os.close(fd)
        temporary = Path(name)
        with rasterio.open(temporary, "w", driver="GTiff", height=layout.height, width=layout.width,
                           count=len(bands), dtype=dtype, crs=f"EPSG:{epsg}", transform=layout.transform,
                           nodata=nodata, compress="deflate", tiled=True) as ds:
            for index, (values, description) in enumerate(zip(bands, descriptions), 1):
                ds.write(values.astype(dtype), index)
                ds.set_band_description(index, description)
            ds.update_tags(stage="03", meaning="point_occupancy_not_canopy_or_terrain_validity",
                           all_touched="false", count_unit="point_records_not_unique_pulses")
            if tags:
                ds.update_tags(**tags)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _count_update(target: np.ndarray, layout: GridLayout, x, y):
    cols = np.floor((x-layout.transform.c)/layout.resolution).astype(np.int64)
    rows = np.floor((layout.transform.f-y)/layout.resolution).astype(np.int64)
    inside = (cols >= 0) & (cols < layout.width) & (rows >= 0) & (rows < layout.height)
    flat = rows[inside]*layout.width+cols[inside]
    target.ravel()[:] += np.bincount(flat, minlength=target.size).astype(np.uint64)
    return int((~inside).sum())


def audit_cloud(path: Path, product: str, code: str, nominal, domain, layout: GridLayout,
                counts_all: np.ndarray, counts_usable: np.ndarray, config: Config) -> dict:
    classes = Counter()
    returns = Counter()
    total_returns = Counter()
    flags = Counter()
    spectra = {}
    count = finite_count = context_count = usable_context_count = outside_nominal = outside_header = outside_grid = 0
    bbox = domain.context.bounds
    shapely.prepare(domain.context)
    shapely.prepare(nominal)
    with laspy.open(path, read_evlrs=False) as reader:
        h = reader.header
        crs = h.parse_crs()
        if crs is None or crs.to_epsg() != config.grid.epsg:
            raise ValueError(f"CRS do LAZ incompatível: {path}")
        if not np.isfinite(h.scales).all() or np.any(h.scales <= 0) or not np.isfinite(h.offsets).all():
            raise ValueError(f"Escalas/offsets inválidos: {path}")
        dims = list(h.point_format.dimension_names)
        header = {"path": str(path), "produto": product, "quadricula": code,
                  "epsg": crs.to_epsg(), "version": str(h.version), "point_format": h.point_format.id,
                  "declared_points": int(h.point_count), "scales": h.scales.tolist(), "offsets": h.offsets.tolist(),
                  "mins": h.mins.tolist(), "maxs": h.maxs.tolist(), "dimensions": dims,
                  "global_encoding": h.global_encoding.value, "creation_date": str(h.creation_date),
                  "software": h.generating_software,
                  "projection_vlrs": [{"user_id": v.user_id, "record_id": v.record_id, "description": v.description}
                                      for v in h.vlrs if v.user_id in {"VertDatum-Geoid", "Scale-Height", "LASF_Projection"}]}
        for points in reader.chunk_iterator(config.resources.chunk_points):
            count += len(points)
            xyz = np.column_stack([points.x, points.y, points.z])
            finite = np.isfinite(xyz).all(axis=1)
            finite_count += int(finite.sum())
            cls = np.asarray(points.classification)
            vals, nums = np.unique(cls, return_counts=True)
            classes.update(dict(zip(vals.tolist(), nums.tolist())))
            rn = np.asarray(points.return_number)
            nr = np.asarray(points.number_of_returns)
            for array, counter in [(rn, returns), (nr, total_returns)]:
                vals, nums = np.unique(array, return_counts=True)
                counter.update(dict(zip(vals.tolist(), nums.tolist())))
            invalid_returns = (rn < 1) | (rn > nr)
            flags["invalid_return"] += int(invalid_returns.sum())
            for name in ["withheld", "synthetic", "key_point", "overlap"]:
                if name in dims:
                    flags[name] += int(np.count_nonzero(np.asarray(points[name])))
            for name in ["intensity", "red", "green", "blue", "nir"]:
                if name in dims:
                    array = np.asarray(points[name])
                    prior = spectra.setdefault(name, {"min": int(array.min()), "max": int(array.max()), "zero_count": 0})
                    prior["min"] = min(prior["min"], int(array.min()))
                    prior["max"] = max(prior["max"], int(array.max()))
                    prior["zero_count"] += int(np.count_nonzero(array == 0))
            tolerance = h.scales*2
            outside_header += int(np.sum(finite & np.any((xyz < h.mins-tolerance) | (xyz > h.maxs+tolerance), axis=1)))
            outside_nominal += int(np.sum(finite & ~shapely.intersects_xy(nominal, xyz[:, 0], xyz[:, 1])))
            candidates = finite & (xyz[:, 0] >= bbox[0]) & (xyz[:, 0] <= bbox[2]) & (xyz[:, 1] >= bbox[1]) & (xyz[:, 1] <= bbox[3])
            in_context = np.zeros(len(points), dtype=bool)
            in_context[candidates] = shapely.intersects_xy(domain.context, xyz[candidates, 0], xyz[candidates, 1])
            context_count += int(in_context.sum())
            withheld = np.asarray(points.withheld).astype(bool)
            usable = in_context & ~withheld & ~invalid_returns & ~np.isin(cls, config.input_preparation.excluded_noise_classes)
            usable_context_count += int(usable.sum())
            outside_grid += _count_update(counts_all, layout, xyz[in_context, 0], xyz[in_context, 1])
            _count_update(counts_usable, layout, xyz[usable, 0], xyz[usable, 1])
    if count != header["declared_points"] or count == 0:
        raise ValueError(f"Contagem lida diverge do cabeçalho/vazia: {path}: {count}")
    if finite_count != count or outside_header:
        raise ValueError(f"Coordenadas não finitas ou fora dos limites declarados: {path}")
    header.update(points_read=count, classes={str(k): v for k, v in sorted(classes.items())},
                  class_proportions={str(k): v/count for k, v in sorted(classes.items())},
                  return_number_counts={str(k): v for k, v in sorted(returns.items())},
                  number_of_returns_counts={str(k): v for k, v in sorted(total_returns.items())}, flags=dict(flags),
                  spectra=spectra, points_in_context=context_count, usable_points_in_context=usable_context_count,
                  points_outside_nominal_tile=outside_nominal, points_outside_header=outside_header,
                  context_points_outside_raster_halfopen_bounds=outside_grid,
                  classification_scope="whole_file", integrity="all_declared_points_decoded")
    return header


def support_products(config: Config, domain, layout: GridLayout, rows: list[dict], directory: Path,
                     event=lambda *a, **kw: None) -> tuple[dict, list[dict], list[Path]]:
    reports = {}
    audits = []
    outputs = []
    measurement = np.full(layout.shape, 255, dtype=np.uint8)
    measurement[layout.context_mask] = 0
    measurement[layout.measurement_mask] = 1
    path = directory / "mascara_medicao.tif"
    write_raster(path, [measurement], layout, epsg=config.grid.epsg, dtype="uint8", nodata=255,
                 descriptions=["1_medicao_0_somente_contexto_255_exterior"])
    outputs.append(path)
    for product in ("MDT", "MDS"):
        counts = np.zeros(layout.shape, dtype=np.uint64)
        usable = np.zeros_like(counts)
        for row in rows:
            if row["produto"] != product:
                continue
            code = row["quadricula"]
            nominal = domain.nominal_tiles.loc[domain.nominal_tiles.quadricula == code].geometry.iloc[0]
            event("audit_start", product=product, tile=code)
            item = audit_cloud(Path(row["selected_laz"]), product, code, nominal, domain, layout, counts, usable, config)
            audits.append(item)
            event("audit_complete", product=product, tile=code, points=item["points_read"])
        if counts.max() >= COUNT_NODATA:
            raise ValueError("Contagem por célula excede formato uint32")
        masks = {"medicao": layout.measurement_mask, "borda_medicao": layout.edge_mask,
                 "interior_medicao": layout.measurement_mask & ~layout.edge_mask, "contexto": layout.context_mask}
        stats = {}
        for label, mask in masks.items():
            n = int(mask.sum())
            occupied = int(np.sum(mask & (usable > 0)))
            stats[label] = {"cells": n, "usable_occupied_cells": occupied,
                            "no_return_cells": int(np.sum(mask & (counts == 0))),
                            "only_excluded_return_cells": int(np.sum(mask & (counts > 0) & (usable == 0))),
                            "occupied_fraction": occupied/n if n else None,
                            "center_mask_area_m2": n*layout.resolution**2}
        reports[product] = stats
        for array in (counts, usable):
            array[~layout.context_mask] = COUNT_NODATA
        count_path = directory / f"{product}_contagem_retornos.tif"
        write_raster(count_path, [counts, usable], layout, epsg=config.grid.epsg, dtype="uint32", nodata=COUNT_NODATA,
                     descriptions=["registros_totais_por_celula", "registros_apos_exclusoes_qc"])
        density = usable.astype(np.float32)/layout.resolution**2
        density[~layout.context_mask] = config.grid.nodata
        density_path = directory / f"{product}_densidade_retornos.tif"
        write_raster(density_path, [density], layout, epsg=config.grid.epsg, dtype="float32", nodata=config.grid.nodata,
                     descriptions=["registros_apos_qc_por_m2_nao_pulsos_independentes"])
        status = np.full(layout.shape, 255, dtype=np.uint8)
        status[layout.context_mask] = 3
        status[layout.context_mask & (counts > 0)] = 2
        status[layout.context_mask & (usable > 0)] = 1
        status_path = directory / f"{product}_suporte_xy.tif"
        write_raster(status_path, [status], layout, epsg=config.grid.epsg, dtype="uint8", nodata=255,
                     descriptions=["1_retorno_utilizavel_2_somente_excluidos_3_sem_retorno_255_exterior"])
        outputs.extend([count_path, density_path, status_path])
    return reports, audits, outputs
