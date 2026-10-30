"""Persistência atômica e identidade verificável de entradas/produtos."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path: Path) -> dict:
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError(f"Entrada mudou durante a leitura: {path}")
    return {"path": str(path.resolve()), "bytes": after.st_size, "sha256": digest}


def atomic_write_json(path: Path, payload: Any) -> None:
    # Serializar antes de criar arquivos: NaN e tipos inválidos não deixam resíduos.
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True,
                      allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Objeto JSON esperado: {path}")
    return value


def cache_key(*, command: str, config: dict, inputs: list[dict], code: str, environment: dict) -> str:
    identity = {"command": command, "config": config, "inputs": inputs,
                "code_sha256": code, "environment": environment}
    return hashlib.sha256(canonical_json(identity).encode()).hexdigest()


def load_cache(root: Path, key: str) -> dict | None:
    entry = root / key / "entry.json"
    if not entry.is_file():
        return None
    try:
        record = read_json(entry)
        if record.get("key") != key or record.get("status") != "completed" or not record.get("outputs"):
            return None
        for output in record["outputs"]:
            if fingerprint(Path(output["path"])) != output:
                return None
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cache(root: Path, key: str, run_id: str, outputs: list[Path]) -> None:
    atomic_write_json(root / key / "entry.json", {
        "schema_version": "0.1.0", "key": key, "status": "completed",
        "source_run_id": run_id, "outputs": [fingerprint(p) for p in outputs],
    })
