"""Etapa 05: preparar material de anotação real sem preencher rótulos humanos."""
from __future__ import annotations

import math
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import pyogrio

from .annotations import PURPOSES,LABELS,Annotation,empty_annotations,check_annotations
from .doctor import existing_parent
from .domain import build_domain,input_plan
from .environment import environment_snapshot,source_digest,native_command
from .preparation import _vectors,_input_fingerprints
from .reference_sampling import corridor_groups,make_frame,select_windows
from .reference_materials import clip_heights,clip_lidar_rgb,render_window_profiles
from .runtime import Run,exclusive_lock
from .schemas import RunManifest
from .storage import atomic_write_json,read_json,fingerprint,cache_key,load_cache,save_cache


def terrain_sources(config,state):
    if state.get('etapas',{}).get('04',{}).get('status')!='concluida':
        raise ValueError('Concluir etapa 04 antes de preparar referência')
    references=state.get('terreno_altura_piloto',{})
    result={}
    for case,key in [('main','principal'),('adversarial','adverso')]:
        entry=references.get(key)
        if not entry:raise ValueError('Estado não aponta relatório de terreno: '+case)
        manifest=RunManifest.model_validate(read_json(Path(entry['manifest'])))
        report=read_json(Path(entry['report']))
        if manifest.status!='completed' or manifest.stage!='04' or report['domain']['case']!=case:
            raise ValueError('Relatório de terreno incompatível')
        if report['grid']['resolution_m']!=config.grid.resolution_m or report['primary_radius_m']!=config.terrain.maximum_distance_m:
            raise ValueError('Grade/raio divergem da referência congelada da etapa 04')
        if config.terrain.method not in {'pending_qc',report['selected_method']}:raise ValueError('Método difere do terreno de origem')
        products={Path(p).name:Path(p) for p in report['products']}
        method=report['selected_method'];radius=f"{report['primary_radius_m']:g}"
        products['primary_validity']=products[f'validade_{method}_r{radius}.tif']
        products['primary_dtm']=products[f'dtm_{method}_r{radius}_contexto.tif']
        result[case]={'entry':entry,'report':report,'products':products}
    return result


def _source_inventory(config):
    suffixes={'.tif','.tiff','.jp2','.ecw','.jpg','.jpeg','.png'}
    found=[]
    # Sem varrer arquivos pessoais: apenas os insumos e pastas convencionais do projeto.
    roots=[config.paths.project_root/'files']
    roots += [p for p in config.paths.data_root.iterdir() if p.is_dir() and p!=config.paths.output_root]
    for root in roots:
        for path in root.rglob('*'):
            if path.is_file() and path.suffix.lower() in suffixes:found.append(str(path))
    return {'searched_roots':[str(p) for p in roots],'image_candidates':sorted(found),
            'verified_external_2020_images':[],
            'note':'Candidate files are not accepted as dated/independent reference automatically; derived LiDAR imagery is same sensor.'}


def reference_run(config,*,use_cache=True):
    if not config.paths.mount_root.is_mount():raise ValueError('HD externo não montado')
    if psutil.virtual_memory().available/2**30<config.resources.max_ram_gib:raise ValueError('RAM disponível abaixo do orçamento')
    for path,minimum in [(config.paths.runs_root,config.resources.min_local_free_gib),(config.paths.output_root,config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free/2**30<minimum:raise ValueError('Espaço abaixo da reserva')
    state=read_json(config.paths.state_file)
    sources=terrain_sources(config,state)
    groups,mapping=corridor_groups(config)
    inventory=_source_inventory(config)
    guide=config.paths.project_root/'docs/guia_anotacao_etapa05.md'
    if not guide.is_file():raise ValueError('Guia de anotação ausente')
    inputs=_input_fingerprints(config)+[fingerprint(guide)]
    for source in sources.values():
        inputs += [fingerprint(Path(source['entry'][k])) for k in ['report','manifest']]
        inputs += [fingerprint(source['products'][k]) for k in ['alturas_pontos.parquet','contagens_altura.tif','primary_validity','primary_dtm']]
    domains={case:build_domain(config,case) for case in sources}
    plans={case:input_plan(config,domain) for case,domain in domains.items()}
    raw_paths=sorted({Path(r['selected_laz']) for plan in plans.values() for r in plan if r['produto']=='MDS' and r['selected_laz']})
    inputs += [fingerprint(p) for p in raw_paths]
    if len(raw_paths)!=sum(len(d.nominal_tiles) for d in domains.values()):raise ValueError('MDS ausente no plano do piloto')
    inputs=list({record['path']:record for record in inputs}.values())
    snapshot=config.model_dump(mode='json')
    snapshot['external_image_inventory']=inventory
    with exclusive_lock(config.paths.runs_root/'.reference.lock'):
        env=environment_snapshot(config.tools.pdal,config.tools.gdalinfo,config.tools.timeout_seconds)
        env['qgis']=native_command(config.reference.qgis_python,['-c','from qgis.core import Qgis; print(Qgis.QGIS_VERSION)'],30)
        code=source_digest();command='reference:pilot'
        key=cache_key(command=command,config=snapshot,inputs=inputs,code=code,environment=env)
        cache_root=config.paths.runs_root/'cache'
        run=Run(config.paths.runs_root,config.paths.state_file,command,snapshot,inputs,env,code,stage='05')
        started=time.monotonic()
        def event(name,**details):
            run.event(name,**details);print(f'{name}: {details}',file=sys.stderr,flush=True)
        try:
            cached=load_cache(cache_root,key) if use_cache else None
            if cached:
                outputs=[Path(x['path']) for x in cached['outputs']]
                report=read_json(outputs[0]);directory=Path(report['package'])
                current=check_annotations(directory)
                status_path=run.path/'estado_anotacoes_atual.json';atomic_write_json(status_path,current)
                mutable=[directory/p for p in report['mutable_workfiles']]
                run.finish([status_path,*outputs,*mutable],cache_hit=True,source_run_id=cached['source_run_id'])
                return {'ok':True,'run_id':run.run_id,'cache_hit':True,'manifest':str(run.path/'manifest.json'),
                    'report':str(outputs[0]),'package':str(directory),'annotation_status_report':str(status_path),
                    'human_labeling_status':current['human_labeling_status'],'pending_tasks':current['pending_tasks']}
            directory=config.paths.output_root/'etapa05'/run.run_id
            directory.mkdir(parents=True,exist_ok=False)
            frames=[];selected=[];design={};source_indices={}
            for number,(case,source) in enumerate(sources.items()):
                domain=domains[case];fold='treino' if case=='main' else 'teste'
                event('sample_frame',case=case)
                frame=make_frame(config,domain,source['products'],mapping[domain.corridor_id],fold)
                n=config.reference.main_windows if case=='main' else config.reference.adversarial_windows
                chosen,details=select_windows(frame,n,config.resources.seed+number)
                frame['selected']=frame.window_id.isin(chosen.window_id)
                frames.append(frame);selected.append(chosen);design[case]=details
            samples=gpd.GeoDataFrame(pd.concat(selected,ignore_index=True),crs=config.grid.epsg)
            full=gpd.GeoDataFrame(pd.concat(frames,ignore_index=True),crs=config.grid.epsg)
            # Reserva de uma fração para dois intérpretes reais; A/B são slots, não nomes.
            rng=np.random.default_rng(config.resources.seed+5)
            double_n=max(2,math.ceil(len(samples)*config.reference.double_annotation_fraction))
            double=[]
            for case in ['main','adversarial']:
                ids=sorted(samples.loc[samples.case==case,'window_id'])
                double.append(ids[int(rng.integers(len(ids)))])
            remaining=sorted(set(samples.window_id)-set(double))
            double+=rng.choice(remaining,size=max(0,double_n-len(double)),replace=False).tolist()
            samples['double_annotation']=samples.window_id.isin(double)
            tasks=[];windows=[]
            for row in samples.itertuples():
                windows.append({'window_id':row.window_id,'case':row.case,'corridor_id':row.corridor_id,
                    'group_id':row.group_id,'fold':row.fold,'intended_use':row.intended_use,
                    'bounds':list(row.geometry.bounds),'double_annotation':row.double_annotation})
                for purpose in PURPOSES:
                    for slot in ['A','B'] if row.double_annotation else ['A']:
                        tasks.append({'task_id':f'{row.window_id}__{purpose}__{slot}','window_id':row.window_id,
                            'purpose':purpose,'reviewer_slot':slot,'review_state':'pendente','observer':'','review_date':'','notes':''})
            immutable=[]
            frame_path=directory/'quadro_amostral.gpkg';_vectors(frame_path,{'candidatas':full,'selecionadas':samples});immutable.append(frame_path)
            group_path=directory/'grupos_reservados.csv';pd.DataFrame(groups).to_csv(group_path,index=False);immutable.append(group_path)
            csv=directory/'amostras_administracao.csv';samples.drop(columns='geometry').to_csv(csv,index=False);immutable.append(csv)
            public=samples[['window_id','double_annotation','geometry']].copy();public['label_status']='pendente'
            context=public.copy();measurement=public.copy()
            context.geometry=[r.geometry.intersection(domains[r.case].context) for r in samples.itertuples()]
            measurement.geometry=[r.geometry.intersection(domains[r.case].measurement) for r in samples.itertuples()]
            sample_gpkg=directory/'amostras.gpkg'
            _vectors(sample_gpkg,{'janelas':public,'contextos':context,'medicao':measurement.loc[~measurement.is_empty].copy()});immutable.append(sample_gpkg)
            template=directory/'modelo_anotacoes.gpkg'
            for purpose in PURPOSES:
                pyogrio.write_dataframe(empty_annotations(config.grid.epsg,purpose),template,layer=purpose,
                    geometry_type='Point' if purpose=='altura' else 'MultiPolygon')
            immutable.append(template)
            template_tasks=directory/'modelo_tarefas.csv';pd.DataFrame(tasks).to_csv(template_tasks,index=False);immutable.append(template_tasks)
            schema=directory/'anotacao.schema.json';atomic_write_json(schema,Annotation.model_json_schema());immutable.append(schema)
            work=directory/'trabalho';work.mkdir()
            shutil.copyfile(template,work/'anotacoes.gpkg');shutil.copyfile(template_tasks,work/'tarefas.csv')
            catalog={'sources':{
                'lidar_rgb_xyz_2020':{'kind':'raw_lidar','path':'fontes_lidar.json','year':2020,'available':True,
                    'independent_algorithm':True,'independent_sensor':False,'restriction':'Manual interpretation from unclassified RGB/XYZ; same sensor, colorization not calibrated reflectance.'},
                'terreno_derivado_2020':{'kind':'derived_lidar','path':'fontes_lidar.json','year':2020,'available':True,
                    'independent_algorithm':False,'independent_sensor':False,'restriction':'Internal consistency only; H/DTM from stage 04 are not independent reference.'}},
                'external_images':inventory,'catalog_note':'year is observation epoch, not file creation year; new sources require actual dated evidence.'}
            source_template=directory/'modelo_fontes_referencia.json';atomic_write_json(source_template,catalog);immutable.append(source_template)
            shutil.copyfile(source_template,work/'fontes_referencia.json')
            for case,domain in domains.items():
                chosen=samples.loc[samples.case==case].copy()
                event('materialize_windows',case=case,count=len(chosen))
                paths,hcounts=clip_heights(config,chosen,sources[case]['products']['alturas_pontos.parquet'],directory);immutable+=paths
                paths,raw_counts,index=clip_lidar_rgb(config,domain,chosen,plans[case],directory,event);immutable+=paths
                if raw_counts!=hcounts:raise ValueError('Recortes LAZ/Parquet divergem; não aceitar material inconsistente')
                source_indices[case]=index
                for window_id,n in hcounts.items():
                    expected=int(samples.loc[samples.window_id==window_id,'points'].iloc[0])
                    if n!=expected:raise ValueError('Contagem da janela diverge do quadro amostral')
                immutable+=render_window_profiles(config,chosen,directory)
            provenance=directory/'fontes_lidar.json';atomic_write_json(provenance,{'raw_mds':source_indices,
                'terrain_sources':{case:s['entry'] for case,s in sources.items()},'input_fingerprints':inputs});immutable.append(provenance)
            plan={'schema_version':'0.1.0','epsg':config.grid.epsg,'windows':windows,'tasks':tasks,
                'annotation_labels':LABELS,'sampling':design,'groups':groups,'double_windows':sorted(double),
                'terrain_sources':{case:{'dtm':str(s['products']['primary_dtm']),'validity':str(s['products']['primary_validity'])} for case,s in sources.items()},
                'human_labels_created':0,'semantic_targets':{
                    'crown_low_high_shrubs':'Height/class proxies only; must be confirmed or rejected by human interpretation',
                    'roofs_posts':'LAS 1/6 and structural context are candidates; true presence unverified',
                    'water_shadows':'Low support and dark RGB are not proof; local independent 2020 images unavailable unless supplied',
                    'ground_edges_density':'Sampling/QC proxies; no automatic reference labels'},
                'split_limits':'One training corridor and one adversarial test corridor; QC already inspected. Not untouched municipal test.',
                'independent_height_reference_available':False,'independent_priority_target_available':False}
            plan_path=directory/'plano_referencia.json';atomic_write_json(plan_path,plan);immutable.append(plan_path)
            target_guide=directory/'GUIA_ANOTACAO.md';shutil.copyfile(guide,target_guide);immutable.append(target_guide)
            if env['qgis']['ok']:
                event('qgis_projects',version=env['qgis']['stdout'])
                process=subprocess.run([config.reference.qgis_python,str(Path(__file__).with_name('qgis_reference.py')),'--package',str(directory)],
                    capture_output=True,text=True,timeout=120,check=False)
                run.event('qgis_output',returncode=process.returncode,stdout=process.stdout,stderr=process.stderr)
                if process.returncode:raise RuntimeError('Falha ao gerar/reabrir projetos QGIS: '+process.stderr[-2000:])
                immutable += [directory/'anotacao_cega.qgz',directory/'qa_insumos.qgz',directory/'qgis_validacao.json']
            else:
                atomic_write_json(directory/'qgis_validacao.json',{'available':False,'instructions':str(target_guide),'human_inspection_performed':False})
                immutable.append(directory/'qgis_validacao.json')
            # O primeiro acesso OGR do QGIS pode acrescentar metadados internos ao GPKG.
            # Congelar depois de gerar/reabrir os projetos, sem alterar suas geometrias.
            seal=directory/'integridade_plano.json'
            atomic_write_json(seal,{'files':{name:fingerprint(directory/name) for name in ['plano_referencia.json','amostras.gpkg','grupos_reservados.csv']}})
            immutable.append(seal)
            assessment=check_annotations(directory)
            if not assessment['ok'] or assessment['completed_annotations'] or assessment['supervised_training_allowed']:
                raise ValueError('Pacote inicial deve ter somente rótulos pendentes e estrutura válida: '+str(assessment['errors']))
            for prior in inputs:
                if fingerprint(Path(prior['path']))!=prior:raise OSError('Entrada alterada durante preparo da referência')
            mutable=['trabalho/anotacoes.gpkg','trabalho/tarefas.csv','trabalho/fontes_referencia.json']
            result={'ok':True,'stage':'05','run_id':run.run_id,'package':str(directory),'preparation_complete':True,
                'windows':len(samples),'window_counts_by_case':samples.groupby('case').size().to_dict(),
                'frame_counts_by_case':full.groupby('case').size().to_dict(),'tasks':len(tasks),'double_windows':len(double),
                'human_labeling_status':'pendente','human_labels_created':0,'annotation_assessment':assessment,
                'sampling':design,'external_source_inventory':inventory,'group_reservation':groups,
                'products':[str(p) for p in immutable],'mutable_workfiles':mutable,
                'elapsed_seconds':time.monotonic()-started,'peak_process_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'limitations':['Semantic strata are candidate proxies, not confirmed trees/shrubs/roofs/posts/water/shadows.',
                    'Selection intentional; inclusion probabilities unknown and no municipal population weights.',
                    'RGB image is topmost-point color from LiDAR; same sensor, not orthophoto or calibrated reflectance.',
                    'Training/test reserved by entire intersecting corridor groups; pilot has only two different corridor types.',
                    'Both cases were inspected in earlier QC; reserve concerns future supervised adjustment, not pristine independent test.',
                    'No human labels or external height/priority truth were fabricated; supervised training/precision/recall remain blocked.',
                    'Working copies mutable and excluded from cache hashes; reruns never overwrite edits. Use check-annotations to assess current work.']}
            report=run.path/'referencia.json';atomic_write_json(report,result)
            report_md=run.path/'referencia.md';report_md.write_text(f"# Etapa 05 — preparação da referência\n\nPacote: `{directory}`\n\n"
                f"{len(samples)} janelas reais; {len(tasks)} tarefas; {len(double)} janelas para dupla anotação.\n\n"
                'Preparação concluída; rótulos humanos pendentes. Não há precisão/recall ou referência externa criada.\n\n'+
                '\n'.join('- '+text for text in result['limitations'])+'\n',encoding='utf-8')
            outputs=[report,report_md,*immutable]
            save_cache(cache_root,key,run.run_id,outputs)
            run.finish([*outputs,*[directory/p for p in mutable]])
            return {'ok':True,'run_id':run.run_id,'cache_hit':False,'manifest':str(run.path/'manifest.json'),
                    'report':str(report),'package':str(directory),'human_labeling_status':'pendente','pending_tasks':len(tasks)}
        except BaseException as error:
            run.fail(error,interrupted=isinstance(error,KeyboardInterrupt));raise
