"""Verificações dos produtos reais, após prepare-inputs, sem reprocessar nuvens."""
import argparse
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json

PROTECTED = {
    "baixar_lidar_geosampa.py": "a4f566f39cc06ab931617720c1a8a4fa8391f40b85c4fd04ae69d1e8972df3ca",
    "tests/test_baixar_lidar_geosampa.py": "28b216ac967c08ce55fbc3b88bf9e9eb7dad5ea54f3ffc7f83930b8b7848aed0",
    "requirements.txt": "fd72dd0bc564965c8e021b2b0f38452c00bd290e47fae16df7bc28ce60aedc92",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/piloto.yaml"))
    parser.add_argument("--reports", type=Path, default=Path("relatorios/etapa03"))
    args = parser.parse_args()
    config = load_config(args.config)
    checks = {}
    summary = {}
    for case in ["main", "adversarial"]:
        execution = read_json(args.reports / f"execucao_{case}_final.json")
        report = read_json(Path(execution["report"]))
        domain = build_domain(config,case)
        manifest = RunManifest.model_validate(read_json(Path(execution["manifest"])))
        checks[f"{case}:manifest"] = manifest.status == "completed" and manifest.stage == "03" and manifest.code_sha256 == source_digest()
        checks[f"{case}:clouds"] = len(report["clouds"]) == 2*len(domain.nominal_tiles) and all(
            c["declared_points"] == c["points_read"] == sum(c["classes"].values()) and c["points_outside_header"] == 0
            for c in report["clouds"])
        checks[f"{case}:inputs_unchanged"] = all(fingerprint(Path(p.path)) == p.model_dump() for p in manifest.inputs)
        products = {Path(p).name: Path(p) for p in report["products"]}
        aoi = products["dominios.gpkg"]
        checks[f"{case}:geometry"] = all(
            gpd.read_file(aoi,layer=layer).geometry.iloc[0].equals_exact(geometry,0)
            for layer,geometry in [("corredor_oficial",domain.official),("medicao",domain.measurement),("contexto",domain.context)])
        with rasterio.open(products["mascara_medicao.tif"]) as ds:
            measurement = ds.read(1) == 1
            context = ds.read(1) != 255
            reference = (ds.shape, ds.transform, ds.crs)
        aligned = []
        for product in ["MDT","MDS"]:
            with rasterio.open(products[f"{product}_suporte_xy.tif"]) as ds:
                values = ds.read(1)
                aligned.append((ds.shape,ds.transform,ds.crs)==reference)
                stats = report["support"][product]["medicao"]
                checks[f"{case}:{product}:support"] = (
                    int(measurement.sum()) == stats["cells"] and
                    int(np.sum(measurement & (values == 1))) == stats["usable_occupied_cells"] and
                    int(np.sum(measurement & (values == 2))) == stats["only_excluded_return_cells"] and
                    int(np.sum(measurement & (values == 3))) == stats["no_return_cells"] and
                    np.array_equal(values == 255,~context) and ds.nodata == 255)
            for suffix in ["contagem_retornos","densidade_retornos"]:
                with rasterio.open(products[f"{product}_{suffix}.tif"]) as ds:
                    aligned.append((ds.shape,ds.transform,ds.crs)==reference)
                    checks[f"{case}:{product}:{suffix}:nodata"] = np.array_equal(ds.read(1)==ds.nodata,~context)
        checks[f"{case}:aligned_grid"] = all(aligned)
        cache = read_json(args.reports/f"cache_{case}.json")
        checks[f"{case}:cache"] = cache["cache_hit"] and cache["report"] == execution["report"]
        summary[case] = {"run_id": execution["run_id"], "report": execution["report"],
                         "points_read_by_product": {p: sum(c["points_read"] for c in report["clouds"] if c["produto"]==p)
                                                    for p in ["MDT","MDS"]},
                         "support": report["support"], "domain": report["domain"]}
    for path, expected in PROTECTED.items():
        checks[f"preserved:{path}"] = fingerprint(config.paths.project_root/path)["sha256"]==expected
    doctor = read_json(args.reports/'doctor.json')
    checks['doctor'] = doctor['ok'] and doctor['context_ready']
    scientific_log = (args.reports/'testes_cientificos.log').read_text()
    downloader_log = (args.reports/'downloader_regressao.log').read_text()
    scientific_passed = int(re.search(r'(\d+) passed',scientific_log).group(1))
    downloader_passed = int(re.search(r'(\d+) passed',downloader_log).group(1))
    subtests = int(re.search(r'(\d+) subtests passed',downloader_log).group(1))
    payload = {"ok": all(checks.values()), "checks": checks, "summary": summary,
               "tests": {"scientific_passed":scientific_passed,"downloader_passed":downloader_passed,"downloader_subtests_passed":subtests},
               "test_logs": [str(args.reports/'testes_cientificos.log'),str(args.reports/'downloader_regressao.log')]}
    atomic_write_json(args.reports/'verificacoes.json',payload)
    print(f"{sum(checks.values())}/{len(checks)} verificações de produtos/insumos passaram.")
    if not payload['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
