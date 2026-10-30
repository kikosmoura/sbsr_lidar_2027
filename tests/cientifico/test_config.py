from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sbsr_lidar.config import load_config


def edit(path, section, key, value):
    raw = yaml.safe_load(path.read_text())
    raw[section][key] = value
    path.write_text(yaml.safe_dump(raw))


@pytest.mark.parametrize("section,key,value", [
    ("grid", "resolution_m", 0), ("resources", "workers", True),
    ("resources", "workers", 3), ("resources", "chunk_points", 50000000),
    ("resources", "max_ram_gib", 0.001), ("resources", "smoke_points", 10001),
    ("support", "minimum_observed_fraction", 1.1), ("grid", "nodata", 0),
    ("terrain", "apply_geoid_correction", True),
    ("pilot", "core_tiles", ["../../../x"]), ("pilot", "core_tiles", ["3313-333"]*2),
    ("grid", "resolucao_errada", 1),
])
def test_invalid_config_rejected(config_file, section, key, value):
    edit(config_file, section, key, value)
    with pytest.raises((ValidationError, ValueError)):
        load_config(config_file)


@pytest.mark.parametrize("target", ["data_root", "raw_mds", "outside"])
def test_cannot_write_products_to_raw_or_other_disk(config_file, target):
    raw = yaml.safe_load(config_file.read_text())
    data = Path(raw["paths"]["data_root"])
    value = {"data_root": data, "raw_mds": data/"MDS_2020/derived", "outside": data.parent/"elsewhere"}[target]
    edit(config_file, "paths", "output_root", str(value))
    with pytest.raises(ValidationError):
        load_config(config_file)


def test_relative_paths_use_yaml_directory_not_cwd(config_file, monkeypatch, tmp_path):
    edit(config_file, "paths", "corridors", "files/corredores.gpkg")
    monkeypatch.chdir(tmp_path)
    config = load_config(config_file)
    assert config.paths.corridors == config_file.parent / "files/corredores.gpkg"
    assert not config.paths.output_root.exists()


def test_pilot_budget_prevents_implicit_expansion(config_file):
    edit(config_file, "resources", "max_pilot_tiles", 2)
    with pytest.raises(ValidationError, match="excede"):
        load_config(config_file)


def test_duplicate_yaml_key_rejected(config_file):
    config_file.write_text(config_file.read_text() + '\nschema_version: "0.1.0"\n')
    with pytest.raises(ValueError, match="duplicada"):
        load_config(config_file)
