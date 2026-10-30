"""Protocolo exploratório explicitamente autorizado; não altera os gates da v0.2."""
from dataclasses import dataclass,asdict,replace
from pathlib import Path
from typing import Literal
import geopandas as gpd
import pandas as pd
from pydantic import BaseModel,ConfigDict,Field,model_validator
import yaml
from .domain import Domain,input_plan
from .storage import read_json,fingerprint


class CrownDesign(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    schema_version:Literal['0.1.0']
    protocol_version:Literal['0.3.0']
    mode:Literal['amostra_exploratoria_pycrown']
    external_reference_required_for_execution:Literal[False]
    external_accuracy_claims_enabled:Literal[False]
    municipal_mode_enabled:Literal[False]
    selection_protocol:Literal['0.2.0']
    halo_m:float=Field(ge=20,le=30)
    window_size_m:Literal[200]
    terrain_context_m:float=Field(ge=10,le=20)
    maximum_new_products:int=Field(ge=0,le=32)
    maximum_roi_records_per_window:int=Field(gt=0,le=5000000)
    maximum_ground_vertices_per_window:int=Field(gt=0,le=1000000)
    maximum_raster_cells:int=Field(gt=0,le=20000000)
    primary_resolution_m:Literal[1.0]
    resolutions_m:list[float]
    primary_height_m:Literal[3.0]
    primary_detection_radius_m:Literal[3.0]
    primary_crown_radius_m:Literal[8.0]
    th_seed:float=Field(gt=0,lt=1)
    th_crown:float=Field(gt=0,lt=1)
    seed:int=Field(ge=0)
    target_units_per_corridor:Literal[15]
    worker_python:Path
    upstream_root:Path
    worker_script:Path
    @model_validator(mode='after')
    def consistent(self):
        if sorted(self.resolutions_m)!=[.5,1,2]:raise ValueError('Resoluções .5/1/2 obrigatórias')
        return self


@dataclass(frozen=True)
class CrownScenario:
    scenario_id:str='primary'
    resolution_m:float=1.
    height_m:float=3.
    detection_radius_m:float=3.
    crown_radius_m:float=8.
    algorithm:str='dalponteCIRC_numba'
    fraction:float=1.


def crown_scenarios():
    base=CrownScenario();result=[base]
    for value in [.5,2.]:result.append(replace(base,scenario_id=f'resolution_{value:g}',resolution_m=value))
    for value in [2.,5.]:result.append(replace(base,scenario_id=f'detection_radius_{value:g}',detection_radius_m=value))
    for value in [2.,5.]:result.append(replace(base,scenario_id=f'height_{value:g}',height_m=value))
    for value in [6.,12.]:result.append(replace(base,scenario_id=f'crown_radius_{value:g}',crown_radius_m=value))
    result.append(replace(base,scenario_id='dalponte_standard',algorithm='dalponte_numba'))
    for value in [.5,.25]:result.append(replace(base,scenario_id=f'density_{value:g}',fraction=value))
    return result


def load_crown_design(path):return CrownDesign.model_validate(yaml.safe_load(Path(path).read_text()))


def selected_domains(config,design):
    state=read_json(config.paths.state_file)
    entry=state['avaliacao_piloto'];aggregate=read_json(config.paths.project_root/'docs/manifesto_etapa11.json')
    inventory={p['path']:p for p in aggregate['artifacts']}
    source=Path(entry['products_root'])/'ordem_candidatos.parquet'
    if inventory.get(str(source))!=fingerprint(source):raise ValueError('Seleção congelada da etapa11 mudou')
    selection=gpd.read_parquet(source)
    selection=selection.loc[selection.selected_for_planning.eq(True)].sort_values('candidate_order')
    if len(selection)!=10 or selection.block_id.nunique()!=10:raise ValueError('Escopo de dez casos/blocos mudou')
    grid=gpd.read_file(config.paths.grid);code=config.input_preparation.grid_code_field
    domains={};plans={}
    relaxed=config.model_copy(update={'input_preparation':config.input_preparation.model_copy(update={'max_new_downloads_per_case':32})})
    for row in selection.itertuples():
        context=row.geometry.buffer(design.halo_m)
        tiles=grid.loc[grid.intersects(context)].copy();tiles['quadricula']=tiles[code].astype(str)
        tiles=tiles.sort_values('quadricula').reset_index(drop=True)
        domain=Domain('sample_exploratory',row.corridor_id,row.geometry,row.geometry,context,tiles,
            {'corridor_id':row.corridor_id,'measurement_area_m2':row.geometry.area,'context_area_m2':context.area,
             'halo_m':design.halo_m,'role':{'avaliacao':'evaluation','desenvolvimento':'development'}[row.proposed_role],
             'original_proposed_role':row.proposed_role,'block_id':row.block_id,'tiles':tiles.quadricula.tolist()})
        domains[row.corridor_id]=domain;plans[row.corridor_id]=input_plan(relaxed,domain)
    unique={(r['quadricula'],r['produto']):r for rows in plans.values() for r in rows}
    if sum(r['needs_download'] for r in unique.values())>design.maximum_new_products:raise ValueError('Complementos excedem orçamento declarado')
    return selection,domains,plans,list(unique.values()),[fingerprint(source),fingerprint(config.paths.project_root/'docs/manifesto_etapa11.json')]
