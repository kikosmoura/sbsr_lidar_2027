"""Contrato de rótulos humanos, procedência e bloqueios de validação circular."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import geopandas as gpd
import pandas as pd
from pydantic import BaseModel,ConfigDict,Field,model_validator

from .storage import read_json,fingerprint

PURPOSES=('vegetacao','altura','lacunas','prioridade')
LABELS={
 'vegetacao':('arvore_copa','arbusto','edificacao','terreno','agua','outra_estrutura','incerto'),
 'lacunas':('sem_copa_observada','sem_observacao','sem_suporte_terreno','agua','incerto')}


class Annotation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    annotation_id:str=Field(min_length=1)
    task_id:str=Field(min_length=1)
    window_id:str=Field(min_length=1)
    purpose:Literal['vegetacao','altura','lacunas','prioridade']
    reviewer_slot:Literal['A','B']
    state:Literal['pendente','concluido']='pendente'
    observer:str|None=None
    annotation_date:date|None=None
    confidence:Literal['baixa','media','alta']|None=None
    source_id:str|None=None
    source_year:int|None=Field(default=None,ge=1900,le=2100)
    temporal_compatible:Literal['sim','nao','incerto']|None=None
    method:Literal['manual','medicao_campo','registro_externo']|None=None
    label:str|None=None
    value_m:float|None=Field(default=None,allow_inf_nan=False)
    value_type:Literal['altura_objeto','cota_terreno']|None=None
    vertical_reference:str|None=None
    uncertainty_m:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    priority_score:int|None=Field(default=None,ge=1,le=5,strict=True)
    criterion:str|None=None
    saw_rankings:Literal['sim','nao']|None=None
    notes:str|None=None

    @model_validator(mode='after')
    def coherent(self):
        if self.label is not None and self.label not in LABELS.get(self.purpose,()):
            raise ValueError('Rótulo incompatível com a finalidade')
        if self.state=='concluido':
            for key in ['observer','annotation_date','confidence','source_id','source_year','temporal_compatible','method']:
                if getattr(self,key) is None or (isinstance(getattr(self,key),str) and not getattr(self,key).strip()):
                    raise ValueError(f'Anotação concluída exige {key}')
            if self.annotation_date>date.today() or self.source_year>self.annotation_date.year:
                raise ValueError('Data/ano de fonte posteriores à anotação')
            if self.source_year!=2020 and self.temporal_compatible=='sim':
                raise ValueError('Fonte de outro ano não pode ser declarada automaticamente compatível com 2020')
            if self.purpose in LABELS and self.label is None: raise ValueError('Rótulo manual obrigatório')
            if self.purpose=='altura':
                if self.value_m is None or self.value_type is None: raise ValueError('Altura exige valor e tipo de medição')
                if self.value_type=='cota_terreno' and not self.vertical_reference: raise ValueError('Cota exige referência vertical')
            if self.purpose=='prioridade' and (self.priority_score is None or not self.criterion or self.saw_rankings is None):
                raise ValueError('Prioridade exige critério próprio, nota e declaração de exposição a rankings')
        return self


def annotation_columns():
    return {name:'float64' if name in {'value_m','uncertainty_m'} else 'Int64' if name in {'source_year','priority_score'} else 'object' for name in Annotation.model_fields}


def empty_annotations(epsg,purpose):
    frame=gpd.GeoDataFrame({k:pd.Series(dtype=v) for k,v in annotation_columns().items()},
                           geometry=gpd.GeoSeries([],crs=epsg),crs=epsg)
    return frame


def check_annotations(package:Path):
    package=package.expanduser().resolve()
    plan=read_json(package/'plano_referencia.json')
    catalog=read_json(package/'trabalho/fontes_referencia.json')
    windows={r['window_id']:r for r in plan['windows']}
    tasks={r['task_id']:r for r in plan['tasks']}
    footprints=gpd.read_file(package/'amostras.gpkg',layer='contextos')
    domains=dict(zip(footprints.window_id,footprints.geometry))
    errors=[];warnings=[];records=[];ids=set()
    seal=package/'integridade_plano.json'
    if seal.is_file():
        for name,expected in read_json(seal)['files'].items():
            if fingerprint(package/name)!=expected:
                errors.append('Arquivo do plano congelado foi alterado: '+name)
    group_folds={}
    for row in plan.get('groups',[]):group_folds.setdefault(row['group_id'],set()).add(row['fold'])
    if any(len(folds)>1 for folds in group_folds.values()):errors.append('Grupo espacial aparece em mais de uma divisão')
    reserved={r['corridor_id']:r for r in plan.get('groups',[])}
    for window in windows.values():
        if reserved:
            r=reserved.get(window['corridor_id'])
            if r is None or (r['group_id'],r['fold'])!=(window['group_id'],window['fold']):
                errors.append('Janela diverge da reserva de seu corredor/grupo')
    completed_tasks=set();uncertain=0;eligible={'treino':0,'teste':0};classes=set();height_external=priority_external=0
    observers={}
    completed_geometries={}
    annotation_observers={}
    work_tasks=pd.read_csv(package/'trabalho/tarefas.csv',keep_default_na=False)
    if not {'task_id','window_id','purpose','reviewer_slot','review_state','observer','review_date'}.issubset(work_tasks.columns):
        raise ValueError('CSV de tarefas não contém os campos obrigatórios')
    if work_tasks.task_id.duplicated().any() or set(work_tasks.task_id)!=set(tasks):
        errors.append('Lista de tarefas editada: IDs duplicados, ausentes ou não planejados')
    for purpose in PURPOSES:
        frame=gpd.read_file(package/'trabalho/anotacoes.gpkg',layer=purpose)
        if frame.crs is None or frame.crs.to_epsg()!=plan['epsg']:
            errors.append(f'{purpose}: CRS da anotação incompatível');continue
        for index,row in frame.iterrows():
            try:
                raw={k:(None if pd.isna(row[k]) else row[k]) for k in Annotation.model_fields if k in row.index}
                if raw.get('priority_score') is not None:
                    value=raw['priority_score']
                    if float(value)!=int(value): raise ValueError('Nota de prioridade deve ser inteira')
                    raw['priority_score']=int(value)
                if raw.get('source_year') is not None:
                    if float(raw['source_year'])!=int(raw['source_year']):raise ValueError('Ano de fonte deve ser inteiro')
                    raw['source_year']=int(raw['source_year'])
                a=Annotation.model_validate(raw)
                if a.purpose!=purpose: raise ValueError('Finalidade não corresponde à camada')
                if a.annotation_id in ids:raise ValueError('ID de anotação duplicado')
                ids.add(a.annotation_id)
                if a.task_id not in tasks or a.window_id not in windows: raise ValueError('Tarefa/janela fora do plano congelado')
                task=tasks[a.task_id];window=windows[a.window_id]
                if (a.window_id,a.purpose,a.reviewer_slot)!=(task['window_id'],task['purpose'],task['reviewer_slot']):
                    raise ValueError('Tarefa alterada ou slot B não reservado')
                geom=row.geometry
                expected={'Point'} if purpose=='altura' else {'Polygon','MultiPolygon'}
                if geom is None or geom.is_empty or not geom.is_valid or geom.geom_type not in expected:
                    raise ValueError('Geometria válida e compatível obrigatória')
                if not domains[a.window_id].buffer(1e-6).covers(geom):raise ValueError('Geometria fora do contexto da janela')
                if a.state!='concluido':continue
                source=catalog['sources'].get(a.source_id)
                if source is None or source.get('available') is not True: raise ValueError('Fonte não catalogada/disponível')
                if source.get('kind') not in {'raw_lidar','derived_lidar','orthophoto','field','independent_altimetry','external_priority','model_prediction'}:
                    raise ValueError('Tipo de fonte não reconhecido')
                if any(type(source.get(key)) is not bool for key in ['independent_algorithm','independent_sensor']):
                    raise ValueError('Independência deve ser declarada com booleanos JSON reais')
                source_path=Path(source['path'])
                source_path=source_path if source_path.is_absolute() else package/source_path
                if not source_path.is_file(): raise ValueError('Arquivo de fonte não encontrado')
                if source.get('year')!=a.source_year:raise ValueError('Ano diverge do catálogo de fontes')
                if source.get('kind')=='model_prediction': raise ValueError('Previsão do modelo não é rótulo humano de referência')
                if a.observer.casefold() in {'llm','chatgpt','codex','automatico','automático'}:
                    raise ValueError('Identidade automática não representa intérprete humano')
                key=(a.window_id,purpose)
                observers.setdefault(key,{})[a.reviewer_slot]=a.observer.strip().casefold()
                if purpose in LABELS:
                    for prior_geom,prior_label in completed_geometries.setdefault(a.task_id,[]):
                        if prior_label!=a.label and prior_geom.intersection(geom).area>0.01:
                            raise ValueError('Polígonos de rótulos conflitantes sobrepostos na mesma revisão')
                    completed_geometries[a.task_id].append((geom,a.label))
                annotation_observers.setdefault(a.task_id,set()).add(a.observer.strip().casefold())
                completed_tasks.add(a.task_id)
                is_uncertain=a.label=='incerto'
                uncertain+=is_uncertain
                eligible_truth=(not is_uncertain and a.temporal_compatible=='sim' and
                    source.get('independent_algorithm') is True and window['intended_use']!='qa')
                if purpose=='vegetacao' and eligible_truth:
                    eligible[window['fold']]+=1
                    if window['fold']=='treino':classes.add(a.label)
                external=eligible_truth and source.get('independent_sensor') is True
                if purpose=='altura' and external and source.get('kind') in {'field','independent_altimetry'}:height_external+=1
                if purpose=='prioridade' and external and source.get('kind') in {'field','external_priority'} and a.saw_rankings=='nao':priority_external+=1
                records.append({'annotation_id':a.annotation_id,'purpose':purpose,'fold':window['fold'],
                    'task_id':a.task_id,'label':a.label,
                    'eligible_vegetation_truth':bool(eligible_truth and purpose=='vegetacao'),
                    'eligible_height_external':bool(purpose=='altura' and external and source.get('kind') in {'field','independent_altimetry'}),
                    'eligible_priority_external':bool(purpose=='prioridade' and external and source.get('kind') in {'field','external_priority'} and a.saw_rankings=='nao'),
                    'independent_sensor':source.get('independent_sensor') is True,'uncertain':is_uncertain})
            except (ValueError,TypeError,KeyError) as error:
                errors.append(f'{purpose}[{index}]: {error}')
    for key,slots in observers.items():
        if 'A' in slots and 'B' in slots and slots['A']==slots['B']:
            errors.append(f'{key}: dupla anotação exige intérpretes distintos')
    reviewed=set()
    for task in work_tasks.to_dict('records'):
        expected=tasks.get(task['task_id'])
        if expected is None:continue
        if any(task[k]!=expected[k] for k in ['window_id','purpose','reviewer_slot']):
            errors.append('Tarefa difere da reserva congelada: '+task['task_id']);continue
        if task['review_state'] not in {'pendente','concluido'}:
            errors.append('Estado de revisão inválido: '+task['task_id']);continue
        if task['review_state']!='concluido':continue
        if task['task_id'] not in completed_tasks or not task['observer'].strip() or not task['review_date']:
            errors.append('Revisão concluída exige anotação, intérprete e data: '+task['task_id']);continue
        try:
            reviewed_date=date.fromisoformat(task['review_date'])
            if reviewed_date>date.today():raise ValueError('Data futura')
        except ValueError:
            errors.append('Data de revisão inválida: '+task['task_id']);continue
        if annotation_observers.get(task['task_id'])!={task['observer'].strip().casefold()}:
            errors.append('Intérprete da revisão difere das anotações: '+task['task_id']);continue
        if task['purpose'] in LABELS:
            from shapely import union_all
            union=union_all([geom for geom,label in completed_geometries.get(task['task_id'],[])])
            if domains[task['window_id']].difference(union).area>0.01:
                errors.append('Revisão concluída deve mapear todo contexto, usando incerto onde necessário: '+task['task_id']);continue
        reviewed.add(task['task_id'])
    eligible={'treino':0,'teste':0};classes=set();height_external=priority_external=0
    for record in records:
        if record['task_id'] not in reviewed:continue
        if record['eligible_vegetation_truth']:
            eligible[record['fold']]+=1
            if record['fold']=='treino':classes.add(record['label'])
        height_external+=record['eligible_height_external']
        priority_external+=record['eligible_priority_external']
    if eligible['treino'] and not eligible['teste']:warnings.append('Há rótulos de treino, mas teste independente ainda está pendente')
    warnings.append('Teste do adverso foi inspecionado em QC anterior; reserva é para ajuste supervisionado futuro, não teste municipal intocado')
    return {'ok':not errors,'preparation_complete':True,'human_labeling_complete':not errors and len(reviewed)==len(tasks),
        'human_labeling_status':'concluida' if not errors and len(reviewed)==len(tasks) else 'pendente',
        'tasks':len(tasks),'completed_tasks_with_at_least_one_valid_annotation':len(completed_tasks),
        'reviewed_tasks':len(reviewed),'pending_tasks':len(tasks)-len(reviewed),'completed_annotations':len(records),'uncertain_annotations':int(uncertain),
        'eligible_vegetation_annotations':eligible,'supervised_training_allowed':not errors and eligible['treino']>0 and eligible['teste']>0 and len(classes)>=2,
        'independent_height_references':height_external,'independent_priority_references':priority_external,
        'precision_recall_computed':False,'errors':errors,'warnings':warnings,'records':records,
        'completion_note':'Reviewed tasks require signed review; vegetation/gaps require full footprint coverage with unknown areas explicitly uncertain'}
