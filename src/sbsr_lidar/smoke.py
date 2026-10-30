"""Testes pequenos de interoperabilidade; não calcula métricas científicas."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import psutil
import rasterio
from pyproj import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from .config import Config
from .environment import environment_snapshot, native_command, source_digest
from .runtime import Run, exclusive_lock
from .storage import atomic_write_json, cache_key, fingerprint, load_cache, save_cache


def real_input(config: Config) -> Path:
    code = config.pilot.core_tiles[0]
    return config.paths.data_root / "MDS_2020" / f"MDS_{code}_1000.laz"


def header_and_sample(path: Path, limit: int) -> dict:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
        raise ValueError("Teste de leitura limitado a 1–10.000 pontos")
    with laspy.open(path, read_evlrs=False) as reader:
        header = reader.header
        crs = header.parse_crs()
        points = reader.read_points(min(limit, header.point_count))
        if len(points) == 0:
            raise ValueError("Nuvem vazia no teste de leitura")
        xyz = np.column_stack([points.x, points.y, points.z])
        if not np.isfinite(xyz).all():
            raise ValueError("Coordenadas não finitas na amostra")
        return {"path": str(path), "declared_point_count": int(header.point_count),
                "sample_points_read": len(points), "sample_selection": "primeiros_pontos_apenas_teste_IO",
                "sample_is_representative": False, "version": str(header.version),
                "point_format": header.point_format.id, "epsg": crs.to_epsg() if crs else None,
                "scales": header.scales.tolist(), "offsets": header.offsets.tolist(),
                "bounds_min": header.mins.tolist(), "bounds_max": header.maxs.tolist(),
                "dimensions": list(header.point_format.dimension_names),
                "vertical_vlrs": [{"user_id": v.user_id, "description": v.description}
                                  for v in header.vlrs if "vert" in v.user_id.lower()]}


def synthetic_checks(config: Config, directory: Path) -> tuple[dict, list[Path]]:
    header = laspy.LasHeader(version="1.4", point_format=8)
    header.scales = np.array([0.001, 0.001, 0.001])
    header.offsets = np.array([330000.0, 7390000.0, 0.0])
    header.add_crs(CRS.from_epsg(config.grid.epsg))
    data = laspy.LasData(header)
    data.x = np.array([330000.5, 330001.5, 330000.5, 330001.5])
    data.y = np.array([7390000.5, 7390000.5, 7390001.5, 7390001.5])
    data.z = np.array([0.0, 3.0, 8.0, 12.0])
    data.classification = np.array([2, 3, 4, 6], dtype=np.uint8)
    data.return_number = np.ones(4, dtype=np.uint8)
    data.number_of_returns = np.ones(4, dtype=np.uint8)
    source = directory / "synthetic.laz"
    data.write(source)
    with laspy.open(source) as reader:
        recovered = list(reader.chunk_iterator(2))
    if not np.allclose(np.concatenate([p.z for p in recovered]), data.z):
        raise AssertionError("Falha no round-trip LAZ sintético")
    raster = directory / "synthetic_pdal.tif"
    pipeline = directory / "synthetic_pipeline.json"
    atomic_write_json(pipeline, {"pipeline": [
        {"type": "readers.las", "filename": str(source)},
        {"type": "filters.head", "count": 4},
        {"type": "writers.gdal", "filename": str(raster), "resolution": 1.0,
         "output_type": "max", "data_type": "float32", "nodata": config.grid.nodata},
    ]})
    native = native_command(config.tools.pdal, ["pipeline", str(pipeline)], config.tools.timeout_seconds)
    if not native["ok"]:
        raise RuntimeError(f"PDAL não processou o LAZ sintético: {native}")
    with rasterio.open(raster) as ds:
        values = ds.read(1, masked=True)
        if ds.crs is None or ds.crs.to_epsg() != config.grid.epsg or values.count() == 0:
            raise AssertionError("Raster PDAL ilegível ou sem CRS/dados")
        raster_shape = list(ds.shape)
    gdal = native_command(config.tools.gdalinfo, ["-json", str(raster)], config.tools.timeout_seconds)
    if not gdal["ok"]:
        raise RuntimeError(f"GDAL CLI não leu o produto sintético: {gdal}")
    parsed = json.loads(gdal["stdout"])
    # Invariante: altura zero válida e NoData são estados distintos.
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", height=1, width=2, count=1, dtype="float32",
                         crs=f"EPSG:{config.grid.epsg}", transform=from_origin(330000, 7390001, 1, 1),
                         nodata=config.grid.nodata) as ds:
            ds.write(np.array([[0.0, config.grid.nodata]], dtype=np.float32), 1)
            masked = ds.read(1, masked=True)
            if masked.mask.tolist() != [[False, True]]:
                raise AssertionError("Zero e NoData foram confundidos")
    return {"laz_roundtrip": True, "pdal_read_write": True,
            "rasterio_read_pdal_output": True, "gdal_cli_read_pdal_output": True,
            "zero_distinct_from_nodata": True, "synthetic_points": 4,
            "raster_shape": raster_shape, "gdal_size": parsed["size"]}, [source, pipeline, raster]


def smoke(config: Config, *, use_cache=True) -> dict:
    if not config.paths.mount_root.is_mount():
        raise ValueError(f"HD não montado: {config.paths.mount_root}")
    source = real_input(config)
    if not source.is_file():
        raise FileNotFoundError(source)
    if psutil.virtual_memory().available / 2**30 < config.resources.max_ram_gib:
        raise ValueError("RAM disponível inferior ao orçamento configurado")
    from .doctor import existing_parent
    for path, minimum in [(config.paths.runs_root, config.resources.min_local_free_gib),
                          (config.paths.output_root, config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free / 2**30 < minimum:
            raise ValueError(f"Espaço livre inferior à reserva configurada: {path}")
    # Impede duas execuções iguais no mesmo diretório, preservando o estado.
    with exclusive_lock(config.paths.runs_root / ".smoke.lock"):
        env = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
        if not env["pdal"]["ok"] or not env["gdalinfo"]["ok"]:
            raise RuntimeError("PDAL/GDAL CLI indisponíveis; execute doctor")
        inputs = [fingerprint(source), fingerprint(config.paths.protocol_file)]
        for file in [config.paths.corridors, config.paths.grid]:
            for sibling in sorted(file.parent.glob(file.stem + ".*")):
                if sibling.is_file():
                    inputs.append(fingerprint(sibling))
        code = source_digest()
        snapshot = config.model_dump(mode="json")
        key = cache_key(command="smoke", config=snapshot, inputs=inputs, code=code, environment=env)
        cache_root = config.paths.runs_root / "cache"
        run = Run(config.paths.runs_root, config.paths.state_file, "smoke", snapshot, inputs, env, code)
        try:
            cached = load_cache(cache_root, key) if use_cache else None
            if cached:
                outputs = [Path(x["path"]) for x in cached["outputs"]]
                run.finish(outputs, cache_hit=True, source_run_id=cached["source_run_id"])
                return {"ok": True, "run_id": run.run_id, "cache_hit": True,
                        "manifest": str(run.path / "manifest.json"), "report": str(outputs[0])}
            started = time.monotonic()
            sample = header_and_sample(source, config.resources.smoke_points)
            if sample["epsg"] != config.grid.epsg:
                raise ValueError("CRS do cabeçalho real difere da configuração")
            preview = native_command(config.tools.pdal, ["info", "--summary", str(source)],
                                     config.tools.timeout_seconds)
            if not preview["ok"]:
                raise RuntimeError(f"PDAL não abriu o cabeçalho real: {preview}")
            native_summary = json.loads(preview["stdout"])["summary"]
            if native_summary["num_points"] != sample["declared_point_count"]:
                raise ValueError("PDAL e Laspy discordam da contagem do cabeçalho")
            corridors = gpd.read_file(config.paths.corridors)
            selected = corridors.loc[corridors[config.pilot.corridor_field] == config.pilot.corridor_id]
            if len(selected) != 1:
                raise ValueError("Identificador do piloto não seleciona uma feição")
            checks, products = synthetic_checks(config, run.path)
            result = {"ok": True, "scope": "infraestrutura_etapa02", "scientific_pilot_executed": False,
                      "real_input": sample, "synthetic": checks,
                      "pdal_real_header_points": native_summary["num_points"],
                      "corridor_id": config.pilot.corridor_id, "features_selected": len(selected),
                      "elapsed_seconds": time.monotonic() - started,
                      "process_rss_mib_at_end": psutil.Process().memory_info().rss / 2**20,
                      "memory_measurement_is_peak": False}
            report = run.path / "smoke.json"
            atomic_write_json(report, result)
            outputs = [report, *products]
            save_cache(cache_root, key, run.run_id, outputs)
            run.finish(outputs)
            return {"ok": True, "run_id": run.run_id, "cache_hit": False,
                    "manifest": str(run.path / "manifest.json"), "report": str(report)}
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt))
            raise
