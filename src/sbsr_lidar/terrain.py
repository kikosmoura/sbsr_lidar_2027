"""Etapa 04: terreno/altura do piloto, validação interna e mapas de suporte."""
from __future__ import annotations

import csv
import resource
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import shapely

from .doctor import existing_parent
from .domain import build_domain, input_plan
from .environment import environment_snapshot, source_digest
from .input_qc import grid_layout, write_raster, COUNT_NODATA
from .normalized_heights import stream_heights
from .preparation import _input_fingerprints, _vectors
from .runtime import Run, exclusive_lock
from .storage import fingerprint, atomic_write_json, read_json, cache_key, load_cache, save_cache
from .terrain_inputs import load_ground
from .terrain_surface import Surface, STATUS, error_metrics
from .terrain_validation import validate_surfaces, choose_method


def grid_xy(layout):
    rows,cols=np.nonzero(layout.context_mask)
    return np.column_stack([layout.transform.c+(cols+.5)*layout.resolution,
                            layout.transform.f-(rows+.5)*layout.resolution])


def evaluate(model,xy,radius,query_points):
    parts={}
    for start in range(0,len(xy),query_points):
        q=model.query(xy[start:start+query_points],radius)
        for key,values in q.items(): parts.setdefault(key,[]).append(values)
    return {key:np.concatenate(values) for key,values in parts.items()}


def terrain_run(config,case,*,requested_method='auto',use_cache=True):
    if requested_method not in {'auto','tin','idw'}: raise ValueError('Método deve ser auto/tin/idw')
    if not config.paths.mount_root.is_mount(): raise ValueError('HD externo não montado')
    if psutil.virtual_memory().available/2**30<config.resources.max_ram_gib:
        raise ValueError('RAM disponível inferior ao orçamento configurado')
    for path,minimum in [(config.paths.runs_root,config.resources.min_local_free_gib),
                         (config.paths.output_root,config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free/2**30<minimum: raise ValueError(f'Espaço abaixo da reserva: {path}')
    state=read_json(config.paths.state_file)
    if state.get('etapas',{}).get('03',{}).get('status')!='concluida':
        raise ValueError('Concluir etapa 03 antes de gerar terreno/altura')
    domain=build_domain(config,case)
    rows=input_plan(config,domain)
    if any(not r['selected_laz'] for r in rows): raise ValueError('LAZ faltante; completar a etapa 03 antes de prosseguir')
    layout=grid_layout(config,domain)
    xy=grid_xy(layout)
    radii=sorted(set(config.sensitivity.terrain_distances_m+[config.terrain.maximum_distance_m]))
    with exclusive_lock(config.paths.runs_root/'.terrain.lock'):
        environment=environment_snapshot(config.tools.pdal,config.tools.gdalinfo,config.tools.timeout_seconds)
        inputs=_input_fingerprints(config)+[fingerprint(Path(r['selected_laz'])) for r in rows]
        snapshot=config.model_dump(mode='json')
        snapshot['execution']={'case':case,'requested_method':requested_method}
        code=source_digest()
        command=f'terrain:{case}'
        key=cache_key(command=command,config=snapshot,inputs=inputs,code=code,environment=environment)
        cache_root=config.paths.runs_root/'cache'
        run=Run(config.paths.runs_root,config.paths.state_file,command,snapshot,inputs,environment,code,stage='04')
        started=time.monotonic()
        def event(name,**details):
            run.event(name,**details)
            print(f'{name}: {details}',file=sys.stderr,flush=True)
        try:
            cached=load_cache(cache_root,key) if use_cache else None
            if cached:
                outputs=[Path(x['path']) for x in cached['outputs']]
                run.finish(outputs,cache_hit=True,source_run_id=cached['source_run_id'])
                source=read_json(outputs[0])
                return {'ok':True,'case':case,'run_id':run.run_id,'cache_hit':True,'method':source['selected_method'],
                        'manifest':str(run.path/'manifest.json'),'report':str(outputs[0])}
            directory=config.paths.output_root/'etapa04'/case/run.run_id
            directory.mkdir(parents=True,exist_ok=False)
            outputs=[]
            def raster(name,values,*,dtype='float32',nodata=None,mask=None,description=None):
                if nodata is None: nodata=config.grid.nodata
                bands=[]
                for values_band in values if isinstance(values,list) else [values]:
                    array=np.full(layout.shape,nodata,dtype=dtype)
                    array[layout.context_mask]=np.where(np.isfinite(values_band),values_band,nodata)
                    if mask is not None: array[~mask]=nodata
                    bands.append(array)
                path=directory/name
                descriptions=description or [name]*len(bands)
                write_raster(path,bands,layout,epsg=config.grid.epsg,dtype=dtype,nodata=nodata,descriptions=descriptions,
                    tags={'stage':'04','meaning':'terrain_support_or_elevation_not_canopy','vertical_datum':config.terrain.expected_vertical_datum,
                          'geoid_correction_applied':'false','count_unit':'unique_MDT_XY_vertices_or_MDS_records_as_band_described'})
                outputs.append(path)
                return path
            event('terrain_start',case=case,tiles=domain.metadata['tiles'])
            ground,ground_report=load_ground(config,domain,rows,event)
            vertices=directory/'vertices_terreno.parquet'
            pd.DataFrame(ground,columns=['x','y','z']).to_parquet(vertices,index=False)
            outputs.append(vertices)
            validation,samples=validate_surfaces(ground,config,radii,event)
            validation_path=directory/'validacao_reservada.csv'
            pd.DataFrame(samples).to_csv(validation_path,index=False)
            outputs.append(validation_path)
            method,decision=choose_method(validation,config,requested_method)
            event('method_selected',method=method,rule=decision['rule'])
            model=Surface(ground,config.terrain)
            support={}
            baseline=None
            for radius in radii:
                event('terrain_grid',radius=radius,cells=len(xy))
                q=evaluate(model,xy,radius,config.terrain.query_points)
                label=f'{radius:g}'
                for algorithm in ['tin','idw']:
                    values=q[algorithm]
                    raster(f'dtm_{algorithm}_r{label}_contexto.tif',values)
                    raster(f'dtm_{algorithm}_r{label}_medicao.tif',values,mask=layout.measurement_mask)
                    raster(f'validade_{algorithm}_r{label}.tif',q[algorithm+'_status'],dtype='uint8',nodata=255)
                    stats={}
                    for region,mask in [('medicao',layout.measurement_mask),('borda',layout.edge_mask),('contexto',layout.context_mask)]:
                        select=mask[layout.context_mask]
                        n=int(select.sum())
                        valid=int(np.sum(select & np.isfinite(values)))
                        stats[region]={'cells':n,'valid_cells':valid,'nodata_cells':n-valid,'valid_fraction':valid/n if n else None}
                    support[f'{algorithm}_r{label}']=stats
                raster(f'contagem_mdt_r{label}.tif',q['count'],dtype='uint32',nodata=COUNT_NODATA,
                       description=['vertices_MDT_XY_unicos_dentro_do_raio'])
                if radius==config.terrain.maximum_distance_m:
                    baseline=q
                    raster('distancia_mdt_mais_proximo.tif',q['nearest'])
                    raster('triangulos_qc.tif',[q['triangle_edge'],q['circumradius']],description=['aresta_maxima_m','circunraio_m'])
            # Comparação com terreno recortado em P ANTES de interpolar, na mesma grade.
            core_mask=shapely.intersects_xy(domain.measurement,ground[:,0],ground[:,1])
            no_context=Surface(ground[core_mask],config.terrain)
            q_without=evaluate(no_context,xy,config.terrain.maximum_distance_m,config.terrain.query_points)
            with_values=baseline[method]
            without_values=q_without[method]
            raster('dtm_sem_contexto_medicao.tif',without_values,mask=layout.measurement_mask)
            raster('efeito_contexto_dtm.tif',with_values-without_values,mask=layout.measurement_mask)
            edge={}
            for label,mask in [('medicao',layout.measurement_mask),('borda',layout.edge_mask),('interior',layout.measurement_mask & ~layout.edge_mask)]:
                select=mask[layout.context_mask]
                a=np.isfinite(with_values)&select
                b=np.isfinite(without_values)&select
                common=a & b
                edge[label]={'cells':int(select.sum()),'valid_with_context':int(a.sum()),'valid_without_context':int(b.sum()),
                    'gained_valid_cells':int(np.sum(a & ~b)),'lost_valid_cells':int(np.sum(b & ~a)),
                    'difference_with_minus_without':error_metrics((with_values-without_values)[common])}
            # Perfis cartesianos de inspeção: não são eixo longitudinal validado do corredor.
            representative=domain.measurement.representative_point()
            xmin,ymin,xmax,ymax=domain.context.bounds
            profiles=[]
            for axis,coords in [('E_W',np.column_stack([np.arange(xmin,xmax,layout.resolution),
                                                     np.full(len(np.arange(xmin,xmax,layout.resolution)),representative.y)])),
                                ('N_S',np.column_stack([np.full(len(np.arange(ymin,ymax,layout.resolution)),representative.x),
                                                       np.arange(ymin,ymax,layout.resolution)]))]:
                coords=coords[shapely.intersects_xy(domain.context,coords[:,0],coords[:,1])]
                if not len(coords): continue
                q=evaluate(model,coords,config.terrain.maximum_distance_m,config.terrain.query_points)
                for i in range(len(coords)):
                    profiles.append({'profile':axis,'x':coords[i,0],'y':coords[i,1],
                        'tin':q['tin'][i],'idw':q['idw'][i],'nearest_mdt_m':q['nearest'][i],
                        'tin_status':q['tin_status'][i],'idw_status':q['idw_status'][i]})
            profile_path=directory/'perfis_cartesianos.csv'
            pd.DataFrame(profiles).to_csv(profile_path,index=False)
            outputs.append(profile_path)
            height_report,height_path,cell_counts,flagged=stream_heights(config,domain,rows,model,method,layout,directory,event)
            outputs.append(height_path)
            raster('contagens_altura.tif',[a[layout.context_mask] for a in cell_counts],dtype='uint32',nodata=COUNT_NODATA,
                   description=['MDS_registros_contexto','MDS_registros_H_valido','MDS_registros_H_menor_que_alerta_negativo'])
            flagged_path=directory/'pontos_alerta_amostra.csv'
            pd.DataFrame(flagged,columns=['source_tile','source_point_index','x','y','z_absolute','h','classification','qc_flags']).to_csv(flagged_path,index=False)
            outputs.append(flagged_path)
            import geopandas as gpd
            aoi=directory/'dominios.gpkg'
            _vectors(aoi,{'medicao':gpd.GeoDataFrame({'corridor_id':[domain.corridor_id]},geometry=[domain.measurement],crs=config.grid.epsg),
                          'contexto':gpd.GeoDataFrame({'corridor_id':[domain.corridor_id]},geometry=[domain.context],crs=config.grid.epsg),
                          'quadriculas':domain.nominal_tiles[['quadricula','geometry']]})
            outputs.append(aoi)
            for prior in inputs:
                if fingerprint(Path(prior['path']))!=prior: raise OSError('Insumo mudou durante terreno/altura')
            report={'ok':True,'stage':'04','run_id':run.run_id,'domain':domain.metadata,
                    'selected_method':method,'selection':decision,'primary_radius_m':config.terrain.maximum_distance_m,
                    'radii_m':radii,'grid':{'resolution_m':layout.resolution,'transform':list(layout.transform)[:6],
                                         'shape':list(layout.shape),'nodata':config.grid.nodata},
                    'ground':ground_report,'validation':validation,'support':support,'edge_comparison':edge,
                    'heights':height_report,'terrain_status_codes':{**STATUS,6:'input_point_excluded_by_qc'},
                    'elapsed_seconds':time.monotonic()-started,
                    'peak_process_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                    'products':[str(p) for p in outputs],
                    'limitations':['Validação interna de interpolação/consistência entre produtos relacionados; não acurácia absoluta independente.',
                        'MDT classe original preservada; nenhuma correção geoidal ou remapeamento de classe aplicado.',
                        'H usa a superfície contínua TIN/IDW nos XY, em float64; GeoTIFF é avaliação float32 nos centros da grade, sem segunda normalização.',
                        'Propriedade por folha nominal elimina halos de exportação sobrepostos; duplicatas de registros MDS dentro da mesma folha permanecem.',
                        'Z e classificação originais preservados; H ausente é null/NoData e alturas negativas/extremas não são truncadas.',
                        'Água e pontes não receberam rótulos manuais; flags LAS 9/17 são apenas pistas de classe, não validação da ausência dessas feições.',
                        'IDW limitado a oito vizinhos e mínimo configurado, ao raio, à envoltória/triângulo suportado e à distribuição angular local.',
                        'TIN/árvore construídos em memória somente com MDT da janela; limite de vértices explícito, sem promessa de streaming de triangulação.',
                        'Amostra de alertas contém os primeiros 1000 alertas; não é amostra representativa. Perfis são cartesianos de inspeção.',
                        'Não foram produzidos rótulos, máscara arbórea, segmentação ou indicadores das etapas posteriores.']}
            report_path=run.path/'qc_altimetrico.json'
            atomic_write_json(report_path,report)
            report_md=run.path/'qc_altimetrico.md'
            lines=[f"# QC altimétrico — {case} / {domain.corridor_id}", '',
                   f"Execução `{run.run_id}`; método {method}; raio principal {config.terrain.maximum_distance_m} m.",
                   f"Vértices MDT: {len(ground)}; tempo: {report['elapsed_seconds']:.2f} s; pico RSS: {report['peak_process_rss_mib']:.2f} MiB.",'',
                   '|Cenário|Células de medição|DTM válido|NoData|','|---|---:|---:|---:|']
            for scenario,values in support.items():
                s=values['medicao']
                lines.append(f"|{scenario}|{s['cells']}|{s['valid_cells']}|{s['nodata_cells']}|")
            lines+=['','## Limites','']+['- '+s for s in report['limitations']]
            lines+=['','## Produtos','']+['- `'+str(p)+'`' for p in outputs]
            report_md.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            outputs=[report_path,report_md,*outputs]
            save_cache(cache_root,key,run.run_id,outputs)
            run.finish(outputs)
            return {'ok':True,'case':case,'run_id':run.run_id,'cache_hit':False,'method':method,
                    'manifest':str(run.path/'manifest.json'),'report':str(report_path),'products_root':str(directory)}
        except BaseException as error:
            run.fail(error,interrupted=isinstance(error,KeyboardInterrupt))
            raise
