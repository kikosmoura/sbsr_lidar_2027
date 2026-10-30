"""Ferramentas nativas são verificadas em subprocessos, sem bindings PDAL."""
from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import shutil
import subprocess
from pathlib import Path

from . import __version__

PACKAGES = ["numpy", "scipy", "pandas", "geopandas", "shapely", "pyogrio", "pyproj",
            "rasterio", "laspy", "lazrs", "PyYAML", "pydantic", "psutil",
            "scikit-image", "scikit-learn", "pyarrow", "matplotlib", "requests"]
REQUIRED_PDAL = {"readers.las", "writers.las", "writers.gdal", "writers.null",
                 "filters.crop", "filters.hag_dem", "filters.hag_delaunay",
                 "filters.covariancefeatures", "filters.smrf", "filters.head"}


def native_command(executable: str, args: list[str], timeout: int) -> dict:
    found = shutil.which(executable)
    if found is None:
        return {"ok": False, "executable": executable, "error": "Executável ausente"}
    try:
        process = subprocess.run([found, *args], capture_output=True, text=True,
                                 timeout=timeout, check=False)
        return {"ok": process.returncode == 0, "executable": str(Path(found).resolve()),
                "returncode": process.returncode, "stdout": process.stdout.strip(),
                "stderr": process.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "executable": found, "error": str(error)}


def environment_snapshot(pdal: str, gdalinfo: str, timeout: int) -> dict:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "package": __version__, "packages": versions,
            "pdal": native_command(pdal, ["--version"], timeout),
            "gdalinfo": native_command(gdalinfo, ["--version"], timeout)}


def source_digest() -> str:
    digest = hashlib.sha256()
    root = Path(__file__).parent
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()
