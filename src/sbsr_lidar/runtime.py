"""Registro de execuções e retomada; não executa módulos científicos."""
from __future__ import annotations

import fcntl
import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .storage import atomic_write_json, read_json
from .schemas import ProjectState, RunManifest


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"Outra execução mantém o bloqueio: {path}") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def record_run(state_file: Path, run: dict) -> None:
    """Anexa o estado operacional sem marcar etapas científicas como concluídas."""
    with exclusive_lock(state_file.with_suffix(".json.lock")):
        state = ProjectState.model_validate(read_json(state_file)).model_dump(mode="json")
        records = state.setdefault("execucoes", [])
        record = {key: run.get(key) for key in ["run_id", "command", "status", "started_at", "finished_at"]}
        for index, item in enumerate(records):
            if item.get("run_id") == run["run_id"]:
                records[index] = record
                break
        else:
            records.append(record)
        state["ultima_execucao"] = record
        atomic_write_json(state_file, state)


class Run:
    def __init__(self, runs_root: Path, state_file: Path, command: str, config: dict,
                 inputs: list[dict], environment: dict, code_sha256: str, *, stage="02"):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:10]
        self.path = runs_root / self.run_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.state_file = state_file
        self.manifest = {"schema_version": "0.1.0", "run_id": self.run_id,
                         "command": command, "status": "running", "started_at": utc_now(),
                         "finished_at": None, "config": config, "inputs": inputs,
                         "environment": environment, "code_sha256": code_sha256,
                         "outputs": [], "cache_hit": False,
                         "scientific_pilot_executed": False}
        self.manifest["stage"] = stage
        self.log = logging.getLogger(f"sbsr_lidar.run.{self.run_id}")
        self.log.setLevel(logging.INFO)
        self.log.propagate = False
        self.handler = logging.FileHandler(self.path / "execution.log", encoding="utf-8")
        self.handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.log.addHandler(self.handler)
        self._closed = False
        try:
            self._checkpoint()
        except BaseException:
            self.close()
            raise
        self.log.info("Início: %s", command)

    def _checkpoint(self):
        checked = RunManifest.model_validate(self.manifest).model_dump(mode="json")
        atomic_write_json(self.path / "manifest.json", checked)
        record_run(self.state_file, self.manifest)

    def event(self, name: str, **details):
        self.log.info("%s %s", name, json.dumps(details, ensure_ascii=False, sort_keys=True))

    def finish(self, outputs: list[Path], *, cache_hit=False, source_run_id=None):
        self.manifest.update(status="completed", finished_at=utc_now(),
                             outputs=[str(p.resolve()) for p in outputs],
                             cache_hit=cache_hit, source_run_id=source_run_id)
        self._checkpoint()
        self.log.info("Concluído; cache_hit=%s", cache_hit)
        self.close()

    def fail(self, error: BaseException, interrupted=False):
        self.manifest.update(status="interrupted" if interrupted else "failed",
                             finished_at=utc_now(), error={"type": type(error).__name__, "message": str(error)})
        # Erro de persistência não pode ocultar a falha original (por exemplo disco cheio).
        try:
            self._checkpoint()
        except (OSError, ValueError, RuntimeError):
            pass
        self.close()

    def close(self):
        if not self._closed:
            self.handler.close()
            self.log.removeHandler(self.handler)
            self._closed = True
