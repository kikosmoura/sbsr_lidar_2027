#!/usr/bin/env python3
"""Seleciona quadrículas por interseção e baixa MDT/MDS LiDAR de 2020.

Exemplos (na pasta do projeto):
    venv/bin/python baixar_lidar_geosampa.py --listar
    venv/bin/python baixar_lidar_geosampa.py --quadricula 3312-431
    venv/bin/python baixar_lidar_geosampa.py
"""

from __future__ import annotations

import argparse
import csv
import errno
import logging
import re
import shutil
import sys
import time
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import requests
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parent
EXTERNAL_DRIVE = Path("/media/s299259068/TOSHIBA EXT")
DEFAULT_OUTPUT = EXTERNAL_DRIVE / "sbbr_lidar_2027"
PREVIOUS_OUTPUT = ROOT / "downloads/geosampa_2020"
PORTAL = "https://novogeosampa.prefeitura.sp.gov.br"
# IDs confirmados na configuração pública do novo GeoSampa em 24/10/2026.
LAYERS = {"MDT": 125, "MDS": 719}
LOG = logging.getLogger("geosampa")


class DownloadError(Exception):
    """Resposta ou arquivo incompatível com o produto solicitado."""


def polygon_parts(geometry):
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        return [part for item in geometry.geoms for part in polygon_parts(item)]
    return []


def read_polygons(path: Path, label: str) -> gpd.GeoDataFrame:
    if not path.is_file():
        raise ValueError(f"{label}: arquivo não encontrado: {path}")
    frame = gpd.read_file(path)
    if frame.crs is None:
        raise ValueError(f"{label}: CRS ausente. Defina o CRS correto e salve a camada com seu .prj.")
    usable = frame.geometry.notna() & ~frame.geometry.is_empty
    if not usable.all():
        LOG.warning("%s: ignorando %d geometrias nulas/vazias.", label, (~usable).sum())
    frame = frame.loc[usable].copy().reset_index(drop=True)
    if frame.empty:
        raise ValueError(f"{label}: nenhuma geometria utilizável.")
    if not frame.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError(f"{label}: são necessários polígonos ou multipolígonos.")
    invalid = ~frame.geometry.is_valid
    if invalid.any():
        LOG.warning("%s: reparando %d geometrias inválidas.", label, invalid.sum())
        repaired = frame.loc[invalid, "geometry"].make_valid()
        frame.loc[invalid, "geometry"] = repaired.apply(
            lambda geometry: unary_union(polygon_parts(geometry))
        )
        frame = frame.loc[~frame.geometry.is_empty].copy()
    if frame.empty:
        raise ValueError(f"{label}: nenhum polígono permaneceu após o reparo.")
    return frame


def select_tiles(aoi_path: Path, grid_path: Path, field: str | None = None) -> gpd.GeoDataFrame:
    aoi = read_polygons(aoi_path, "Área de interesse")
    grid = read_polygons(grid_path, "Quadrículas")
    if field is None:
        field = next((name for name in ("cd_quadric", "cd_quadricula", "qmdt_cod") if name in grid), None)
    if field is None or field not in grid:
        raise ValueError("Campo do código não encontrado. Informe --campo-codigo. "
                         f"Campos disponíveis: {', '.join(grid.columns)}")
    if aoi.crs != grid.crs:
        LOG.info("Reprojetando a área de interesse de %s para %s.", aoi.crs, grid.crs)
        aoi = aoi.to_crs(grid.crs)
    # Interseção real das geometrias, inclusive contato na borda. Um corredor
    # pode cruzar várias folhas, e uma folha pode cruzar vários corredores.
    matches = gpd.sjoin(grid, aoi[["geometry"]], how="inner", predicate="intersects")
    selected = grid.loc[grid.index.isin(matches.index)].copy()
    selected["quadricula"] = selected[field].astype("string").str.strip()
    valid_codes = selected["quadricula"].str.fullmatch(r"\d{4}-\d{3}").fillna(False)
    if not valid_codes.all():
        raise ValueError(f"Códigos de quadrícula inválidos: {selected.loc[~valid_codes, field].tolist()}")
    if "an_levanta" in selected and not selected["an_levanta"].eq(2020).all():
        raise ValueError("A seleção contém folhas de outro ano ou sem ano. Use a grade de 2020.")
    # Dissolve também preserva a geometria se um mesmo código tiver várias partes.
    if selected["quadricula"].duplicated().any():
        selected = selected.dissolve(by="quadricula", as_index=False, aggfunc="first")
    selected = selected.sort_values("quadricula").reset_index(drop=True)
    LOG.info("%d polígonos de interesse; %d folhas na grade; %d quadrículas selecionadas.",
             len(aoi), len(grid), len(selected))
    return selected


def download_url(code: str, product: str) -> str:
    return f"{PORTAL}/Download/File/{LAYERS[product]}?" + urlencode(
        {"key": "cd_quadricula", "value": code}
    )


def make_plan(tiles: gpd.GeoDataFrame, products: list[str], output: Path) -> list[dict]:
    return [
        {"quadricula": code, "produto": product, "ano": 2020,
         "url": download_url(code, product),
         "arquivo": str(output / f"{product}_2020" / f"{code}.zip")}
        for code in tiles["quadricula"] for product in products
    ]


def save_plan(tiles: gpd.GeoDataFrame, plan: list[dict], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # GeoPackage mantém nomes completos dos campos e pode ser aberto no QGIS.
    tiles.to_file(output / "quadriculas_selecionadas.gpkg", layer="quadriculas", driver="GPKG")
    tiles.drop(columns="geometry").to_csv(
        output / "quadriculas_selecionadas.csv", index=False, encoding="utf-8-sig"
    )
    with (output / "plano_download.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["quadricula", "produto", "ano", "url", "arquivo"])
        writer.writeheader()
        writer.writerows(plan)


def validate_zip(path: Path) -> None:
    """Confere diretório ZIP, CRC de todos os membros e presença de pontos LAS/LAZ."""
    try:
        with zipfile.ZipFile(path) as archive:
            point_files = [name for name in archive.namelist() if name.lower().endswith((".laz", ".las"))]
            if not point_files:
                raise DownloadError("O ZIP não contém nenhum arquivo LAS/LAZ.")
            bad = archive.testzip()
            if bad:
                raise DownloadError(f"CRC inválido no membro {bad}.")
            for name in point_files:
                with archive.open(name) as member:
                    if member.read(4) != b"LASF":
                        raise DownloadError(f"Cabeçalho LAS/LAZ inválido em {name}.")
    except (zipfile.BadZipFile, EOFError, RuntimeError, zlib.error, NotImplementedError) as error:
        raise DownloadError(f"ZIP inválido: {error}") from error


def transfer(session: requests.Session, url: str, partial: Path, timeout: float) -> int:
    """Retoma com Range; reinicia se o servidor responder com o arquivo inteiro."""
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    with session.get(url, headers=headers, stream=True, timeout=(15, timeout)) as response:
        # Um .part pode já estar completo se a execução parou antes da validação.
        if response.status_code == 416:
            total_match = re.fullmatch(r"bytes \*/(\d+)", response.headers.get("Content-Range", ""))
            if offset and total_match and offset == int(total_match[1]):
                try:
                    validate_zip(partial)
                except DownloadError:
                    partial.unlink(missing_ok=True)
                    raise
                return offset
            partial.unlink(missing_ok=True)
            raise DownloadError("Range recusado; a próxima tentativa começará do início.")
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if any(kind in content_type for kind in ("text/", "html", "json", "xml")):
            raise DownloadError(f"O servidor retornou {content_type}, em vez de um ZIP: {url}")
        if response.status_code == 206:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if (not match or int(match[1]) != offset or int(match[2]) < offset
                    or int(match[2]) >= int(match[3])):
                partial.unlink(missing_ok=True)
                raise DownloadError("Content-Range incompatível com o arquivo parcial.")
            total = int(match[3])
            expected_body = int(match[2]) - offset + 1
            mode = "ab" if offset else "wb"
        elif response.status_code == 200:
            if offset:
                LOG.info("Servidor enviou o arquivo inteiro; reiniciando %s.", partial.name)
            offset, mode = 0, "wb"
            length = response.headers.get("Content-Length")
            total = int(length) if length is not None else None
            expected_body = total
        else:
            raise DownloadError(f"Status HTTP inesperado: {response.status_code}")
        if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
            raise DownloadError("Resposta com compressão HTTP inesperada; tamanho/Range não são confiáveis.")
        received = 0
        last_progress = time.monotonic()
        with partial.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                # Protege também contra páginas HTML com Content-Type incorreto.
                if offset == 0 and received == 0 and chunk[:4] != b"PK\x03\x04":
                    partial.unlink(missing_ok=True)
                    raise DownloadError("A resposta não começa com a assinatura de um ZIP.")
                handle.write(chunk)
                received += len(chunk)
                if time.monotonic() - last_progress >= 5:
                    LOG.info("  %.1f MiB recebidos%s", (offset + received) / 2**20,
                             f" de {total / 2**20:.1f} MiB" if total is not None else "")
                    last_progress = time.monotonic()
        if expected_body is not None and received != expected_body:
            raise DownloadError(f"Transferência incompleta: {received} de {expected_body} bytes recebidos.")
        size = partial.stat().st_size
        if total is not None and size != total:
            raise DownloadError(f"Arquivo parcial: {size} de {total} bytes.")
        return size


def download(session: requests.Session, task: dict, attempts: int, timeout: float,
             previous: Path | None = None) -> tuple[str, int]:
    destination = Path(task["arquivo"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            validate_zip(destination)
            return "existente", destination.stat().st_size
        except DownloadError as error:
            LOG.warning("%s será substituído: %s", destination.name, error)
    partial = destination.with_suffix(".zip.part")
    # Retoma localmente um download completo que ainda não foi renomeado.
    if partial.exists():
        try:
            validate_zip(partial)
        except DownloadError:
            pass
        else:
            partial.replace(destination)
            return "baixado", destination.stat().st_size
    if previous is not None and previous.resolve() != destination.parent.parent.resolve():
        original = previous / destination.parent.name / destination.name
        if original.is_file():
            try:
                validate_zip(original)
            except DownloadError as error:
                LOG.warning("Arquivo antigo inválido, não será copiado: %s: %s", original, error)
            else:
                LOG.info("  Copiando arquivo já baixado para o novo destino: %s", original)
                shutil.copyfile(original, partial)
                validate_zip(partial)
                partial.replace(destination)
                return "reaproveitado", destination.stat().st_size
        original_partial = original.with_suffix(".zip.part")
        if not partial.exists() and original_partial.is_file():
            LOG.info("  Copiando download parcial para o novo destino: %s", original_partial)
            shutil.copyfile(original_partial, partial)
    for attempt in range(1, attempts + 1):
        try:
            size = transfer(session, task["url"], partial, timeout)
            try:
                validate_zip(partial)
            except DownloadError:
                # CRC identifica inclusive mistura de versões após uma retomada.
                partial.unlink(missing_ok=True)
                raise
            partial.replace(destination)
            return "baixado", size
        except (requests.RequestException, DownloadError) as error:
            if attempt == attempts:
                raise
            LOG.warning("Tentativa %d/%d falhou: %s", attempt, attempts, error)
            time.sleep(min(2 ** attempt, 30))
    raise AssertionError("Número de tentativas inválido")


def append_result(output: Path, task: dict, status: str, size: int, detail: str = "") -> None:
    path = output / "resultado_downloads.csv"
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "data_utc", "quadricula", "produto", "ano", "status", "bytes", "detalhe", "url", "arquivo"
        ])
        if new:
            writer.writeheader()
        writer.writerow({**task, "data_utc": datetime.now(timezone.utc).isoformat(),
                         "status": status, "bytes": size, "detalhe": detail})


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("O valor precisa ser maior que zero.")
    return number


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aoi", type=Path, default=ROOT / "files/corredor_verde/corredor_verde.shp",
                        help="Shapefile dos polígonos de interesse.")
    parser.add_argument("--grade", type=Path,
                        default=ROOT / "files/quadricula_folha_mdt_mds_2020/quadricula_folha_mdt_mds_2020.shp",
                        help="Shapefile da articulação MDT/MDS de 2020.")
    parser.add_argument("--campo-codigo", help="Campo dos códigos (detectado automaticamente por padrão).")
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Pasta dos ZIPs e relatórios (padrão: {DEFAULT_OUTPUT}).")
    parser.add_argument("--reaproveitar-de", type=Path, default=PREVIOUS_OUTPUT,
                        help="Copia ZIPs válidos e parciais da pasta antiga sem apagar os originais.")
    parser.add_argument("--tipo", type=str.upper, choices=["MDT", "MDS", "AMBOS"], default="AMBOS")
    parser.add_argument("--listar", action="store_true", help="Exporta seleção e plano sem acessar a internet.")
    parser.add_argument("--quadricula", nargs="+", help="Restringe a códigos que também intersectam a AOI.")
    parser.add_argument("--limite", type=positive_int, help="Limita a quantidade de quadrículas, em ordem de código.")
    parser.add_argument("--tentativas", type=positive_int, default=4)
    parser.add_argument("--timeout", type=positive_int, default=120, help="Tempo máximo sem receber dados, em segundos.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        tiles = select_tiles(args.aoi, args.grade, args.campo_codigo)
        if args.quadricula:
            missing = sorted(set(args.quadricula) - set(tiles["quadricula"]))
            if missing:
                raise ValueError("Códigos ausentes da interseção: " + ", ".join(missing))
            tiles = tiles.loc[tiles["quadricula"].isin(args.quadricula)].copy()
        if args.limite:
            tiles = tiles.head(args.limite).copy()
        if tiles.empty:
            LOG.info("Nenhuma quadrícula intersecta a área de interesse. Nenhum download solicitado.")
            return 0
        products = list(LAYERS) if args.tipo == "AMBOS" else [args.tipo]
        output = args.saida.expanduser().resolve()
        if output.is_relative_to(EXTERNAL_DRIVE) and not EXTERNAL_DRIVE.is_mount():
            raise ValueError(f"HD externo não está montado em {EXTERNAL_DRIVE}. Conecte-o antes de continuar.")
        previous = args.reaproveitar_de.expanduser().resolve()
        plan = make_plan(tiles, products, output)
        save_plan(tiles, plan, output)
        LOG.info("Plano: %d quadrículas, %d arquivos (%s, 2020).", len(tiles), len(plan), ", ".join(products))
        LOG.info("Seleção, URLs e destino de cada arquivo: %s", output)
        if args.listar:
            LOG.info("Somente listagem: nenhum arquivo LiDAR foi baixado.")
            return 0
        counts = {"baixado": 0, "reaproveitado": 0, "existente": 0, "falha": 0}
        with requests.Session() as session:
            session.headers.update({"User-Agent": "GeoSampa-AOI-downloader/1.0", "Accept-Encoding": "identity"})
            for index, task in enumerate(plan, 1):
                LOG.info("[%d/%d] %s %s", index, len(plan), task["produto"], task["quadricula"])
                try:
                    status, size = download(session, task, args.tentativas, args.timeout, previous)
                    append_result(output, task, status, size)
                    counts[status] += 1
                    LOG.info("  %s: %.1f MiB", status, size / 2**20)
                except (requests.RequestException, DownloadError, OSError) as error:
                    # Não tentar os próximos arquivos nem escrever outro resultado
                    # no mesmo disco cheio. O .part fica disponível para a retomada.
                    if isinstance(error, OSError) and error.errno in {errno.ENOSPC, errno.EDQUOT}:
                        raise
                    counts["falha"] += 1
                    LOG.error("  Falha: %s", error)
                    append_result(output, task, "falha", 0, str(error))
        LOG.info("Resultado: %d baixados, %d copiados da pasta antiga, %d já existentes, %d falhas.",
                 counts["baixado"], counts["reaproveitado"], counts["existente"], counts["falha"])
        if counts["falha"]:
            LOG.error("Consulte resultado_downloads.csv. Execute o mesmo comando para tentar novamente.")
            return 1
        return 0
    except KeyboardInterrupt:
        LOG.warning("Interrompido. Execute o mesmo comando para retomar; parciais ficam em .zip.part.")
        return 130
    except OSError as error:
        if error.errno in {errno.ENOSPC, errno.EDQUOT}:
            LOG.error("Sem espaço no destino %s. Execução interrompida. Libere espaço ou informe "
                      "outra pasta com --saida e execute novamente. Os arquivos parciais foram preservados.",
                      args.saida)
        else:
            LOG.error("%s", error)
        return 1
    except (ValueError, requests.RequestException) as error:
        LOG.error("%s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
