"""Etapa 06: máscara candidata, refino experimental e incerteza explícita."""
from __future__ import annotations

import os
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import pyogrio
import rasterio
from shapely.geometry import box

from .annotations import check_annotations
from .canopy_features import accumulate_points,local_geometry,spectral_features
from .canopy_masks import (OBSERVATION,UNCERTAINTY,CLASSIFICATION,observation_mask,make_masks,
                           classification_status,observed_geometry,patch_layers)
from .doctor import existing_parent
from .domain import build_domain,cloud_path
from .environment import environment_snapshot,source_digest
from .input_qc import grid_layout,write_raster
from .preparation import _input_fingerprints
from .reference import terrain_sources
from .runtime import Run,exclusive_lock
from .storage import atomic_write_json,fingerprint,read_json,cache_key,load_cache,save_cache


def write_polygon_layers(path,layers):
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.canopy_',suffix='.gpkg');os.close(fd)
    temporary=Path(name);temporary.unlink()
    try:
        for name,frame in layers.items():
            pyogrio.write_dataframe(frame,temporary,layer=name,geometry_type='MultiPolygon',promote_to_multi=True)
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def qa_cells(config,layout,domain,mask,flags,counts,candidate,class1,geometry,spectral):
    candidates=np.flatnonzero((flags.ravel()!=0)&(flags.ravel()!=65535))
    priority=candidates[(flags.ravel()[candidates]&(8|16))!=0]
    rng=np.random.default_rng(config.resources.seed)
    n=min(config.vegetation.qa_sample_cells,len(candidates))
    if len(priority)>n:chosen=rng.choice(priority,n,replace=False)
    else:
        rest=np.setdiff1d(candidates,priority)
        chosen=np.r_[priority,rng.choice(rest,n-len(priority),replace=False)]
    rows=[]
    for index in sorted(chosen):
        rr,cc=divmod(int(index),layout.width)
        left=layout.transform.c+cc*layout.resolution;top=layout.transform.f-rr*layout.resolution
        geom=box(left,top-layout.resolution,left+layout.resolution,top).intersection(domain.context)
        row={'cell_id':f'Q06_{domain.case}_{int(left/layout.resolution)}_{int(top/layout.resolution)}',
             'case':domain.case,'candidate_records':int(candidate[rr,cc]),'class1_high_records':int(class1[rr,cc]),
             'structure_records':int(counts['structure'][rr,cc]),'flags':int(flags[rr,cc]),
             'refined_status':int(mask[rr,cc]),'manual_status':'pendente','geometry':geom}
        for name,array in {**geometry,**spectral}.items():row[name]=float(array[rr,cc]) if np.isfinite(array[rr,cc]) else None
        rows.append(row)
    if not rows:
        return gpd.GeoDataFrame({'cell_id':pd.Series(dtype=str),'manual_status':pd.Series(dtype=str)},geometry=gpd.GeoSeries([],crs=config.grid.epsg))
    return gpd.GeoDataFrame(rows,crs=config.grid.epsg)


def canopy_run(config,case,*,use_cache=True):
    if not config.paths.mount_root.is_mount():raise ValueError('HD externo não montado')
    if psutil.virtual_memory().available/2**30<config.resources.max_ram_gib:raise ValueError('RAM abaixo do orçamento')
    for path,minimum in [(config.paths.runs_root,config.resources.min_local_free_gib),(config.paths.output_root,config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free/2**30<minimum:raise ValueError('Espaço abaixo da reserva configurada')
    state=read_json(config.paths.state_file)
    if state.get('etapas',{}).get('05',{}).get('status')!='concluida':raise ValueError('Concluir preparação da referência da etapa 05')
    package=Path(state['referencia_anotacao']['package'])
    assessment=check_annotations(package)
    if not assessment['ok']:raise ValueError('Anotações/planos inconsistentes; corrigir antes de registrar máscara: '+str(assessment['errors']))
    source=terrain_sources(config,state)[case]
    domain=build_domain(config,case);layout=grid_layout(config,domain)
    parent=read_json(Path(source['entry']['manifest']))
    # O H pré-calculado só é coerente com os mesmos arquivos usados na etapa 04.
    parent_inputs=[fingerprint(Path(r['path'])) for r in parent['inputs']]
    if parent_inputs!=parent['inputs']:raise ValueError('Originais/protocolo mudaram desde a etapa 04; reconstruir H antes da máscara')
    raw_paths={tile:cloud_path(config,'MDS',tile) for tile in domain.metadata['tiles']}
    if not np.allclose(source['report']['grid']['transform'],list(layout.transform)[:6],atol=1e-9,rtol=0):
        raise ValueError('Grade da máscara difere do DTM de origem')
    products=source['products']
    input_paths=[Path(source['entry']['report']),Path(source['entry']['manifest']),
                 products['alturas_pontos.parquet'],products['primary_validity'],
                 package/'plano_referencia.json',package/'integridade_plano.json',package/'amostras.gpkg',
                 package/'trabalho/anotacoes.gpkg',package/'trabalho/tarefas.csv',package/'trabalho/fontes_referencia.json']
    inputs=list({r['path']:r for r in [*parent_inputs,*_input_fingerprints(config),*[fingerprint(p) for p in input_paths]]}.values())
    heights=sorted(set(config.sensitivity.heights_m+[config.vegetation.minimum_height_m]))
    with exclusive_lock(config.paths.runs_root/'.canopy.lock'):
        env=environment_snapshot(config.tools.pdal,config.tools.gdalinfo,config.tools.timeout_seconds)
        code=source_digest();snapshot=config.model_dump(mode='json');snapshot['execution']={'case':case,'reference_assessment':assessment}
        command=f'canopy:{case}';key=cache_key(command=command,config=snapshot,inputs=inputs,code=code,environment=env)
        cache_root=config.paths.runs_root/'cache'
        run=Run(config.paths.runs_root,config.paths.state_file,command,snapshot,inputs,env,code,stage='06')
        started=time.monotonic()
        def event(name,**details):run.event(name,**details);print(f'{name}: {details}',file=sys.stderr,flush=True)
        try:
            cached=load_cache(cache_root,key) if use_cache else None
            if cached:
                outputs=[Path(p['path']) for p in cached['outputs']]
                run.finish(outputs,cache_hit=True,source_run_id=cached['source_run_id'])
                report=read_json(outputs[0])
                return {'ok':True,'case':case,'run_id':run.run_id,'cache_hit':True,'manifest':str(run.path/'manifest.json'),
                        'report':str(outputs[0]),'products_root':report['products_root'],'analysis_version':report['analysis_version']}
            directory=config.paths.output_root/'etapa06'/case/run.run_id;directory.mkdir(parents=True,exist_ok=False)
            outputs=[]
            def raster(name,values,*,dtype='float32',nodata=None,mask=None,descriptions=None):
                if nodata is None:nodata=config.grid.nodata
                target=directory/name
                bands=[]
                for value in values if isinstance(values,list) else [values]:
                    array=np.where(np.isfinite(value),value,nodata).astype(dtype)
                    array[~(layout.context_mask if mask is None else mask)]=nodata
                    bands.append(array)
                write_raster(target,bands,layout,epsg=config.grid.epsg,dtype=dtype,nodata=nodata,
                    descriptions=descriptions or [name]*len(bands),tags={'stage':'06','meaning':'unvalidated_candidate_crown_or_QC',
                    'count_unit':'MDS_records_not_independent_pulses','reference_status':assessment['human_labeling_status'],
                    'supervised_model_trained':'false'})
                outputs.append(target);return target
            event('canopy_counts',case=case,heights=heights)
            counts,candidate,class1,xyz,lookup,point_report=accumulate_points(config,layout,products['alturas_pontos.parquet'],heights)
            with rasterio.open(products['primary_validity']) as ds:
                if ds.shape!=layout.shape or ds.transform!=layout.transform or ds.crs.to_epsg()!=config.grid.epsg:raise ValueError('Raster de terreno desalinhado')
                terrain_valid=ds.read(1)==0
            observation,valid=observation_mask(layout,counts,terrain_valid)
            geometry,geometry_report=local_geometry(config,layout,xyz,counts['above_geometry']>0,event)
            spectral,spectral_report=spectral_features(config,layout,lookup,raw_paths,event)
            del xyz,lookup
            masks,flags,return_features=make_masks(config,layout,counts,candidate,class1,geometry,valid)
            raster('observabilidade.tif',observation,dtype='uint8',nodata=255)
            raster('dominio_valido.tif',valid.astype(np.uint8),dtype='uint8',nodata=255)
            raster('mascara_medicao.tif',layout.measurement_mask.astype(np.uint8),dtype='uint8',nodata=255)
            raster('contagem_suporte.tif',[counts[k] for k in ['all','usable','valid_h','above_geometry']],dtype='uint32',nodata=4294967295,
                   descriptions=['MDS_registros','MDS_apos_QC','MDS_H_valido','MDS_H_acima_do_menor_limiar'])
            raster('geometria_auxiliar.tif',[geometry[k] for k in ['planarity','linearity','roughness_m','xy_spread_m','neighbor_count']],
                   descriptions=['planaridade','linearidade','rugosidade_RMS_plano_m','dispersao_XY_m','vizinhos_ate_k'])
            raster('espectral_auxiliar.tif',[spectral[k] for k in ['nir_red','excess_green','brightness']],
                   descriptions=['indice_NIR_R_nao_calibrado','excesso_verde_normalizado_nao_calibrado','brilho_RGB_relativo'])
            raster('retornos_auxiliares.tif',list(return_features.values()),descriptions=list(return_features))
            observed=observed_geometry(layout,valid,domain)
            layers={'medicao':gpd.GeoDataFrame({'corridor_id':[domain.corridor_id]},geometry=[domain.measurement],crs=config.grid.epsg),
                    'contexto':gpd.GeoDataFrame({'corridor_id':[domain.corridor_id]},geometry=[domain.context],crs=config.grid.epsg)}
            if observed.is_empty:
                layers['suporte_observado']=gpd.GeoDataFrame({'area_m2':pd.Series(dtype=float)},geometry=gpd.GeoSeries([],crs=config.grid.epsg))
            else:layers['suporte_observado']=gpd.GeoDataFrame({'area_m2':[observed.area]},geometry=[observed],crs=config.grid.epsg)
            scenarios={};baseline_areas=[]
            for height,versions in masks.items():
                label=f'{height:g}'
                raster(f'contagem_candidatos_h{label}.tif',[candidate[height],class1[height]],dtype='uint32',nodata=4294967295,
                       descriptions=['registros_classes_3_4_5_H_ge_limiar','registros_classe_1_H_ge_limiar'])
                raster(f'incerteza_h{label}.tif',flags[height],dtype='uint16',nodata=65535,mask=valid)
                for version,mask in versions.items():
                    raster(f'copa_{version}_h{label}_contexto.tif',mask,dtype='uint8',nodata=255)
                    raster(f'copa_{version}_h{label}_medicao.tif',mask,dtype='uint8',nodata=255,mask=layout.measurement_mask)
                    raster(f'estados_{version}_h{label}.tif',classification_status(observation,mask),dtype='uint8',nodata=255)
                    event('canopy_patches',version=version,height=height)
                    context,core,labels,summary=patch_layers(config,layout,domain,mask,version,height,valid)
                    layers[f'{version}_h{label}_contexto']=context;layers[f'{version}_h{label}_medicao']=core
                    raster(f'manchas_{version}_h{label}.tif',labels,dtype='int32',nodata=-2147483648,mask=valid)
                    if summary['candidate_area_measurement_exact_m2']>observed.area+1e-6:raise ValueError('Copa excede suporte observado')
                    summary['record_density_sensitivity']={
                        'candidate_cells_one_or_more_measurement':int(np.sum((candidate[height]>=1)&valid&layout.measurement_mask)),
                        'candidate_cells_two_or_more_measurement':int(np.sum((candidate[height]>=2)&valid&layout.measurement_mask)),
                        'selected_rule_minimum_records':config.vegetation.minimum_points_per_cell}
                    scenarios[f'{version}_h{label}']=summary
                    if version=='baseline':baseline_areas.append(summary['candidate_area_measurement_exact_m2'])
                if np.any((versions['refinada']==1)&(versions['baseline']!=1)):raise ValueError('Refino promoveu copa sem referência')
            if np.any(np.diff(baseline_areas)>1e-6):raise ValueError('Área baseline deve diminuir ou permanecer com altura mínima crescente')
            h=config.vegetation.minimum_height_m
            layers['celulas_qa']=qa_cells(config,layout,domain,masks[h]['refinada'],flags[h],counts,candidate[h],class1[h],geometry,spectral)
            vectors=directory/'mascaras_manchas.gpkg';write_polygon_layers(vectors,layers);outputs.append(vectors)
            classes_path=directory/'auditoria_classes.csv';pd.DataFrame(point_report['classes']).to_csv(classes_path,index=False);outputs.append(classes_path)
            analysis_version=f'baseline_h{h:g}'
            primary=layers[f'baseline_h{h:g}_medicao']
            decision={'version':analysis_version,'provisional':True,'quality_measured':False,
                'reason':'Baseline explicit from protocol; retain class 3/small candidates. Refined flags lack human validation and remain sensitivity only.',
                'not_selected_using_rankings_or_3D_advantage':True}
            qa_report={'class1_high_cells_measurement':int(np.sum((class1[h]>0)&valid&layout.measurement_mask)),
                'class1_high_without_baseline_cells_measurement':int(np.sum((class1[h]>0)&valid&layout.measurement_mask&(masks[h]['baseline']==0))),
                'flagged_cells_measurement':{description:int(np.sum(valid&layout.measurement_mask&((flags[h]&bit)!=0))) for bit,description in UNCERTAINTY.items()},
                'manual_QA_cells_exported':len(layers['celulas_qa']),'confirmed_omissions':None,'confirmed_false_positives':None,
                'QA_is_hypothesis_not_verified_error':True}
            quality={'status':'pending_adequate_human_reference','reference_assessment':assessment,
                'confusion_matrix':None,'precision':None,'recall':None,'F1':None,'IoU':None,
                'supervised_classifier_trained':False,'semantic_separation_trees_shrubs_roofs_posts_validated':False,
                'reason':'No completed reference labels in current pilot; no predictions reused as truth. Future labels require quality/adjudication audit before metrics or fitting.'}
            # Não reescrever planos/anotações anteriores; detectar mudanças concorrentes.
            for prior in inputs:
                if fingerprint(Path(prior['path']))!=prior:raise OSError('Entrada mudou durante a geração da máscara')
            result={'ok':True,'stage':'06','case':case,'run_id':run.run_id,'domain':domain.metadata,'products_root':str(directory),
                'grid':{'epsg':config.grid.epsg,'shape':list(layout.shape),'transform':list(layout.transform)[:6],'resolution_m':layout.resolution},
                'analysis_version':analysis_version,'selection':decision,'heights_m':heights,'geometry':geometry_report,'spectral':spectral_report,
                'point_audit':point_report,'QA':qa_report,'quality':quality,'scenarios':scenarios,
                'observation':{'context_cells':int(layout.context_mask.sum()),'measurement_center_cells':int(layout.measurement_mask.sum()),
                    'valid_cells_measurement_center':int(np.sum(valid&layout.measurement_mask)),
                    'exact_observed_area_in_measurement_m2':float(observed.area),
                    'status_counts_measurement_center':{name:int(np.sum((observation==code)&layout.measurement_mask)) for code,name in OBSERVATION.items() if code!=255}},
                'mask_values':{'baseline':{'0':'no_candidate_detected_by_rule_not_verified_tree_absence','1':'candidate_crown','255':'outside_valid_observed_domain'},
                               'refinada':{'0':'no_candidate_detected','1':'retained_candidate','2':'classification_uncertain','255':'outside_valid_observed_domain'}},
                'observation_codes':OBSERVATION,'classification_codes':CLASSIFICATION,'uncertainty_bits':UNCERTAINTY,
                'patches_are_individual_trees':False,'products':[str(p) for p in outputs],
                'elapsed_seconds':time.monotonic()-started,'peak_process_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'limitations':['Unvalidated candidate mask; no supervised fitting or classification accuracy claimed.',
                    'Same observation domain for all heights/versions; uncertainty remains in denominator, never converted to known no-tree.',
                    'No dilation, closing, minimum-area deletion or forced promotion of class 1 was applied to crown masks.',
                    'Counts are MDS records; repeated within-file observations may affect density; PCA alone uses 0.1 m voxel thinning.',
                    'RGB/NIR auxiliary indices uncalibrated, photographic epoch unknown; no universal spectral threshold.',
                    'Planar/thin/isolated flags are uncertain hypotheses, not confirmed roofs/posts/shrubs.',
                    'Patches reconstructed with context before exact vector clipping; components can contain several trees and are censored at support/context limits.',
                    'Raster center-cell areas and exact polygon intersections differ; use reported area definition consistently.',
                    f'Baseline of {h:g} m remains a provisional protocol choice; no ranking or advantage of C was evaluated.',
                    'No longitudinal segmentation, ecological priority or scientific indicator comparison was performed.']}
            report=run.path/'mascara_copa.json';atomic_write_json(report,result)
            text=run.path/'mascara_copa.md'
            lines=[f'# Máscara candidata — {domain.corridor_id} / {case}','',f'Execução `{run.run_id}`; análise provisória: `{analysis_version}`; referência humana pendente.','',
                '|Versão|Área candidata em P, interseção exata (m²)|Células incertas em P (centro)|Manchas que têm área em P|',
                '|---|---:|---:|---:|']
            for name,summary in scenarios.items():lines.append(f"|{name}|{summary['candidate_area_measurement_exact_m2']:.3f}|{summary['uncertain_cells_measurement_center']}|{summary['components_intersecting_measurement']}|")
            lines+=['','## Limites','']+['- '+s for s in result['limitations']]+['','## Produtos','']+['- `'+str(p)+'`' for p in outputs]
            text.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            outputs=[report,text,*outputs];save_cache(cache_root,key,run.run_id,outputs);run.finish(outputs)
            return {'ok':True,'case':case,'run_id':run.run_id,'cache_hit':False,'manifest':str(run.path/'manifest.json'),
                    'report':str(report),'products_root':str(directory),'analysis_version':analysis_version}
        except BaseException as error:
            run.fail(error,interrupted=isinstance(error,KeyboardInterrupt));raise
