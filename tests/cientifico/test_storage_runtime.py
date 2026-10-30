import errno
from pathlib import Path

import pytest
from pydantic import ValidationError

from sbsr_lidar.runtime import Run, exclusive_lock
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import (atomic_write_json, cache_key, fingerprint, load_cache,
                               read_json, save_cache)


def test_atomic_failure_preserves_previous_file(tmp_path, monkeypatch):
    import sbsr_lidar.storage as storage
    path = tmp_path / "result.json"
    atomic_write_json(path, {"previous": True})
    def full_disk(*args):
        raise OSError(errno.ENOSPC, "No space")
    monkeypatch.setattr(storage.os, "replace", full_disk)
    with pytest.raises(OSError):
        atomic_write_json(path, {"previous": False})
    assert read_json(path) == {"previous": True}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.json"]


def test_nan_cannot_be_persisted_as_valid_result(tmp_path):
    with pytest.raises(ValueError):
        atomic_write_json(tmp_path/"result.json", {"height": float("nan")})
    assert not (tmp_path/"result.json").exists()


def test_cache_detects_same_size_content_tampering(tmp_path):
    output = tmp_path/"output.json"
    output.write_text('{"n": 1}')
    cache = tmp_path/"cache"
    save_cache(cache, "a"*64, "source", [output])
    assert load_cache(cache, "a"*64)
    output.write_text('{"n": 2}')
    assert load_cache(cache, "a"*64) is None


@pytest.mark.parametrize("change", ["config", "inputs", "code", "environment"])
def test_cache_identity_invalidates_on_real_changes(change):
    base = dict(command="smoke", config={"resolution": 1}, inputs=[{"sha256": "a"}],
                code="v1", environment={"laspy": "2"})
    initial = cache_key(**base)
    base[change] = {"changed": True} if change != "code" else "v2"
    assert cache_key(**base) != initial


def test_missing_or_incomplete_cache_not_reused(tmp_path):
    assert load_cache(tmp_path, "key") is None
    atomic_write_json(tmp_path/"key/entry.json", {"key": "key", "status": "running", "outputs": []})
    assert load_cache(tmp_path, "key") is None


def test_interruption_and_new_run_preserve_history_and_scientific_status(inputs):
    config = inputs
    arguments = (config.paths.runs_root, config.paths.state_file, "smoke", {}, [], {}, "a"*64)
    interrupted = Run(*arguments)
    interrupted.fail(KeyboardInterrupt(), interrupted=True)
    second = Run(*arguments)
    artifact = second.path/"ok.json"
    atomic_write_json(artifact, {"ok": True})
    second.finish([artifact])
    state = read_json(config.paths.state_file)
    assert [x["status"] for x in state["execucoes"]] == ["interrupted", "completed"]
    assert state["etapas"]["02"]["status"] == "nao_iniciada"
    assert state["piloto_executado"] is False
    assert state["campo_preexistente"] == {"preservar": True}
    for run in (interrupted, second):
        RunManifest.model_validate(read_json(run.path/"manifest.json"))


def test_lock_rejects_competing_writer(tmp_path):
    with exclusive_lock(tmp_path/"state.lock"):
        with pytest.raises(RuntimeError, match="bloqueio"):
            with exclusive_lock(tmp_path/"state.lock"):
                pytest.fail("Segundo escritor não deveria entrar")


def test_schema_rejects_false_completion(inputs):
    config = inputs
    run = Run(config.paths.runs_root, config.paths.state_file, "smoke", {}, [], {}, "a"*64)
    manifest = dict(run.manifest)
    manifest["status"] = "completed"
    with pytest.raises(ValidationError):
        RunManifest.model_validate(manifest)
    run.fail(RuntimeError("test cleanup"))
