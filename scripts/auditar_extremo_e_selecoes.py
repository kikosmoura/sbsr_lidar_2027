"""Conferir o par máximo e a permanência das listas em fontes já produzidas."""
from pathlib import Path
import json
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio
import shapely
from scipy import ndimage

from sbsr_lidar.config import load_config
from sbsr_lidar.crown_data import deduplicate_ground
from sbsr_lidar.indicator_support import RasterSupport,UnitAssigner
from sbsr_lidar.pair_review import retained_returns,describe_returns,top_turnover
from sbsr_lidar.terrain_surface import Surface
from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json


class Checked:
    def __init__(self): self.records={}
    def add(self,path,expected=None):
        fp=fingerprint(Path(path))
        if expected is not None and fp!=expected: raise ValueError(f'Fonte alterada: {path}')
        self.records[fp['path']]=fp
        return Path(path)


def replay_terrain(config,case,points,measurement,checked):
    normalized=Path(case['normalized_source']).parent
    index=read_json(checked.add(normalized.parent/'raw/index.json'))
    windows=read_json(checked.add(normalized/'normalization.json'))['windows']
    reports=[]
    for (wx,wy),group in points.groupby([np.floor(points.x/200).astype(int),np.floor(points.y/200).astype(int)]):
        context=measurement.buffer(20.)
        region=shapely.box(wx*200,wy*200,(wx+1)*200,(wy+1)*200).buffer(10.,join_style='mitre').intersection(context)
        ground=[]
        for bucket in index['buckets']:
            if bucket['product']!='MDT' or abs(bucket['wx']-wx)>1 or abs(bucket['wy']-wy)>1:continue
            path=Path(bucket['path']);seal=read_json(checked.add(path.parent/'complete.json'))
            fp=next(x for x in seal['outputs'] if x['path']==str(path));frame=pd.read_parquet(checked.add(path,fp))
            use=((frame.qc_flags.to_numpy()&2)==0)&shapely.intersects_xy(region,frame.x,frame.y)
            if use.any():ground.append(frame.loc[use,['x','y','z_absolute']].to_numpy())
        xyz=deduplicate_ground(np.concatenate(ground),config)
        expected=next(w for w in windows if (w['wx'],w['wy'])==(wx,wy))
        if len(xyz)!=expected['unique_ground_vertices']:raise ValueError('Vértices MDT diferentes da janela original')
        prediction=Surface(xyz,config.terrain).query(group[['x','y']].to_numpy(),5.)
        delta=np.abs(prediction['tin']-group.terrain_z.to_numpy())
        if not (prediction['tin_status']==0).all() or not np.isfinite(delta).all() or delta.max()>1e-9:
            raise ValueError('TIN do par não reproduz as alturas registradas')
        reports.append({'wx':int(wx),'wy':int(wy),'selected_records_checked':len(group),
            'unique_ground_vertices':len(xyz),'max_terrain_difference_m':float(delta.max()),
            'max_nearest_MDT_distance_m':float(prediction['nearest'].max()),
            'max_triangle_edge_m':float(prediction['triangle_edge'].max()),
            'all_retained_terrain_status_valid':True,
            'source_level':'preserved_decoded_MDT_blocks_not_new_LAZ_decode_or_external_reference'})
    return reports


def analyze(project,out):
    checked=Checked();prior=read_json(project/'docs/manifesto_revisao_interpretacao.json')
    inv={x['path']:x for x in prior['artifacts']}
    p32=Path(read_json(project/'relatorios/revisao_interpretacao/ultima_execucao.json')['output_root'])
    pairpath=p32/'pares16_preservados.csv';pairs=pd.read_csv(checked.add(pairpath,inv[str(pairpath)]))
    selected=pairs.sort_values(['absolute_P95_difference_m','unit_i','unit_j'],ascending=[False,True,True]).iloc[0]
    ids=[selected.unit_i,selected.unit_j];cid=selected.corridor_i
    run=read_json(project/'relatorios/etapa12/execucao.json');case=run['case_results'][cid];root=Path(case['root'])
    original={x['path']:x for x in read_json(project/'docs/manifesto_etapa12.json')['artifacts']}
    sealpath=root/'complete.json';seal=read_json(checked.add(sealpath,original[str(sealpath)]))
    outputs={x['path']:x for x in seal['outputs']}
    def case_file(relative):
        path=root/relative;return checked.add(path,outputs[str(path)])
    config=load_config(project/'configs/terreno_congelado_etapa04.yaml')
    units=gpd.read_parquet(case_file('primary/coorte_50m.parquet')).sort_values('unit_id').reset_index(drop=True)
    targets=units.loc[units.unit_id.isin(ids)].set_index('unit_id',drop=False).loc[ids]
    if len(targets)!=2 or not targets.eligible_A_plus_3D.all():raise ValueError('Par extremo diferente da coorte primária')
    arrays={};transform=None
    for key in ['observation','uncertainty','terrain_valid']:
        with rasterio.open(case_file(f'rasters_r1_f1/{key}.tif')) as f:
            arrays[key]=f.read(1);transform=f.transform
    with rasterio.open(case_file('primary/labels.tif')) as f:labels=f.read(1)
    mask=np.where(arrays['observation']==1,(labels>0).astype('uint8'),255).astype('uint8')
    support=RasterSupport(arrays['observation'],mask,arrays['uncertainty'],arrays['terrain_valid'].astype(bool),transform,31983)
    assigner=UnitAssigner(units,support)
    patches=gpd.read_parquet(case_file('primary/manchas_conectadas.parquet'))
    crown=shapely.union_all(patches.geometry.to_numpy());shapely.prepare(crown)
    cc,_=ndimage.label(mask==1,structure=np.ones((3,3),dtype=np.uint8))
    path=Path(case['normalized_source']);merge=read_json(checked.add(path.parent/'merge_complete.json'))
    fp=next(x for x in merge['outputs'] if x['path']==str(path));checked.add(path,fp)
    pieces={u:[] for u in ids}
    extent=shapely.union_all(targets.geometry.to_numpy()).envelope.bounds
    x0,y0,x1,y1=extent
    for batch in pq.ParquetFile(path).iter_batches(batch_size=65536):
        frame=batch.to_pandas();use=frame.x.between(x0,x1)&frame.y.between(y0,y1)
        frame=frame.loc[use].copy()
        if frame.empty:continue
        owner=assigner.assign(frame.x.to_numpy(),frame.y.to_numpy())
        uid=np.array([units.iloc[i].unit_id if i>=0 else '' for i in owner])
        use=np.isin(uid,ids);frame=frame.loc[use].copy();uid=uid[use]
        if frame.empty:continue
        rr,cols,inside=support.indices(frame.x.to_numpy(),frame.y.to_numpy())
        frame['raster_row']=rr;frame['raster_col']=cols
        frame['observed']=inside&(arrays['observation'][rr,cols]==1)
        frame['inside_estimated_canopy']=(mask[rr,cols]==1)&shapely.intersects_xy(crown,frame.x,frame.y)
        frame['uncertain_pixel']=(arrays['uncertainty'][rr,cols]!=0)&(arrays['uncertainty'][rr,cols]!=65535)
        frame['patch_component']=cc[rr,cols]
        frame['retained_original']=retained_returns(frame)
        for u in ids:
            part=frame.loc[uid==u].copy()
            if len(part):pieces[u].append(part)
    summaries={};patch_rows=[];all_selected=[]
    for index,u in enumerate(ids):
        frame=pd.concat(pieces[u],ignore_index=True);unit=targets.loc[u]
        frame['unit_id']=u
        frame['distance_to_unit_boundary_m']=shapely.distance(shapely.points(frame.x,frame.y),unit.geometry.boundary)
        frame.to_parquet(out/f'retornos_unidade_{index+1}.parquet',index=False)
        retained=frame.loc[frame.retained_original].copy();all_selected.append(retained)
        info=describe_returns(retained)
        if info['n']!=int(unit.n_vegetation_records) or abs(info['P95_m']-unit.I6)>1e-9 or abs(info['IQR_m']-unit.I7)>1e-9:
            raise ValueError('Contagem/percentis do par não reproduzidos')
        if len(frame)!=int(unit.n_mds_records):raise ValueError('Propriedade ou contagem total de registros divergente')
        for component,group in retained.groupby('patch_component'):
            patch=patches.loc[patches.component_label.eq(component)].iloc[0]
            patch_rows.append({'unit_id':u,'component_label':int(component),'n_records':len(group),
                'P95_m':float(np.quantile(group.h,.95)),'touches_context_limit':bool(patch.touches_context_limit),
                'touches_invalid_support':bool(patch.touches_invalid_support)})
        info.update({'unit_id':u,'total_mds_records':len(frame),'fraction_observed':float(unit.fraction_observed),
            'I1':float(unit.I1),'I4':float(unit.I4),'area_observed_m2':float(unit.area_observed_m2),
            'area_canopy_m2':float(unit.area_canopy_m2),'uncertain_area_m2':float(unit.area_classification_uncertain_m2),
            'n_patches':int(unit.n_patches),'n_context_censored':int(unit.n_patches_context_censored),
            'n_support_censored':int(unit.n_patches_support_censored),
            'without_uncertain_pixels':describe_returns(retained.loc[~retained.uncertain_pixel]),
            'interior_1m':describe_returns(retained.loc[retained.distance_to_unit_boundary_m>=1.]),
            'classification_or_tree_identity_externally_confirmed':False})
        summaries[u]=info
    pd.DataFrame(patch_rows).to_csv(out/'contribuicao_manchas.csv',index=False)
    frozen=gpd.read_parquet(checked.add(Path(run['products_root'])/'selecao_corredores_congelada.parquet',original[str(Path(run['products_root'])/'selecao_corredores_congelada.parquet')]))
    measurement=frozen.loc[frozen.corridor_id.eq(cid)].iloc[0].geometry
    terrain=replay_terrain(config,case,pd.concat(all_selected,ignore_index=True),measurement,checked)
    source_analysis=Path(read_json(project/'relatorios/etapa17/ultima_analise.json')['output_root'])
    m17={x['path']:x for x in read_json(project/'docs/manifesto_etapa17.json')['artifacts']}
    rankings_path=source_analysis/'estabilidade_rankings.csv';ranks=pd.read_csv(checked.add(rankings_path,m17[str(rankings_path)]))
    old_path=source_analysis/'estabilidade_comparisons.csv';old=pd.read_csv(checked.add(old_path,m17[str(old_path)]))
    stats=[];members=[]
    r=ranks.loc[ranks.analysis_method.eq('A_plus_3D')]
    for scenario,group in r.groupby('scenario_id'):
        a=group.loc[group.measurement.eq('primary_on_pair_support')];b=group.loc[group.measurement.eq('scenario_on_pair_support')]
        turn=top_turnover(a,b)
        row=old.loc[old.scenario_id.eq(scenario)&old.cohort.eq('strict_fixed')&old.method.eq('A_plus_3D')&old.contrast.eq('method_on_pair_support')].iloc[0]
        rho=float(a.set_index('unit_id').rank_mean.corr(b.set_index('unit_id').rank_mean))
        if abs(rho-row.spearman_rho)>1e-12 or abs(turn['jaccard']-row.jaccard_exact)>1e-12 or turn['shared_n']!=row.top_intersection_n:
            raise ValueError('Reconstrução de seleção/rho difere do complemento17')
        members.append({'scenario_id':scenario,**turn})
        stats.append({'scenario_id':scenario,'spearman_rho':rho,**{k:v for k,v in turn.items() if not isinstance(v,list)}})
    selections=pd.DataFrame(stats);selections.to_csv(out/'permanencia_selecoes.csv',index=False)
    atomic_write_json(out/'membros_selecoes.json',{'scenarios':members,'inclusion_not_a_probability':True})
    all_pairs_path=source_analysis/'complementaridade_primary.csv';all_pairs=pd.read_csv(checked.add(all_pairs_path,m17[str(all_pairs_path)]))
    influence={}
    for label,data in [('disjoint16',pairs),('matched25',all_pairs)]:
        remove=data.unit_i.eq(selected.unit_i)&data.unit_j.eq(selected.unit_j)
        if int(remove.sum())!=1:raise ValueError('Par extremo ausente ou repetido')
        remaining=data.loc[~remove]
        influence[label]={'n_original':len(data),'n_without_max_pair':len(remaining),
            'median_abs_P95_original_m':float(data.absolute_P95_difference_m.median()),
            'median_abs_P95_without_max_pair_m':float(remaining.absolute_P95_difference_m.median()),
            'primary_selection_unchanged':True,'post_result_influence_description_only':True}
    one,two=(summaries[u] for u in ids)
    result={'revision':'0.3.3-revisao-quantitativa','source_run_id':run['run_id'],'corridor_id':cid,
        'unit_i':ids[0],'unit_j':ids[1],'units':summaries,
        'absolute_P95_difference_m':abs(one['P95_m']-two['P95_m']),
        'absolute_IQR_difference_m':abs(one['IQR_m']-two['IQR_m']),
        'original_cover_difference':float(selected.absolute_coverage_difference),
        'original_fragmentation_rank_difference':float(selected.absolute_fragmentation_rank_difference),
        'original_observed_area_ratio':float(selected.observed_area_ratio),
        'centroid_distance_m':float(selected.centroid_distance_m),
        'normalization_replay':terrain,'influence':influence,
        'top_replacements_min':int(selections.lost_n.min()),'top_replacements_max':int(selections.lost_n.max()),
        'density25_selection':selections.loc[selections.scenario_id.eq('density_0.25')].iloc[0].to_dict(),
        'arithmetic_consistency_passed':True,'external_semantic_or_altimetric_validation_performed':False,
        'max_pair_retained_in_primary_results':True,'new_LAZ_decode_or_PyCrown':False}
    atomic_write_json(out/'resultados.json',result)
    atomic_write_json(out/'fontes_utilizadas.json',{'inputs':list(checked.records.values()),
        'code':[fingerprint(project/'src/sbsr_lidar/pair_review.py'),fingerprint(Path(__file__))],
        'scope':'historical_case_seals_and_current_decoded_checkpoints_not_external_reference'})
    targets.to_file(out/'unidades_par_maximo.gpkg',layer='par_maximo',driver='GPKG',index=False)
    diagnostic_figure(out,targets)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def diagnostic_figure(out,units):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr_revisao_final_matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Times New Roman','font.size':8,'axes.labelsize':8,
        'xtick.labelsize':7.5,'ytick.labelsize':7.5,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axes=plt.subplots(3,2,figsize=(178/25.4,170/25.4))
    fig.subplots_adjust(left=.10,right=.98,bottom=.08,top=.80,hspace=.43,wspace=.28)
    for index,u in enumerate(units.itertuples()):
        frame=pd.read_parquet(out/f'retornos_unidade_{index+1}.parquet');a=frame.loc[frame.retained_original];other=frame.loc[~frame.retained_original&np.isfinite(frame.h)]
        x0,y0,_,_=u.geometry.bounds
        ax=axes[0,index]
        ax.scatter(other.x-x0,other.y-y0,s=.3,color='#b5b5b5',rasterized=True)
        ax.scatter(a.x-x0,a.y-y0,c=a.h,vmin=0,vmax=35,cmap='viridis',s=2,rasterized=True)
        gpd.GeoSeries([u.geometry]).translate(xoff=-x0,yoff=-y0).boundary.plot(ax=ax,color='black',linewidth=.7)
        ax.set_aspect('equal');ax.set_xlabel('E local (m)');ax.set_ylabel('N local (m)');ax.set_title(f'{index+1}: X{u.grid_x}/Y{u.grid_y}\n{len(a)} retornos selecionados')
        ax=axes[1,index]
        ax.scatter(other.x-x0,other.h,s=.5,color='#b5b5b5',rasterized=True)
        ax.scatter(a.x-x0,a.h,s=2,c=a.h,vmin=0,vmax=35,cmap='viridis',rasterized=True)
        ax.set_xlabel('Projeção em E local (m)');ax.set_ylabel('H (m)');ax.set_ylim(-2,38)
        ax=axes[2,index]
        for label,subset,style in [('Máscara original',a,'-'),('Sem pixel incerto',a.loc[~a.uncertain_pixel],'--')]:
            h=np.sort(subset.h)
            if len(h):ax.plot(h,np.arange(1,len(h)+1)/len(h),style,lw=1,label=label)
        ax.axhline(.95,color='#888888',lw=.6);ax.set_xlim(0,38);ax.set_ylim(0,1.02)
        ax.set_xlabel('H dos retornos selecionados (m)');ax.set_ylabel('Fração acumulada');ax.legend(loc='lower right',fontsize=7,frameon=False)
    fig.suptitle('Conferência interna do par máximo — CO_PR_02\nCor: H (0–35 m) dos selecionados; cinza: demais retornos\nSem validação externa de identidade arbórea ou altura',fontsize=9)
    for suffix in ['pdf','svg','png']:fig.savefig(out/f'diagnostico_par_maximo.{suffix}',dpi=400)
    plt.close(fig)


if __name__=='__main__':
    project=Path(__file__).resolve().parents[1]
    out=Path(read_json(project/'relatorios/revisao_final_quantitativa/ultima_execucao.json')['output_root'])
    analyze(project,out)
