"""Pré-verificação somente de leitura: sem download e sem criação de produtos."""
from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path

from .config import Config
from .domain import cloud_path
from .environment import REQUIRED_PDAL, environment_snapshot, native_command
from .runtime import utc_now


def existing_parent(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def inspect_environment(config: Config) -> dict:
    import psutil

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    env = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
    memory = psutil.virtual_memory()
    available = memory.available / 2**30
    add("memory", "ok" if available >= config.resources.max_ram_gib else "error",
        {"available_gib": available, "total_gib": memory.total / 2**30,
         "budget_gib": config.resources.max_ram_gib, "logical_cpus": psutil.cpu_count()})
    add("mount", "ok" if config.paths.mount_root.is_mount() else "error", str(config.paths.mount_root))
    add("protocol_file", "ok" if config.paths.protocol_file.is_file() else "error", str(config.paths.protocol_file))
    for name, target, required in [
        ("output_disk", config.paths.output_root, config.resources.min_output_free_gib),
        ("local_disk", config.paths.runs_root, config.resources.min_local_free_gib),
    ]:
        parent = existing_parent(target)
        try:
            free = shutil.disk_usage(parent).free / 2**30
            writable = os.access(parent, os.W_OK | os.X_OK)
            add(name, "ok" if free >= required and writable else "error",
                {"target": str(target), "checked_parent": str(parent), "free_gib": free,
                 "required_gib": required, "writable_by_os_access": writable,
                 "write_probe_performed": False})
        except OSError as error:
            add(name, "error", str(error))
    for name, info in [("pdal", env["pdal"]), ("gdalinfo", env["gdalinfo"])]:
        add(name, "ok" if info["ok"] else "error", info)
    if env["pdal"]["ok"]:
        drivers = native_command(config.tools.pdal, ["--drivers"], config.tools.timeout_seconds)
        missing = sorted(x for x in REQUIRED_PDAL if x not in drivers.get("stdout", ""))
        add("pdal_drivers", "ok" if drivers["ok"] and not missing else "error", {"missing": missing})
    module_names = {"numpy": "numpy", "scipy": "scipy", "pandas": "pandas",
                    "geopandas": "geopandas", "shapely": "shapely", "pyogrio": "pyogrio",
                    "pyproj": "pyproj", "rasterio": "rasterio", "laspy": "laspy", "lazrs": "lazrs",
                    "PyYAML": "yaml", "pydantic": "pydantic", "psutil": "psutil",
                    "scikit-image": "skimage", "scikit-learn": "sklearn", "pyarrow": "pyarrow",
                    "requests": "requests"}
    for package, module in module_names.items():
        try:
            importlib.import_module(module)
            add("python:" + package, "ok", env["packages"][package])
        except Exception as error:
            add("python:" + package, "error", f"{type(error).__name__}: {error}")
    # Importar matplotlib pode criar cache no HOME. No doctor, verificar instalação
    # sem inicializar backend/configuração gráfica e manter a checagem sem escrita.
    add("python:matplotlib", "ok" if env["packages"]["matplotlib"] else "error",
        {"version": env["packages"]["matplotlib"], "import_performed": False})
    try:
        import laspy
        import rasterio
        import pyogrio
        backends = [str(x) for x in laspy.LazBackend.detect_available()]
        add("laz_backend", "ok" if backends else "error", backends)
        env["gdal_python"] = {"rasterio": rasterio.__gdal_version__,
                              "pyogrio": pyogrio.__gdal_version_string__}
        # Versões distintas são registradas; interoperabilidade é testada no smoke.
        add("gdal_versions", "ok", env["gdal_python"])
    except Exception as error:
        add("laz_and_gdal_python", "error", str(error))
    try:
        import geopandas as gpd
        from pyproj import CRS

        target = CRS.from_epsg(config.grid.epsg)
        metric = target.is_projected and all(axis.unit_conversion_factor == 1 for axis in target.axis_info[:2])
        add("configured_crs", "ok" if metric else "error", target.to_string())
        for name, path in [("corridors", config.paths.corridors), ("grid", config.paths.grid)]:
            frame = gpd.read_file(path)
            crs_ok = frame.crs is not None and frame.crs.equals(target)
            add(name, "ok" if crs_ok and len(frame) else "error",
                {"path": str(path), "features": len(frame), "crs": str(frame.crs)})
            if name == "corridors":
                valid_field = config.pilot.corridor_field in frame.columns
                selected = frame.loc[frame[config.pilot.corridor_field] == config.pilot.corridor_id] if valid_field else frame.iloc[:0]
                ok = len(selected) == 1 and selected.geom_type.isin(["Polygon", "MultiPolygon"]).all() and selected.is_valid.all() and not selected.is_empty.any()
                add("pilot_id", "ok" if ok else "error", {"field": config.pilot.corridor_field,
                    "id": config.pilot.corridor_id, "matches": len(selected)})
    except Exception as error:
        add("vector_inputs", "error", f"{type(error).__name__}: {error}")
    for group, codes in [("core", config.pilot.core_tiles), ("context", config.pilot.context_tiles),
                         ("sensitivity", config.pilot.sensitivity_tiles),
                         ("adversarial", [config.pilot.adversarial_tile])]:
        for code in codes:
            for product in ("MDT", "MDS"):
                path = cloud_path(config, product, code)
                present = path.is_file() and path.stat().st_size > 0
                add(f"input:{group}:{product}:{code}", "ok" if present else ("error" if group in {"core", "adversarial"} else "warning"),
                    {"path": str(path), "present": present,
                     "meaning": "Existência; cabeçalho/pontos não auditados por doctor"})
    return {"schema_version": "0.1.0", "command": "doctor", "timestamp_utc": utc_now(),
            "ok": not any(x["status"] == "error" for x in checks),
            "warnings": sum(x["status"] == "warning" for x in checks),
            "checks": checks, "environment": env,
            "scientific_pilot_executed": False, "write_probe_performed": False,
            "context_ready": all(cloud_path(config, prod, code).is_file()
                                 for code in config.pilot.context_tiles for prod in ("MDS", "MDT"))}
