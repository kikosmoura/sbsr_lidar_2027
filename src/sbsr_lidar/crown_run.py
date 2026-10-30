"""Etapa 12 autorizada: execução limitada de amostra exploratória sem referência."""
from dataclasses import asdict
from pathlib import Path
import gc
import json
import shutil
import threading
import time
import subprocess
import importlib.metadata

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import shapely

from .config import load_config
from .crown_plan import load_crown_design,selected_domains,crown_scenarios
from .crown_data import extract_case,normalize_case,digest,completed,write_frame
from .crown_raster import raster_inputs,thin_source,run_worker,crown_vectors,source_apices,scenario_support
from .crown_metrics import physical_table,choose_units,paired_rank_stability
from .comparison_analysis import analyze_comparisons
from .environment import source_digest,environment_snapshot
from .runtime import Run,exclusive_lock
from .storage import fingerprint,read_json,atomic_write_json
from .acquisition import ensure_inputs
from .input_qc import write_raster
from .spatial_units import polygonal
from .crown_validation import internal_validation


class Budget:
    def __init__(self,config,path):
        self.config=config;self.path=path;self.stop=threading.Event();self.peak=0.;self.samples=[];self.over=False
    def sample(self):
        process=psutil.Process();rss=process.memory_info().rss
        for child in process.children(recursive=True):
            try:rss+=child.memory_info().rss
            except psutil.NoSuchProcess:pass
        gib=rss/2**30;self.peak=max(self.peak,gib);self.over|=gib>self.config.resources.max_ram_gib
        self.samples.append({'seconds':round(time.monotonic()-self.started,2),'rss_parent_and_children_gib':gib})
    def loop(self):
        while not self.stop.wait(1):self.sample()
    def __enter__(self):
        self.started=time.monotonic();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start();return self
    def check(self):
        if self.over:raise ValueError('Orçamento RAM excedido; conservar checkpoints e reduzir janela')
        if shutil.disk_usage(self.config.paths.output_root).free<self.config.resources.min_output_free_gib*2**30:raise OSError('Espaço livre abaixo da reserva configurada')
    def __exit__(self,*args):
        self.stop.set();self.thread.join();self.sample()
        atomic_write_json(self.path,{'peak_rss_gib':self.peak,'elapsed_seconds':time.monotonic()-self.started,
            'budget_gib':self.config.resources.max_ram_gib,'exceeded':self.over,'samples':self.samples})


def prepare(config,design):
    if (config.grid.epsg,config.grid.origin_x,config.grid.origin_y,config.grid.resolution_m)!=(31983,0,0,1):
        raise ValueError('v0.3.0 exige EPSG31983, origem0/0 e resolução principal1m')
    if config.terrain.method!='tin' or config.terrain.maximum_distance_m!=5 or config.vegetation.minimum_height_m!=3 or config.vegetation.connectivity!=8:
        raise ValueError('v0.3.0 exige terreno congelado TIN5, altura3m e conectividade8; use configs/terreno_congelado_etapa04.yaml')
    if tuple(config.support.model_dump().values())!=(.95,25.,10.,50):
        raise ValueError('Suporte difere do protocolo v0.3.0')
    return config.model_copy(update={'protocol_version':'0.3.0','pilot':config.pilot.model_copy(update={'halo_m':design.halo_m}),
        'input_preparation':config.input_preparation.model_copy(update={'max_new_downloads_per_case':32})})


def cache_identity(config,design,domain,inputs):
    files=['crown_data.py','terrain_inputs.py','terrain_surface.py']
    return digest({'inputs':inputs,'geometry':shapely.normalize(domain.context).wkb_hex,
        'nominal_tiles':[[str(r.quadricula),shapely.normalize(r.geometry).wkb_hex] for r in domain.nominal_tiles.sort_values('quadricula').itertuples()],
        'grid':config.grid.model_dump(mode='json'),'design':{'window':design.window_size_m,
        'terrain_context':design.terrain_context_m,'resolutions':design.resolutions_m},'terrain':config.terrain.model_dump(mode='json'),
        'qc':config.input_preparation.model_dump(mode='json'),
        'runtime':{n:importlib.metadata.version(n) for n in ['numpy','scipy','laspy','lazrs','shapely','pyarrow']},
        'code':[fingerprint(Path(__file__).parent/f) for f in files]})[:20]


def sample_pycrown(config,design_path,*,case=None,plan_only=False,download_missing=False):
    design=load_crown_design(design_path);config=prepare(config,design)
    frozen=read_json(config.paths.project_root/'configs/protocolo_congelado_pycrown_v0_3_0.json')
    if any(fingerprint(Path(frozen[k]['path']))!=frozen[k] for k in ['protocol','design','selection_protocol_0_2_preserved']):raise ValueError('Protocolo congelado divergiu')
    selection,domains,plans,unique,selection_inputs=selected_domains(config,design)
    if case is not None and case not in domains:raise ValueError('Caso não pertence à seleção congelada')
    if plan_only:return {'protocol':'0.3.0','mode':design.mode,'cases':{k:v.metadata for k,v in domains.items()},'files':unique,
        'missing_products':sum(r['needs_download'] for r in unique),'scenario_count':len(crown_scenarios()),'external_accuracy':False,'municipal':False}
    if not config.paths.mount_root.is_mount():raise ValueError('HD não montado')
    if psutil.virtual_memory().available<config.resources.max_ram_gib*2**30:raise ValueError('RAM disponível inferior ao orçamento')
    if shutil.disk_usage(config.paths.project_root).free<config.resources.min_local_free_gib*2**30:raise ValueError('Disco local abaixo da reserva')
    upstream=config.paths.project_root/design.upstream_root
    for item in read_json(upstream/'UPSTREAM.json')['files']:
        if fingerprint(upstream/item['path'])['sha256']!=item['sha256']:raise ValueError('Fonte PyCrown original alterada')
    ensure_inputs(config,unique,download_missing=download_missing,event=lambda name,**kw:print(name,kw,flush=True))
    selection,domains,plans,unique,selection_inputs=selected_domains(config,design)
    grid_files=sorted(config.paths.grid.parent.glob(config.paths.grid.stem+'.*'))
    inputs=selection_inputs+[fingerprint(p) for p in grid_files if p.is_file()]+[fingerprint(Path(r['selected_laz'])) for r in unique]
    worker_inputs=[fingerprint(p) for p in sorted((config.paths.project_root/design.upstream_root).rglob('*')) if p.is_file() and '__pycache__' not in str(p)]
    worker_inputs +=[fingerprint(config.paths.project_root/design.worker_script),fingerprint(config.paths.project_root/'relatorios/etapa12/requirements_pycrown.lock.txt')]
    env=environment_snapshot(config.tools.pdal,config.tools.gdalinfo,config.tools.timeout_seconds)
    worker_env=subprocess.run([str(config.paths.project_root/design.worker_python),'-m','pip','freeze'],capture_output=True,text=True,check=True).stdout.strip().splitlines()
    frozen_env=(config.paths.project_root/'relatorios/etapa12/requirements_pycrown.lock.txt').read_text().strip().splitlines()
    if sorted(worker_env)!=sorted(frozen_env):raise ValueError('Ambiente PyCrown diverge do lock')
    env['pycrown_worker_packages']=worker_env
    with exclusive_lock(config.paths.output_root/'etapa12.lock'):
        run=Run(config.paths.runs_root,config.paths.state_file,'sample-pycrown',{'physical':config.model_dump(mode='json'),
            'design':design.model_dump(mode='json'),'case_filter':case},inputs+worker_inputs,env,source_digest(),stage='12')
        products=config.paths.output_root/'etapa12'/'v0.3.0'/run.run_id;products.mkdir(parents=True)
        result={'run_id':run.run_id,'products_root':str(products),'protocol_version':'0.3.0','external_accuracy':False,'case_results':{}}
        def event(name,**kw):run.event(name,**kw);print(name,kw,flush=True);budget.check()
        try:
            with Budget(config,products/'resources.json') as budget:
                order=sorted(domains,key=lambda cid:(domains[cid].metadata['role']!='development',int(selection.loc[selection.corridor_id.eq(cid),'candidate_order'].iloc[0])))
                tables=[];all_sensitivity=[];all_qc=[];all_primary=[]
                for cid in order:
                    if case is not None and cid!=case:continue
                    started=time.monotonic();domain=domains[cid]
                    own_inputs=[fingerprint(Path(r['selected_laz'])) for r in plans[cid]]
                    data_root=config.paths.output_root/'etapa12'/'cache_dados'/cid/cache_identity(config,design,domain,own_inputs)
                    buckets,qc=extract_case(config,design,domain,plans[cid],data_root/'raw',event)
                    heights,reports=normalize_case(config,design,domain,buckets,data_root/'normalized',event)
                    validation_key=digest({'heights':fingerprint(heights),'code':fingerprint(Path(__file__).parent/'crown_validation.py')})[:16]
                    validation=internal_validation(config,design,domain,buckets,reports,heights,data_root/f'validation_{validation_key}',event)
                    analysis_key=digest({'heights':fingerprint(heights),'design':design.model_dump(mode='json'),
                        'source':source_digest(),'worker':worker_inputs,'environment':env})[:20]
                    root=config.paths.output_root/'etapa12'/'cache_analise'/cid/analysis_key;root.mkdir(parents=True,exist_ok=True)
                    seal=root/'complete.json';record=completed(seal)
                    if record:event('case_cache',corridor=cid);case_result=record['case_result']
                    else:
                        scenario_rows=[];primary=None;canonical=None;primary_chosen=None
                        for scenario in crown_scenarios():
                            folder=root/scenario.scenario_id;folder.mkdir(parents=True,exist_ok=True)
                            source=thin_source(heights,root/f'density_{scenario.fraction:g}.parquet',scenario.fraction,design.seed)
                            raster_root=root/f'rasters_r{scenario.resolution_m:g}_f{scenario.fraction:g}'
                            layout,arrays=raster_inputs(config,design,domain,source,reports,scenario.resolution_m,raster_root)
                            label_path,worker=run_worker(config,design,layout,arrays,scenario,folder,event)
                            with np.load(label_path) as data:labels=data['labels'];seeds=data['seeds'];original=data['original_xy'];corrections=data['corrections'].tolist()
                            crowns,tops=crown_vectors(config,layout,domain,labels,seeds,original,corrections,arrays['observation']==1,scenario)
                            support,observed,patches,patch_summary=scenario_support(config,layout,domain,arrays,labels,scenario)
                            cfg=config.model_copy(update={'vegetation':config.vegetation.model_copy(update={'minimum_height_m':scenario.height_m})})
                            if primary is None:
                                canonical=support;tops=source_apices(cfg,layout,source,labels,tops,scenario.height_m,arrays['observation']==1)
                                physical,audit=physical_table(cfg,domain,source,support,observed,patches,tops,[25,50,100],canonical,event)
                                primary_chosen=choose_units(physical.loc[physical.nominal_size_m.eq(50)],design)
                                write_frame(physical,folder/'indicadores.parquet');write_frame(primary_chosen,folder/'coorte_50m.parquet')
                                primary={'observed':observed,'patches':patches,'tops':tops,'support':support,'source':source,'config':cfg}
                                atomic_write_json(folder/'auditoria_indicadores.json',audit)
                                write_raster(folder/'labels.tif',[np.where(arrays['observation']==1,labels,-1)],layout,epsg=config.grid.epsg,dtype='int32',nodata=-1,
                                    descriptions=['estimated_crown_label_0_observed_without_segment'],tags={'stage':'12','accuracy_validated':'false','protocol_version':'0.3.0'})
                                for name,gdf in [('copas_estimadas',crowns),('topos_estimados',tops),('manchas_conectadas',patches)]:
                                    write_frame(gdf,folder/f'{name}.parquet')
                                    if len(gdf):gdf.to_file(folder/'copas_topos.gpkg',layer=name,driver='GPKG')
                            else:
                                common=polygonal(primary['observed'].intersection(observed));ids=primary_chosen.loc[primary_chosen.selected_primary_cohort,'unit_id'].tolist()
                                left,_=physical_table(primary['config'],domain,primary['source'],primary['support'],primary['observed'],primary['patches'],primary['tops'],[50],canonical,event,common=common)
                                right,_=physical_table(cfg,domain,source,support,observed,patches,tops,[50],canonical,event,common=common)
                                write_frame(left,folder/'principal_suporte_comum.parquet');write_frame(right,folder/'cenario_suporte_comum.parquet')
                                ca=polygonal(shapely.union_all(primary['patches'].geometry.to_numpy()).intersection(common))
                                cb=polygonal(shapely.union_all(patches.geometry.to_numpy()).intersection(common));union=ca.union(cb).area
                                scenario_rows.append({'corridor_id':cid,'role':domain.metadata['role'],**asdict(scenario),
                                    'observed_primary_m2':primary['observed'].area,'observed_scenario_m2':observed.area,'common_observed_m2':common.area,
                                    'canopy_union_IoU_common_support':ca.intersection(cb).area/union if union else None,
                                    'estimated_segments_context':len(crowns),'estimated_seeds_in_measurement':int(tops.seed_in_measurement.sum()) if len(tops) else 0,
                                    **paired_rank_stability(left,right,config,ids),'accuracy_metric':False})
                            atomic_write_json(folder/'summary.json',{'scenario':asdict(scenario),'worker':worker,'patches':patch_summary,
                                'estimated_segments_context':len(crowns),'estimated_segments_intersecting_P':int((crowns.area_measurement_m2>0).sum()) if len(crowns) else 0,
                                'estimated_seeds_inside_P':int(tops.seed_in_measurement.sum()) if len(tops) else 0,
                                'observed_area_m2':observed.area,'P_area_m2':domain.measurement.area,'whole_corridor_segmentation_before_crop':True,'external_accuracy':False})
                            event('scenario_complete',corridor=cid,scenario=scenario.scenario_id,crowns=len(crowns));del arrays,layout,labels;gc.collect()
                        write_frame(pd.DataFrame(scenario_rows),root/'sensibilidade.parquet')
                        atomic_write_json(root/'qc.json',{'sources':qc,'windows':reports,'domain':domain.metadata,'inputs':own_inputs,'internal_validation':fingerprint(validation)})
                        case_result={'corridor_id':cid,'role':domain.metadata['role'],'block_id':domain.metadata['block_id'],'root':str(root),
                            'normalized_source':str(heights),'seconds_including_acquisition_cache':time.monotonic()-started,
                            'primary':read_json(root/'primary/summary.json'),'selected_units':int(primary_chosen.selected_primary_cohort.sum()),
                            'eligible_units_50m':int(primary_chosen.eligible_A_plus_3D.sum()),'window_count':len(reports)}
                        files=[p for p in root.rglob('*') if p.is_file() and not p.name.endswith('.part') and p!=seal]
                        atomic_write_json(seal,{'case_result':case_result,'outputs':[fingerprint(p) for p in files]})
                    result['case_results'][cid]=case_result
                    tables.append(gpd.read_parquet(Path(case_result['root'])/'primary/coorte_50m.parquet'))
                    all_primary.append(gpd.read_parquet(Path(case_result['root'])/'primary/indicadores.parquet'))
                    all_sensitivity.append(pd.read_parquet(Path(case_result['root'])/'sensibilidade.parquet'))
                    all_qc.extend({'corridor_id':cid,**r} for r in read_json(Path(case_result['root'])/'qc.json')['sources'])
                    primary=None;canonical=None;gc.collect()
                table=gpd.GeoDataFrame(pd.concat(tables,ignore_index=True),geometry='geometry',crs=config.grid.epsg)
                write_frame(table,products/'todas_unidades_50m.parquet');write_frame(gpd.GeoDataFrame(pd.concat(all_primary,ignore_index=True),crs=config.grid.epsg),products/'indicadores_multiescala.parquet')
                chosen=table.loc[table.selected_primary_cohort].copy();chosen['case']=chosen.role.map({'evaluation':'sample_evaluation','development':'sample_development'})
                write_frame(chosen,products/'coorte_selecionada.parquet')
                comparison=analyze_comparisons(chosen,config,'multiple_provisional_corridor_blocks_not_certified_independent')
                for row in comparison['controles'].index:
                    role='evaluation' if comparison['controles'].loc[row,'case']=='sample_evaluation' else 'development'
                    comparison['controles'].loc[row,'provisional_corridor_groups']=int(chosen.loc[chosen.role.eq(role),'corridor_id'].nunique())
                    comparison['controles'].loc[row,'independent_corridor_groups_in_paired_cohort']=None
                    comparison['controles'].loc[row,'surrogate_status']='independence_and_exchangeability_not_established'
                for name,frame in comparison.items():write_frame(frame,products/f'{name}.parquet')
                write_frame(pd.concat(all_sensitivity,ignore_index=True),products/'sensibilidade_cenarios.parquet');write_frame(pd.DataFrame(all_qc),products/'qc_fontes.parquet')
                write_frame(selection,products/'selecao_corredores_congelada.parquet')
                result['sample']={'corridors':len(tables),'selected_evaluation_units':int(chosen.role.eq('evaluation').sum()),
                    'selected_development_units':int(chosen.role.eq('development').sum()),'target_evaluation_units':120,
                    'independent_groups_certified':None,'p_values_computed':False,'municipal':False,'external_reference_labels':0}
                atomic_write_json(products/'result.json',result);budget.check()
            outputs=[p for p in products.rglob('*') if p.is_file()];run.finish(outputs)
            result['run_manifest']=str(run.path/'manifest.json');result['resources']=read_json(products/'resources.json')|{'samples':'see resources.json'}
            return result
        except BaseException as error:run.fail(error,interrupted=isinstance(error,KeyboardInterrupt));raise
