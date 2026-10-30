"""Planejamento vetorial pós-piloto; não executa a amostra nem cria rótulos."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Literal

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
import shapely
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import cloud_path
from .spatial_units import polygon_parts


class StudyDesign(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schema_version: Literal['0.1.0']
    protocol_version: Literal['0.2.0']
    status: Literal['frozen_conditional_post_pilot']
    execution_enabled: Literal[False]
    seed: int = Field(ge=0)
    mode: Literal['amostra_cientifica']
    municipal_mode_enabled: Literal[False]
    target_corridors: int = Field(ge=8, le=12)
    development_corridors: int = Field(ge=1)
    evaluation_corridors: int = Field(ge=6)
    target_units_per_corridor: int = Field(ge=1)
    minimum_geometric_units_per_corridor: int = Field(ge=1)
    minimum_actual_evaluation_units: int = Field(ge=1)
    target_evaluation_units: int = Field(ge=1)
    maximum_actual_evaluation_units: int = Field(ge=1)
    primary_scale_m: Literal[50]
    block_distance_m: float = Field(gt=0)
    block_sensitivity_m: list[float] = Field(min_length=1)
    stratification: Literal['centroid_geographic_quadrants']
    status_field: str
    included_status: str
    type_field: str
    included_type: str
    exclude_legacy_reserved_groups: Literal[True]
    reference_windows_per_corridor: int = Field(gt=0)
    double_annotation_fraction: float = Field(gt=0, le=1)
    minimum_provisional_evaluation_groups: int = Field(ge=6)
    cpu_workers: Literal[1]
    maximum_ram_gib: float = Field(gt=0)
    external_free_reserve_gib: float = Field(gt=0)
    maximum_tiles_per_computational_window: int = Field(gt=0)
    maximum_ground_vertices_per_window: int = Field(gt=0)
    maximum_roi_records_per_window: int = Field(gt=0)
    cost_uncertainty_factor: float = Field(ge=1)
    disk_safety_factor: float = Field(ge=1)

    @model_validator(mode='after')
    def coherent(self):
        if self.development_corridors+self.evaluation_corridors != self.target_corridors:
            raise ValueError('Papéis não somam o total de corredores')
        if self.target_evaluation_units != self.evaluation_corridors*self.target_units_per_corridor:
            raise ValueError('Meta de unidades incompatível com corredores de avaliação')
        if not self.minimum_actual_evaluation_units <= self.target_evaluation_units <= self.maximum_actual_evaluation_units:
            raise ValueError('Faixa de unidades incoerente')
        if self.block_distance_m not in self.block_sensitivity_m or min(self.block_sensitivity_m) <= 0:
            raise ValueError('Distâncias de bloco incoerentes')
        return self


def load_design(path):
    return StudyDesign.model_validate(yaml.safe_load(Path(path).read_text(encoding='utf-8')))


def connected_blocks(frame, distance):
    """Componentes transitivos de polígonos próximos, sem certificar independência."""
    if distance < 0 or frame.corridor_id.duplicated().any():
        raise ValueError('Distância/IDs inválidos')
    ids = frame.corridor_id.astype(str).to_numpy()
    parent = list(range(len(frame)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    geometries = frame.geometry.to_numpy()
    for a, b in shapely.STRtree(geometries).query(geometries, predicate='dwithin', distance=distance).T:
        if a < b: parent[find(int(a))] = find(int(b))
    groups = {}
    for i, code in enumerate(ids): groups.setdefault(find(i), []).append(code)
    mapping = {}
    for members in groups.values():
        text = f'{distance:g}|'+'|'.join(sorted(members))
        key = 'B11_'+hashlib.sha256(text.encode()).hexdigest()[:14]
        mapping.update({code: key for code in members})
    return mapping


def geometric_units(geometry, scale, minimum_area):
    n = 0
    for part in polygon_parts(geometry):
        x0, y0, x1, y1 = part.bounds
        for x in range(math.floor(x0/scale), math.ceil(x1/scale)):
            for y in range(math.floor(y0/scale), math.ceil(y1/scale)):
                intersection = part.intersection(shapely.box(x*scale, y*scale, (x+1)*scale, (y+1)*scale))
                n += sum(p.area >= minimum_area for p in polygon_parts(intersection))
    return n


def priority(seed, identifier):
    return hashlib.sha256(f'{seed}|{identifier}'.encode()).hexdigest()


def choose_candidates(frame, design):
    """Ordem geográfica estratificada, sem ler cobertura, alturas ou escores."""
    eligible = frame.loc[frame.planning_eligible].sort_values(['selection_priority', 'corridor_id'])
    selected, used = [], set()
    strata = sorted(eligible.stratum.unique())
    # Uma volta por estrato; blocos já usados saem de todas as listas.
    while len(selected) < len(eligible):
        before = len(selected)
        for stratum in strata:
            candidates = eligible.loc[eligible.stratum.eq(stratum) & ~eligible.block_id.isin(used)]
            if len(candidates):
                row = candidates.iloc[0]
                selected.append(row.corridor_id); used.add(row.block_id)
        if len(selected) == before: break
    roles = []
    for order, code in enumerate(selected, 1):
        role = ('avaliacao' if order <= design.evaluation_corridors else
                'desenvolvimento' if order <= design.target_corridors else 'reserva')
        roles.append({'corridor_id': code, 'candidate_order': order, 'proposed_role': role,
            'selected_for_planning': order <= design.target_corridors,
            'target_units': design.target_units_per_corridor if order <= design.target_corridors else 0,
            'actual_eligible_units': None, 'actual_validated_units': None,
            'selection_status': 'proposed_not_executed; support_and_reference_pending'})
    return pd.DataFrame(roles, columns=['corridor_id', 'candidate_order', 'proposed_role', 'selected_for_planning',
        'target_units', 'actual_eligible_units', 'actual_validated_units', 'selection_status'])


def sampling_frame(config, design, reservation):
    frame = gpd.read_file(config.paths.corridors).rename(columns={config.pilot.corridor_field: 'corridor_id'})
    if frame.crs.to_epsg() != config.grid.epsg or not frame.geometry.is_valid.all() or frame.corridor_id.duplicated().any():
        raise ValueError('Quadro vetorial inválido')
    if set(frame.corridor_id) != set(reservation.corridor_id):
        raise ValueError('Reserva antiga difere do quadro atual')
    frame = frame.merge(reservation.rename(columns={'group_id': 'legacy_group_id', 'fold': 'legacy_fold'}), on='corridor_id', validate='1:1')
    frame['area_m2'] = frame.area
    frame['parts'] = [len(polygon_parts(g)) for g in frame.geometry]
    frame['potential_50m_units_area_only'] = [geometric_units(g, 50, config.support.minimum_unit_area_m2) for g in frame.geometry]
    protected = set(frame.loc[~frame.legacy_fold.eq('nao_atribuido'), 'corridor_id'])
    block_rows = []; summaries = []
    for distance in sorted(set(design.block_sensitivity_m)):
        mapping = connected_blocks(frame, distance)
        blocked = {mapping[code] for code in protected}
        for code in sorted(mapping):
            block_rows.append({'corridor_id': code, 'distance_m': distance, 'block_id': mapping[code],
                'contains_legacy_reserved_group': mapping[code] in blocked, 'independence_certified': False})
        if distance == design.block_distance_m:
            frame['block_id'] = frame.corridor_id.map(mapping)
            frame['legacy_proximity_excluded'] = frame.block_id.isin(blocked)
        potential = frame[design.status_field].eq(design.included_status) & frame[design.type_field].eq(design.included_type)
        potential &= ~frame.corridor_id.map(mapping).isin(blocked)
        potential &= frame.potential_50m_units_area_only >= design.minimum_geometric_units_per_corridor
        summaries.append({'distance_m': distance, 'total_blocks': len(set(mapping.values())),
            'candidate_corridors_geometric_only': int(potential.sum()),
            'candidate_blocks_geometric_only': len({mapping[code] for code in frame.loc[potential, 'corridor_id']}),
            'independence_certified': False})
    reasons = []
    for row in frame.to_dict('records'):
        reason = []
        if row[design.status_field] != design.included_status: reason.append('existing_case_not_replicable')
        if row[design.type_field] != design.included_type: reason.append('type_outside_arboreal_study_scope')
        if row['legacy_proximity_excluded']: reason.append('reserved_legacy_group_or_proximity_chain')
        if row['potential_50m_units_area_only'] < design.minimum_geometric_units_per_corridor: reason.append('insufficient_geometric_units_for_target')
        reasons.append(';'.join(reason) or None)
    frame['planning_exclusion_reason'] = reasons
    frame['planning_eligible'] = frame.planning_exclusion_reason.isna()
    centroids = frame.geometry.centroid
    cx = float(centroids.x[frame.planning_eligible].median()); cy = float(centroids.y[frame.planning_eligible].median())
    frame['stratum'] = np.where(centroids.x >= cx, 'E', 'W')+np.where(centroids.y >= cy, 'N', 'S')
    frame['selection_priority'] = [priority(design.seed, code) for code in frame.corridor_id]
    frame['LiDAR_support_assessed_for_new_corridor'] = False
    frame['canopy_quality_assessed_for_new_corridor'] = False
    ordered = choose_candidates(frame, design)
    proposal = frame.merge(ordered, on='corridor_id', how='left', validate='1:1')
    selected = proposal.loc[proposal.selected_for_planning.eq(True)].copy()
    adequate = len(selected) == design.target_corridors and selected.block_id.nunique() == design.target_corridors
    return frame, proposal, pd.DataFrame(block_rows), pd.DataFrame(summaries), {
        'total_frame_corridors': len(frame), 'scope': 'PROPOSTO/CORREDOR VERDE; geometric capacity and exclusion of pilot/reserved proximity groups',
        'candidate_corridors': int(frame.planning_eligible.sum()), 'candidate_blocks': frame.loc[frame.planning_eligible].block_id.nunique(),
        'proposed_corridors': len(selected), 'proposed_evaluation_corridors': int(selected.proposed_role.eq('avaliacao').sum()),
        'proposed_development_corridors': int(selected.proposed_role.eq('desenvolvimento').sum()),
        'adequate_geometric_frame': adequate, 'median_easting': cx, 'median_northing': cy,
        'probability_sample': False, 'selection_uses_3D_results': False, 'statistical_power_computed': False,
        'actual_eligible_units': None, 'independent_groups_certified': False}


def planned_tiles(config, proposal):
    grid = gpd.read_file(config.paths.grid)
    code_field = config.input_preparation.grid_code_field
    links = []
    for row in proposal.loc[proposal.candidate_order.le(12)].itertuples():
        context = row.geometry.buffer(config.pilot.halo_m)
        for i in grid.sindex.query(context, predicate='intersects'):
            tile = grid.iloc[i]
            links.append({'corridor_id': row.corridor_id, 'proposed_role': row.proposed_role,
                'tile': str(tile[code_field]), 'core': row.geometry.intersection(tile.geometry).area > 0,
                'context_intersection_area_m2': context.intersection(tile.geometry).area})
    files = []
    for tile in sorted({row['tile'] for row in links}):
        for product in ['MDT', 'MDS']:
            path = cloud_path(config, product, tile)
            archive_candidates = [config.paths.data_root/f'{product}_2020'/f'{tile}.zip',
                config.paths.output_root/'insumos_complementares'/f'{product}_2020'/f'{tile}.zip']
            archive = next((p for p in archive_candidates if p.is_file()), None)
            row = {'tile': tile, 'product': product, 'path': str(path), 'exists': path.is_file(),
                'compressed_bytes': None, 'declared_points': None, 'header_epsg': None,
                'verification_scope': 'header_only_no_point_decoding', 'needs_download_or_extraction': not path.is_file(),
                'available_archive': str(archive) if archive else None,
                'needs_extraction': not path.is_file() and archive is not None,
                'needs_download': not path.is_file() and archive is None}
            if path.is_file():
                row['compressed_bytes'] = path.stat().st_size
                with laspy.open(path, read_evlrs=False) as reader:
                    row['declared_points'] = int(reader.header.point_count)
                    row['header_epsg'] = reader.header.parse_crs().to_epsg()
            files.append(row)
    return pd.DataFrame(links), pd.DataFrame(files)
