import json
import shutil
from pathlib import Path

import pytest

from sbsr_lidar.cli import main
from sbsr_lidar.doctor import inspect_environment
from sbsr_lidar.smoke import header_and_sample, smoke
from sbsr_lidar.storage import fingerprint, read_json


@pytest.fixture
def native_tools():
    if not shutil.which("pdal") or not shutil.which("gdalinfo"):
        pytest.skip("Integração requer PDAL/GDAL CLI")


def test_real_format_header_reads_only_requested_points(inputs):
    config = inputs
    path = config.paths.data_root/"MDS_2020"/f"MDS_{config.pilot.core_tiles[0]}_1000.laz"
    before = fingerprint(path)
    result = header_and_sample(path, 2)
    assert result["declared_point_count"] == 4
    assert result["sample_points_read"] == 2
    assert result["epsg"] == config.grid.epsg
    assert result["sample_is_representative"] is False
    assert fingerprint(path) == before


@pytest.mark.parametrize("limit", [-1, 0, 10001, True])
def test_header_reader_cannot_accidentally_read_whole_cloud(tmp_path, limit):
    with pytest.raises(ValueError, match="limitado"):
        header_and_sample(tmp_path/"nonexistent.laz", limit)


def test_doctor_readonly_and_missing_context_is_not_fake_success(inputs, native_tools, monkeypatch):
    config = inputs
    # O sandbox pode negar escrita; aqui o teste isola a semântica do doctor.
    monkeypatch.setattr("sbsr_lidar.doctor.os.access", lambda *args: True)
    before = {str(p) for p in config.paths.project_root.rglob('*')}
    report = inspect_environment(config)
    assert report["ok"]
    assert report["context_ready"] is False
    assert report["warnings"] == 4
    assert report["scientific_pilot_executed"] is False
    assert before == {str(p) for p in config.paths.project_root.rglob('*')}
    assert not config.paths.output_root.exists()


def test_unmounted_drive_fails_without_creating_output(inputs, monkeypatch):
    monkeypatch.setattr(Path, "is_mount", lambda p: False)
    with pytest.raises(ValueError, match="montado"):
        smoke(inputs)
    assert not inputs.paths.output_root.exists()
    assert not inputs.paths.runs_root.exists()


def test_synthetic_native_io_cache_resume_and_raw_preservation(inputs, native_tools):
    config = inputs
    originals = {str(p): fingerprint(p) for p in config.paths.data_root.rglob('*.laz')}
    first = smoke(config)
    assert not first["cache_hit"]
    report = read_json(Path(first["report"]))
    assert report["real_input"]["sample_points_read"] == 2
    assert report["synthetic"]["zero_distinct_from_nodata"]
    assert report["synthetic"]["pdal_read_write"]
    assert report["synthetic"]["rasterio_read_pdal_output"]
    assert report["scientific_pilot_executed"] is False
    second = smoke(config)
    assert second["cache_hit"]
    assert second["report"] == first["report"]
    assert first["run_id"] != second["run_id"]
    assert read_json(Path(second["manifest"]))["source_run_id"] == first["run_id"]
    assert originals == {str(p): fingerprint(p) for p in config.paths.data_root.rglob('*.laz')}
    assert not config.paths.output_root.exists()


def test_doctor_report_cannot_overwrite_source(config_file):
    from sbsr_lidar.config import load_config
    config = load_config(config_file)
    # Destino deve ser validado mesmo que a checagem encontre insumos ausentes.
    code = config.paths.project_root / "source.py"
    code.write_text("preserve")
    assert main(["--config", str(config_file), "doctor", "--report", str(code)]) == 2
    assert code.read_text() == "preserve"


def test_cli_schema_and_invalid_configuration(config_file, capsys):
    assert main(["config-schema"]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Config"
    config_file.write_text("paths: []")
    assert main(["--config", str(config_file), "doctor"]) == 2
