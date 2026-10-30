"""Execução limitada da etapa 03: domínio, complementos e QC dos insumos."""
from __future__ import annotations

import csv
import os
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import psutil
from shapely.geometry import box

from .acquisition import ensure_inputs
from .config import Config
from .doctor import existing_parent
from .domain import build_domain, input_plan
from .environment import environment_snapshot, source_digest
from .input_qc import grid_layout, support_products
from .runtime import Run, exclusive_lock
from .storage import atomic_write_json, cache_key, fingerprint, load_cache, save_cache


def plan_inputs(config: Config, case: str) -> dict:
    domain = build_domain(config, case)
    return {"scope": "etapa03_insumos_piloto", "domain": domain.metadata,
            "files": input_plan(config, domain), "network_accessed": False}


def _vectors(path: Path, layers: dict[str, gpd.GeoDataFrame]):
    """Novo GeoPackage, publicado somente após todas as camadas serem gravadas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".aoi_", suffix=".gpkg")
    os.close(fd)
    temporary = Path(name)
    temporary.unlink()
    try:
        for layer, frame in layers.items():
            frame.to_file(temporary, layer=layer, driver="GPKG", engine="pyogrio")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _input_fingerprints(config):
    paths = [config.paths.protocol_file]
    if config.paths.downloader_script:
        paths.append(config.paths.downloader_script)
    for file in (config.paths.corridors, config.paths.grid):
        paths.extend(sorted(file.parent.glob(file.stem + ".*")))
    return [fingerprint(p) for p in paths if p.is_file()]


def _report(result: dict) -> str:
    domain = result["domain"]
    lines = [f"# QC dos insumos — {domain['case']} / {domain['corridor_id']}", "",
             f"Execução: `{result['run_id']}`. EPSG:{domain['epsg']}; célula de {result['resolution_m']} m.", "",
             f"Área oficial: {domain['official_area_m2']:.3f} m²; medição: {domain['measurement_area_m2']:.3f} m²; contexto: {domain['context_area_m2']:.3f} m².",
             f"Folhas: {', '.join(domain['tiles'])}.", "",
             "|Produto|Registros lidos (arquivos integrais)|Células de medição|Com retorno após QC|Sem retorno|Somente excluídos|",
             "|---|---:|---:|---:|---:|---:|"]
    for product, report in result["support"].items():
        stats = report["medicao"]
        count = sum(x["points_read"] for x in result["clouds"] if x["produto"] == product)
        lines.append(f"|{product}|{count}|{stats['cells']}|{stats['usable_occupied_cells']}|{stats['no_return_cells']}|{stats['only_excluded_return_cells']}|")
    lines += ["", "## Interpretação e limites", ""]
    lines += ["- " + text for text in result["limitations"]]
    lines += ["", "## Artefatos", ""]
    lines += [f"- `{path}`" for path in result["products"]]
    return "\n".join(lines) + "\n"


def prepare_inputs(config: Config, case: str, *, download_missing=False, use_cache=True) -> dict:
    # Nenhuma criação externa antes de confirmar montagem, orçamento e plano.
    if not config.paths.mount_root.is_mount():
        raise ValueError(f"HD não montado: {config.paths.mount_root}")
    if psutil.virtual_memory().available / 2**30 < config.resources.max_ram_gib:
        raise ValueError("RAM disponível inferior ao orçamento configurado")
    for path, minimum in [(config.paths.runs_root, config.resources.min_local_free_gib),
                          (config.paths.output_root, config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free / 2**30 < minimum:
            raise ValueError(f"Espaço livre inferior à reserva: {path}")
    domain = build_domain(config, case)
    plan = input_plan(config, domain)
    layout = grid_layout(config, domain)
    with exclusive_lock(config.paths.runs_root / ".prepare_inputs.lock"):
        env = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
        inputs = _input_fingerprints(config)
        snapshot = config.model_dump(mode="json")
        code = source_digest()
        command = f"prepare-inputs:{case}"
        run = Run(config.paths.runs_root, config.paths.state_file, command, snapshot, inputs, env, code, stage="03")
        started = time.monotonic()

        def event(name, **details):
            run.event(name, **details)
            print(f"{name}: {details}", file=sys.stderr, flush=True)

        try:
            plan_path = run.path / "plano_complementos.json"
            atomic_write_json(plan_path, {"domain": domain.metadata, "files": plan})
            rows = ensure_inputs(config, plan, download_missing=download_missing, event=event)
            inputs += [fingerprint(Path(x["selected_laz"])) for x in rows]
            # O cache depende dos LAZ efetivamente lidos. ZIP e LAZ nunca são duas entradas de pontos.
            run.manifest["inputs"] = inputs
            run._checkpoint()
            key = cache_key(command=command, config=snapshot, inputs=inputs, code=code, environment=env)
            cache_root = config.paths.runs_root / "cache"
            cached = load_cache(cache_root, key) if use_cache else None
            if cached:
                outputs = [Path(x["path"]) for x in cached["outputs"]]
                run.finish(outputs, cache_hit=True, source_run_id=cached["source_run_id"])
                return {"ok": True, "case": case, "run_id": run.run_id, "cache_hit": True,
                        "manifest": str(run.path / "manifest.json"), "report": str(outputs[0])}
            directory = config.paths.output_root / "etapa03" / case / run.run_id
            directory.mkdir(parents=True, exist_ok=False)
            aoi = directory / "dominios.gpkg"
            def frame(geometry, role):
                return gpd.GeoDataFrame({"corridor_id": [domain.corridor_id], "role": [role],
                                        "area_m2": [float(geometry.area)]}, geometry=[geometry], crs=config.grid.epsg)
            _vectors(aoi, {"corredor_oficial": frame(domain.official, "oficial"),
                           "medicao": frame(domain.measurement, "medicao"),
                           "contexto": frame(domain.context, "contexto"),
                           "quadriculas": domain.nominal_tiles[["quadricula", "geometry"]]})
            support, audits, rasters = support_products(config, domain, layout, rows, directory, event)
            # Verifica identidade após leitura integral para detectar alterações concorrentes.
            for prior in inputs:
                if fingerprint(Path(prior["path"])) != prior:
                    raise OSError(f"Insumo mudou durante o QC: {prior['path']}")
            index_path = directory / "indice_nuvens.gpkg"
            records = [{k: item[k] for k in ["path", "produto", "quadricula", "points_read", "epsg",
                                              "version", "point_format", "points_outside_nominal_tile"]} for item in audits]
            bounds = [box(item["mins"][0], item["mins"][1], item["maxs"][0], item["maxs"][1]) for item in audits]
            _vectors(index_path, {"nuvens": gpd.GeoDataFrame(records, geometry=bounds, crs=config.grid.epsg)})
            classes_path = directory / "contagem_classes.csv"
            with classes_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["produto", "quadricula", "classe", "registros", "proporcao", "escopo"])
                for item in audits:
                    for cls, n in item["classes"].items():
                        writer.writerow([item["produto"], item["quadricula"], cls, n, n/item["points_read"], "arquivo_integral"])
            provenance = directory / "manifesto_insumos.json"
            for row in rows:
                if row.get("extraction"):
                    row["archive_fingerprint"] = fingerprint(Path(row["archive"]))
            atomic_write_json(provenance, {"run_id": run.run_id, "domain": domain.metadata,
                                          "files": rows, "inputs": inputs})
            products = [aoi, index_path, classes_path, provenance, *rasters]
            limitations = [
                "Contagens de classes/retornos são integrais por arquivo selecionado; não representam o acervo municipal.",
                "Densidade conta registros, sem deduplicar pulsos/pontos entre folhas. MDT e MDS não são observações independentes.",
                "Suporte XY é ocupação por retornos, não validade de terreno nem cobertura arbórea. Célula sem retorno não é ausência de árvores.",
                "Exclusão QC: withheld, retorno inválido (número <1 ou maior que total), classes " + str(config.input_preparation.excluded_noise_classes) + ". Classe 3 permanece incluída.",
                "Rasterização por centro de célula; área rasterizada difere da área vetorial. Zero dentro do contexto significa nenhum registro; exterior é NoData.",
                "Borda de medição: faixa interna de " + str(config.input_preparation.edge_width_m) + " m. Não confundir borda de polígono com erro de costura entre folhas.",
                "RGB/NIR são atributos de intensidade/cor, sem comprovação de refletância calibrada. Não há validação altimétrica externa nesta etapa.",
                "Nenhum DTM interpolado, altura normalizada, máscara arbórea ou indicador científico foi produzido."]
            if domain.metadata["context_clipped_to_tile"]:
                limitations.append(f"Caso adverso restrito à interseção corredor/folha; halo truncado na borda nominal, com {domain.metadata['requested_context_omitted_m2']:.3f} m² de contexto solicitado fora do domínio. Não representa o corredor completo.")
            result = {"ok": True, "stage": "03", "run_id": run.run_id, "domain": domain.metadata,
                      "scientific_pilot_executed": False, "resolution_m": layout.resolution,
                      "raster_grid": {"width": layout.width, "height": layout.height, "transform": list(layout.transform)[:6],
                                      "origin_x": config.grid.origin_x, "origin_y": config.grid.origin_y},
                      "support": support, "clouds": audits, "limitations": limitations,
                      "products": [str(p) for p in products], "elapsed_seconds": time.monotonic()-started,
                      "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                      "new_downloads": sum(x["needs_download"] for x in plan)}
            report = run.path / "qc_insumos.json"
            report_md = run.path / "qc_insumos.md"
            atomic_write_json(report, result)
            report_md.write_text(_report(result), encoding="utf-8")
            outputs = [report, report_md, plan_path, *products]
            save_cache(cache_root, key, run.run_id, outputs)
            run.finish(outputs)
            return {"ok": True, "case": case, "run_id": run.run_id, "cache_hit": False,
                    "manifest": str(run.path / "manifest.json"), "report": str(report), "products_root": str(directory)}
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt))
            raise
