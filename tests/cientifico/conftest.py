from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pytest
import yaml
from pyproj import CRS
from shapely.geometry import box

from sbsr_lidar.config import load_config
from sbsr_lidar.storage import atomic_write_json


@pytest.fixture
def config_file(tmp_path):
    template = Path(__file__).parents[2] / "configs/piloto.yaml"
    raw = yaml.safe_load(template.read_text())
    project = tmp_path / "project"
    mount = tmp_path / "external"
    data = mount / "data"
    project.mkdir()
    data.mkdir(parents=True)
    raw["paths"] = {"project_root": str(project), "mount_root": str(mount),
                    "data_root": str(data), "output_root": str(data / "experimento"),
                    "runs_root": str(project / "runs"), "state_file": str(project / "docs/state.json"),
                    "corridors": str(project / "files/corredores.gpkg"),
                    "grid": str(project / "files/grade.gpkg"),
                    "protocol_file": str(project / "docs/protocolo.md")}
    raw["resources"]["min_output_free_gib"] = 0.001
    raw["resources"]["min_local_free_gib"] = 0.001
    raw["resources"]["max_ram_gib"] = 0.5
    raw["resources"]["smoke_points"] = 2
    path = project / "piloto.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


@pytest.fixture
def config(config_file):
    return load_config(config_file)


@pytest.fixture
def inputs(config, monkeypatch):
    monkeypatch.setattr(Path, "is_mount", lambda p: p == config.paths.mount_root)
    config.paths.corridors.parent.mkdir()
    corridors = gpd.GeoDataFrame({"cd_identi0": [config.pilot.corridor_id]},
                                geometry=[box(330000, 7390000, 330002, 7390002)], crs=config.grid.epsg)
    corridors.to_file(config.paths.corridors)
    corridors.rename(columns={"cd_identi0": "cd_quadric"}).to_file(config.paths.grid)
    for code in set(config.pilot.core_tiles + [config.pilot.adversarial_tile]):
        for product in ["MDS", "MDT"]:
            path = config.paths.data_root / f"{product}_2020" / f"{product}_{code}_1000.laz"
            path.parent.mkdir(exist_ok=True)
            header = laspy.LasHeader(version="1.4", point_format=8)
            header.offsets = np.array([330000, 7390000, 0])
            header.scales = np.array([0.001]*3)
            header.add_crs(CRS.from_epsg(config.grid.epsg))
            cloud = laspy.LasData(header)
            cloud.x = np.array([330000.5, 330001.5, 330000.5, 330001.5])
            cloud.y = np.array([7390000.5, 7390000.5, 7390001.5, 7390001.5])
            cloud.z = np.array([0, 3, 8, 12])
            cloud.classification = np.array([2, 3, 4, 6], dtype=np.uint8)
            cloud.write(path)
    state = {"schema_version": "0.1.0", "etapa_atual": "01", "status": "etapa_01_concluida",
             "etapas": {"01": {"nome": "protocolo", "status": "concluida", "artefatos": []},
                        "02": {"nome": "ambiente", "status": "nao_iniciada", "artefatos": []}},
             "piloto_executado": False, "pipeline_cientifico_implementado": False,
             "campo_preexistente": {"preservar": True}}
    atomic_write_json(config.paths.state_file, state)
    config.paths.protocol_file.write_text("Protocolo sintético para testes de infraestrutura.\n")
    return config
