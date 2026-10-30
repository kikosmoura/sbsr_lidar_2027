"""Reuso do downloader existente e extração segura apenas de complementos."""
from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import zipfile
import zlib
from pathlib import Path, PurePosixPath

import requests

from .config import Config


def load_downloader(config: Config):
    path = config.paths.downloader_script
    if path is None or not path.is_file():
        raise ValueError("Configure paths.downloader_script para reutilizar o downloader existente")
    spec = importlib.util.spec_from_file_location("_sbsr_existing_downloader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_endpoint(session: requests.Session, url: str, timeout: int) -> dict:
    with session.get(url, stream=True, headers={"Range": "bytes=0-3", "Accept-Encoding": "identity"},
                     timeout=(15, timeout)) as response:
        response.raise_for_status()
        kind = response.headers.get("Content-Type", "").lower()
        first = next(response.iter_content(4), b"")
        if response.status_code not in {200, 206} or first != b"PK\x03\x04" or any(x in kind for x in ["html", "json", "text/"]):
            raise ValueError(f"Endpoint não retornou início de ZIP: HTTP {response.status_code}, {kind}")
        return {"url": url, "http_status": response.status_code, "content_type": kind,
                "zip_signature": True, "content_length": response.headers.get("Content-Length")}


def extract_laz(archive: Path, destination: Path, expected_name: str) -> dict:
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = PurePosixPath(info.filename.replace("\\", "/"))
            if name.is_absolute() or ".." in name.parts or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("ZIP contém caminho inseguro ou link simbólico")
        members = [info for info in z.infolist() if info.filename == expected_name and not info.is_dir()]
        if len(members) != 1:
            raise ValueError(f"ZIP não contém exatamente um membro esperado: {expected_name}")
        info = members[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            crc = 0
            size = 0
            with z.open(info) as source, tempfile.NamedTemporaryFile(dir=destination.parent, prefix=f".{destination.name}.",
                                                                  suffix=".part", delete=False) as target:
                temporary = Path(target.name)
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    if size == 0 and not block.startswith(b"LASF"):
                        raise ValueError("Membro não tem assinatura LAS")
                    target.write(block)
                    size += len(block)
                    crc = zlib.crc32(block, crc)
                target.flush()
                os.fsync(target.fileno())
            if size < 4 or size != info.file_size or crc != info.CRC:
                raise ValueError("Tamanho/CRC do LAZ extraído não confere")
            os.replace(temporary, destination)
            return {"archive": str(archive), "member": info.filename, "bytes": size, "crc32": crc}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def ensure_inputs(config: Config, plan: list[dict], *, download_missing: bool, event=lambda *a, **kw: None) -> list[dict]:
    if any(x["needs_download"] for x in plan) and not download_missing:
        raise ValueError("Há complementos ausentes; consulte plan-inputs e use --download-missing para completar apenas esse plano")
    downloader = None
    rows = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "SBSR-LiDAR-pilot/0.1", "Accept-Encoding": "identity"})
        for item in plan:
            row = dict(item)
            if row["selected_laz"]:
                row["origin"] = "original_laz" if row["selected_laz"] == row["original_laz"] else "complementary_laz"
            else:
                if row["needs_download"]:
                    downloader = downloader or load_downloader(config)
                    url = downloader.download_url(row["quadricula"], row["produto"])
                    row["endpoint_check"] = validate_endpoint(session, url, config.input_preparation.download_timeout_seconds)
                    event("download_start", product=row["produto"], tile=row["quadricula"])
                    try:
                        status, size = downloader.download(session, {"arquivo": row["destination_archive"], "url": url},
                            config.input_preparation.download_attempts, config.input_preparation.download_timeout_seconds)
                    except downloader.DownloadError as error:
                        raise RuntimeError(str(error)) from error
                    row.update(archive=row["destination_archive"], download_status=status, download_bytes=size, url=url)
                    event("download_complete", product=row["produto"], tile=row["quadricula"], bytes=size)
                destination = Path(row["complementary_laz"])
                row["extraction"] = extract_laz(Path(row["archive"]), destination, destination.name)
                row["selected_laz"] = str(destination)
                row["origin"] = "complementary_laz_extracted"
            rows.append(row)
    return rows
