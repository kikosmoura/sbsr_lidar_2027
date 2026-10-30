"""Geometrias de medição/contexto e plano limitado aos insumos do piloto."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from pyproj import CRS

from .config import Config

PRODUCTS = ("MDT", "MDS")


def complementary_root(config: Config) -> Path:
    return config.paths.output_root / "insumos_complementares"


def cloud_path(config: Config, product: str, code: str) -> Path:
    name = f"{product}_{code}_1000.laz"
    original = config.paths.data_root / f"{product}_2020" / name
    complement = complementary_root(config) / f"{product}_2020" / name
    return original if original.is_file() or not complement.is_file() else complement


@dataclass
class Domain:
    case: str
    corridor_id: str
    official: object
    measurement: object
    context: object
    nominal_tiles: gpd.GeoDataFrame
    metadata: dict


def _select(frame: gpd.GeoDataFrame, field: str, value: str):
    if field not in frame:
        raise ValueError(f"Campo ausente: {field}")
    selected = frame.loc[frame[field].astype(str) == value]
    if len(selected) != 1:
        raise ValueError(f"Esperada uma feição para {field}={value}; encontradas {len(selected)}")
    geom = selected.geometry.iloc[0]
    if geom is None or geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"Geometria poligonal válida necessária: {value}")
    return geom


def build_domain(config: Config, case: str) -> Domain:
    if case not in {"main", "adversarial"}:
        raise ValueError("Caso deve ser main ou adversarial")
    corridors = gpd.read_file(config.paths.corridors)
    grid = gpd.read_file(config.paths.grid)
    crs = CRS.from_epsg(config.grid.epsg)
    if not crs.is_projected or any(x.unit_conversion_factor != 1 for x in crs.axis_info[:2]):
        raise ValueError("Domínio requer CRS projetado em metros")
    for frame in (corridors, grid):
        if frame.crs is None or not frame.crs.equals(crs):
            raise ValueError("CRS dos vetores difere da configuração; verificar antes de preparar")
    field = config.input_preparation.grid_code_field
    if field not in grid or grid[field].isna().any() or grid[field].duplicated().any():
        raise ValueError("Código da grade ausente, nulo ou duplicado")
    corridor_id = config.pilot.corridor_id if case == "main" else config.pilot.adversarial_corridor
    official = _select(corridors, config.pilot.corridor_field, corridor_id)
    if case == "main":
        measurement = official
        context = official.buffer(config.pilot.halo_m)
        selected = grid.loc[grid.intersects(context)].copy()
        core = sorted(grid.loc[grid.intersects(measurement), field].astype(str))
        expected = sorted(set(config.pilot.core_tiles + config.pilot.context_tiles))
        actual = sorted(selected[field].astype(str))
        if core != sorted(config.pilot.core_tiles) or actual != expected:
            raise ValueError(f"Plano derivado difere do configurado: núcleo={core}, contexto={actual}; revisar configuração")
        clipped_context = False
        omitted_area = 0.0
    else:
        tile = _select(grid, field, config.pilot.adversarial_tile)
        measurement = official.intersection(tile)
        if measurement.is_empty or measurement.area <= 0:
            raise ValueError("Caso adverso não intersecta a quadrícula configurada")
        requested = measurement.buffer(config.pilot.halo_m)
        context = requested.intersection(tile)
        omitted_area = requested.difference(context).area
        clipped_context = omitted_area > 1e-6
        selected = grid.loc[grid[field] == config.pilot.adversarial_tile].copy()
    selected["quadricula"] = selected[field].astype(str)
    selected = selected.sort_values("quadricula").reset_index(drop=True)
    if len(selected) > config.resources.max_pilot_tiles:
        raise ValueError("Domínio excede orçamento de folhas do piloto")
    metadata = {"case": case, "corridor_id": corridor_id, "epsg": config.grid.epsg,
                "official_area_m2": float(official.area), "measurement_area_m2": float(measurement.area),
                "context_area_m2": float(context.area), "halo_m": config.pilot.halo_m,
                "context_clipped_to_tile": clipped_context, "requested_context_omitted_m2": float(omitted_area),
                "measurement_is_official_polygon": case == "main",
                "tiles": selected.quadricula.tolist(), "measurement_bounds": list(measurement.bounds),
                "context_bounds": list(context.bounds)}
    return Domain(case, corridor_id, official, measurement, context, selected, metadata)


def input_plan(config: Config, domain: Domain) -> list[dict]:
    rows = []
    for code in domain.nominal_tiles.quadricula:
        for product in PRODUCTS:
            name = f"{product}_{code}_1000.laz"
            original = config.paths.data_root / f"{product}_2020" / name
            complement = complementary_root(config) / f"{product}_2020" / name
            original_zip = original.parent / f"{code}.zip"
            complement_zip = complement.parent / f"{code}.zip"
            candidates = [p for p in (original, complement) if p.is_file()]
            archives = [p for p in (original_zip, complement_zip) if p.is_file()]
            rows.append({"quadricula": code, "produto": product,
                         "original_laz": str(original), "complementary_laz": str(complement),
                         "selected_laz": str(candidates[0]) if candidates else None,
                         "archive": str(archives[0]) if archives else None,
                         "needs_download": not candidates and not archives,
                         "needs_extraction": not candidates and bool(archives),
                         "destination_archive": str(complement_zip)})
    new = sum(x["needs_download"] for x in rows)
    if new > config.input_preparation.max_new_downloads_per_case:
        raise ValueError(f"Plano exige {new} downloads; excede o limite explícito por caso")
    return rows
