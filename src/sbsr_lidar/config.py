"""Configuração estrita e caminhos resolvidos sem criar diretórios."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
Fraction = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Tile = Annotated[str, Field(pattern=r"^\d{4}-\d{3}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Paths(Model):
    project_root: Path
    data_root: Path
    mount_root: Path
    output_root: Path
    runs_root: Path
    state_file: Path
    corridors: Path
    grid: Path
    protocol_file: Path
    downloader_script: Path | None = None


class Pilot(Model):
    corridor_field: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    core_tiles: list[Tile] = Field(min_length=1)
    context_tiles: list[Tile] = Field(default_factory=list)
    sensitivity_tiles: list[Tile] = Field(default_factory=list)
    adversarial_corridor: str
    adversarial_tile: Tile
    halo_m: NonNegative
    measurement_domain: Literal["original_polygon"]

    @model_validator(mode="after")
    def distinct_tiles(self):
        for key in ("core_tiles", "context_tiles", "sensitivity_tiles"):
            values = getattr(self, key)
            if len(values) != len(set(values)):
                raise ValueError(f"{key}: códigos duplicados")
        if set(self.core_tiles) & set(self.context_tiles):
            raise ValueError("Folhas de núcleo e contexto devem ser disjuntas")
        return self


class Grid(Model):
    epsg: PositiveInt
    resolution_m: Positive
    origin_x: float = Field(allow_inf_nan=False)
    origin_y: float = Field(allow_inf_nan=False)
    nodata: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def nodata_not_zero(self):
        if self.nodata >= 0:
            raise ValueError("NoData deve ser negativo e distinto de altura zero")
        return self


class Vegetation(Model):
    classes: list[Annotated[int, Field(ge=0, le=255, strict=True)]] = Field(min_length=1)
    minimum_height_m: Positive
    connectivity: Literal[4, 8]
    minimum_points_per_cell: PositiveInt = 1
    geometry_radius_m: Positive = 1.5
    geometry_neighbors: Annotated[int, Field(ge=6, le=64, strict=True)] = 32
    geometry_min_neighbors: Annotated[int, Field(ge=3, le=64, strict=True)] = 6
    geometry_voxel_m: Positive = 0.10
    max_geometry_points: PositiveInt = 2_000_000
    geometry_query_cells: Annotated[int, Field(gt=0, le=20_000, strict=True)] = 4096
    planar_threshold: Fraction = 0.80
    planar_max_roughness_m: Positive = 0.15
    structure_fraction_threshold: Fraction = 0.50
    linear_threshold: Fraction = 0.90
    thin_max_xy_spread_m: Positive = 0.50
    thin_min_single_return_fraction: Fraction = 0.90
    qa_sample_cells: PositiveInt = 300

    @model_validator(mode="after")
    def mask_parameters(self):
        if set(self.classes)!={3,4,5} or len(self.classes)!=3:
            raise ValueError("Baseline do piloto exige classes 3/4/5, incluindo classe 3")
        if self.geometry_min_neighbors>self.geometry_neighbors:
            raise ValueError("Mínimo de vizinhos geométricos excede o máximo")
        return self


class Terrain(Model):
    method: Literal["pending_qc", "tin", "idw"]
    maximum_distance_m: Positive
    apply_geoid_correction: Literal[False]
    idw_neighbors: Annotated[int, Field(ge=3, le=32, strict=True)] = 8
    idw_min_neighbors: Annotated[int, Field(ge=3, le=32, strict=True)] = 3
    idw_power: Positive = 2.0
    triangle_edge_radius_factor: Positive = 2.0
    expected_vertical_datum: str = "Maregr.Imbituba(SC)-MAPGEO2015"
    coordinate_key_m: Positive = 0.001
    maximum_xy_z_spread_m: Positive = 0.10
    max_support_points: PositiveInt = 1_000_000
    query_points: Annotated[int, Field(gt=0, le=100_000, strict=True)] = 50_000
    validation_fraction: Annotated[float, Field(gt=0, lt=0.5)] = 0.10
    validation_block_m: Positive = 10.0
    validation_max_points: PositiveInt = 20_000
    minimum_common_validation: PositiveInt = 50
    height_sample_per_class: PositiveInt = 10_000
    negative_warning_m: float = Field(default=-1.0, lt=0, allow_inf_nan=False)
    extreme_height_m: Positive = 80.0

    @model_validator(mode="after")
    def consistent_neighbors(self):
        if self.idw_min_neighbors > self.idw_neighbors:
            raise ValueError("Número mínimo de vizinhos IDW excede o máximo")
        return self


class Segmentation(Model):
    length_m: Positive
    station_spacing_m: Positive
    section_cover_threshold: Fraction
    boundary_spacing_m: Positive = 2.0
    axis_node_snap_tolerance_m: Positive = 0.00001
    maximum_boundary_sites: PositiveInt = 20_000
    terminal_spur_maximum_m: NonNegative = 25.0
    terminal_spur_radius_factor: Positive = 2.5
    minimum_axis_length_m: Positive = 25.0
    minimum_axis_aspect_ratio: Positive = 3.0
    tangent_half_window_m: Positive = 1.0
    maximum_stations_per_part: PositiveInt = 10_000
    maximum_grid_cells_per_scale: PositiveInt = 10_000
    area_tolerance_m2: Positive = 0.0001


class Indicators(Model):
    height_estimand: Literal['normalized_vegetation_returns'] = 'normalized_vegetation_returns'
    quantile_method: Literal['linear'] = 'linear'
    batch_records: Annotated[int, Field(gt=0, le=250_000, strict=True)] = 65_536
    maximum_stored_height_values: PositiveInt = 6_000_000
    maximum_units: PositiveInt = 2_000
    include_I8: Literal[False] = False
    include_I9_I10: Literal[False] = False


class Comparison(Model):
    primary_vertical_weight: Fraction = 0.5
    primary_top_fraction: Annotated[float, Field(gt=0, le=1)] = 0.20
    top_fractions: list[Annotated[float, Field(gt=0, le=1)]] = [0.10, 0.20, 0.30]
    score_tie_decimals: Annotated[int, Field(ge=8, le=14, strict=True)] = 12
    minimum_spearman_units: Annotated[int, Field(ge=3, strict=True)] = 3
    minimum_top_k_for_jaccard: Annotated[int, Field(ge=5, strict=True)] = 5
    similar_cover_tolerance: Fraction = 0.05
    maximum_observed_area_ratio: Annotated[float, Field(ge=1, allow_inf_nan=False)] = 2.0
    pair_boundary_epsilon: NonNegative = 1e-12
    maximum_units_per_cohort: PositiveInt = 500
    maximum_pair_candidates: PositiveInt = 250_000
    minimum_independent_groups_for_surrogates: Annotated[int, Field(ge=3, strict=True)] = 6
    diagnostic_spatial_block_m: Positive = 200.0

    @model_validator(mode='after')
    def fixed_top_sets(self):
        if len(self.top_fractions) != len(set(self.top_fractions)) or self.primary_top_fraction not in self.top_fractions:
            raise ValueError('Frações top devem ser distintas e incluir a principal')
        return self


class Support(Model):
    minimum_observed_fraction: Annotated[float, Field(gt=0, le=1)]
    minimum_unit_area_m2: Positive
    minimum_canopy_area_m2: Positive
    minimum_vegetation_returns: PositiveInt


class Sensitivity(Model):
    resolutions_m: list[Positive] = Field(min_length=1)
    halos_m: list[NonNegative] = Field(min_length=1)
    lengths_m: list[Positive] = Field(min_length=1)
    heights_m: list[Positive] = Field(min_length=1)
    terrain_distances_m: list[Positive] = Field(min_length=1)
    section_thresholds: list[Fraction] = Field(min_length=1)
    vertical_weights: list[Fraction] = Field(min_length=1)


class Robustness(Model):
    """Orçamento do recorte, sem habilitar ampliação municipal."""
    maximum_roi_records: PositiveInt = 5_000_000
    thinning_fractions: list[Annotated[float, Field(gt=0, lt=1)]] = Field(default_factory=lambda: [.5, .25])
    thinning_seed_offsets: list[Annotated[int, Field(ge=0, strict=True)]] = Field(default_factory=lambda: [0, 1, 2])
    maximum_scenarios: Annotated[int, Field(ge=1, le=50)] = 32


class Resources(Model):
    workers: PositiveInt
    chunk_points: Annotated[int, Field(gt=0, le=2_000_000, strict=True)]
    max_ram_gib: Positive
    min_output_free_gib: Positive
    min_local_free_gib: Positive
    max_pilot_tiles: PositiveInt
    smoke_points: Annotated[int, Field(gt=0, le=10_000, strict=True)]
    seed: Annotated[int, Field(ge=0, strict=True)]


class Tools(Model):
    pdal: str = Field(min_length=1)
    gdalinfo: str = Field(min_length=1)
    timeout_seconds: PositiveInt


class InputPreparation(Model):
    grid_code_field: str = "cd_quadric"
    edge_width_m: Positive = 2.0
    excluded_noise_classes: list[Annotated[int, Field(ge=0, le=255, strict=True)]] = [7, 18]
    download_attempts: PositiveInt = 4
    download_timeout_seconds: PositiveInt = 120
    max_new_downloads_per_case: PositiveInt = 2
    adversarial_context_policy: Literal["clip_to_tile"] = "clip_to_tile"


class Reference(Model):
    window_size_m: Positive = 20.0
    main_windows: PositiveInt = 12
    adversarial_windows: PositiveInt = 8
    minimum_context_area_m2: Positive = 1.0
    minimum_regular_context_fraction: Fraction = 0.25
    minimum_regular_measurement_fraction: Fraction = 0.125
    double_annotation_fraction: Annotated[float, Field(gt=0, le=1)] = 0.25
    low_height_range_m: tuple[NonNegative, Positive] = (0.25, 2.0)
    high_height_m: Positive = 20.0
    rgb_resolution_m: Positive = 0.5
    profile_half_width_m: Positive = 1.0
    max_points_per_window: PositiveInt = 100_000
    qgis_python: str = "/usr/bin/python3"

    @model_validator(mode="after")
    def bounded(self):
        if self.main_windows+self.adversarial_windows>40:
            raise ValueError("Referência do piloto limitada a 40 janelas")
        if self.low_height_range_m[0]>=self.low_height_range_m[1]:
            raise ValueError("Intervalo de altura baixa inválido")
        if self.window_size_m/self.rgb_resolution_m>200:
            raise ValueError("Grade RGB da janela excede orçamento")
        return self


class Config(Model):
    schema_version: Literal["0.1.0"]
    protocol_version: str = Field(min_length=1)
    paths: Paths
    pilot: Pilot
    grid: Grid
    vegetation: Vegetation
    terrain: Terrain
    segmentation: Segmentation
    support: Support
    sensitivity: Sensitivity
    resources: Resources
    tools: Tools
    input_preparation: InputPreparation = Field(default_factory=InputPreparation)
    reference: Reference = Field(default_factory=Reference)
    indicators: Indicators = Field(default_factory=Indicators)
    comparison: Comparison = Field(default_factory=Comparison)
    robustness: Robustness = Field(default_factory=Robustness)

    @model_validator(mode="after")
    def limits(self):
        p = self.paths
        if not p.data_root.is_relative_to(p.mount_root):
            raise ValueError("data_root precisa estar no disco configurado")
        if p.output_root == p.data_root or not p.output_root.is_relative_to(p.data_root):
            raise ValueError("output_root deve ser subpasta própria de data_root")
        for name in ("MDS_2020", "MDT_2020"):
            if p.output_root.is_relative_to(p.data_root / name):
                raise ValueError("Produtos não podem ser gravados nas pastas originais")
        if p.runs_root.is_relative_to(p.data_root):
            raise ValueError("runs_root deve permanecer fora dos dados originais")
        if not p.runs_root.is_relative_to(p.project_root):
            raise ValueError("runs_root deve ser subpasta do projeto")
        if not p.state_file.is_relative_to(p.project_root):
            raise ValueError("state_file deve permanecer no projeto")
        if p.runs_root == p.project_root or p.state_file.is_relative_to(p.project_root / "files"):
            raise ValueError("Estado/execuções precisam de diretórios próprios, separados dos insumos")
        if p.output_root.is_relative_to(p.runs_root) or p.runs_root.is_relative_to(p.output_root):
            raise ValueError("Produtos externos e registros locais precisam ser separados")
        n = len(set(self.pilot.core_tiles + self.pilot.context_tiles + self.pilot.sensitivity_tiles
                    + [self.pilot.adversarial_tile]))
        if n > self.resources.max_pilot_tiles:
            raise ValueError(f"Plano do piloto ({n}) excede max_pilot_tiles")
        if self.resources.workers > 2:
            raise ValueError("Esta configuração de piloto permite no máximo 2 trabalhadores")
        # Margem conservadora para estruturas temporárias, não previsão de pico real.
        chunk_gib = self.resources.workers * self.resources.chunk_points * 512 / 2**30
        if chunk_gib > self.resources.max_ram_gib:
            raise ValueError("Blocos/trabalhadores excedem o orçamento de RAM")
        if self.indicators.maximum_stored_height_values*16 > self.resources.max_ram_gib*2**30:
            raise ValueError("Reserva para quantis exatos excede orçamento de RAM")
        if self.comparison.primary_vertical_weight not in self.sensitivity.vertical_weights:
            raise ValueError('Peso vertical principal precisa constar dos cenários do protocolo')
        if self.segmentation.station_spacing_m > self.segmentation.length_m:
            raise ValueError("Espaçamento de estações maior que o segmento")
        if any(x < self.segmentation.station_spacing_m for x in self.sensitivity.lengths_m):
            raise ValueError("Escala de sensibilidade menor que o espaçamento de estações")
        if not all(math.isfinite(x) for x in self.support.model_dump().values()):
            raise ValueError("Suporte contém valor não finito")
        return self


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError(f"Chave YAML duplicada: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_config(path: Path) -> Config:
    path = path.expanduser().resolve()
    try:
        with path.open(encoding="utf-8") as handle:
            raw = yaml.load(handle, Loader=UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"YAML inválido: {error}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("paths"), dict):
        raise ValueError("YAML precisa conter um mapa paths")
    raw = dict(raw)
    raw["paths"] = dict(raw["paths"])
    for key, value in raw["paths"].items():
        if not isinstance(value, str):
            raise ValueError(f"paths.{key} deve ser texto")
        p = Path(value).expanduser()
        raw["paths"][key] = (p if p.is_absolute() else path.parent / p).resolve()
    return Config.model_validate(raw)
