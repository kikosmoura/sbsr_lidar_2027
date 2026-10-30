"""Diagnósticos internos de terreno e costuras; não medem acurácia externa."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from .crown_data import completed,deduplicate_ground,query
from .storage import fingerprint,atomic_write_json
from .terrain_surface import Surface,error_metrics
from .terrain_validation import validate_surfaces


def window_ground(config,design,domain,buckets,wx,wy):
    size=design.window_size_m
    region=shapely.box(wx*size,wy*size,(wx+1)*size,(wy+1)*size).buffer(design.terrain_context_m,join_style='mitre').intersection(domain.context)
    parts=[]
    for r in buckets:
        if r['product']!='MDT' or abs(r['wx']-wx)>1 or abs(r['wy']-wy)>1:continue
        f=pd.read_parquet(r['path']);use=((f.qc_flags.to_numpy()&2)==0)&shapely.intersects_xy(region,f.x.to_numpy(),f.y.to_numpy())
        if use.any():parts.append(f.loc[use,['x','y','z_absolute']].to_numpy())
    n=sum(len(p) for p in parts)
    if n>design.maximum_ground_vertices_per_window:raise ValueError('Validação excede orçamento de terreno')
    return deduplicate_ground(np.concatenate(parts),config) if n else np.empty((0,3))


def internal_validation(config,design,domain,buckets,reports,height_path,root,event):
    root.mkdir(parents=True,exist_ok=True);seal=root/'complete.json'
    if completed(seal):return root/'validation.json'
    ordered=sorted(reports,key=lambda r:hashlib.sha256(f'{design.seed}:{r["wx"]}:{r["wy"]}'.encode()).hexdigest())
    sampled=ordered[:3];validations=[];seams=[]
    cfg=config.model_copy(update={'terrain':config.terrain.model_copy(update={'validation_max_points':2000})})
    for r in sampled:
        wx,wy=r['wx'],r['wy'];xyz=window_ground(config,design,domain,buckets,wx,wy)
        if len(xyz)<10:validations.append({'wx':wx,'wy':wy,'status':'insufficient_ground'});continue
        try:
            v,_=validate_surfaces(xyz,cfg,[config.terrain.maximum_distance_m],event)
            validations.append({'wx':wx,'wy':wy,**v})
        except ValueError as e:validations.append({'wx':wx,'wy':wy,'status':'degenerate_geometry','reason':str(e)})
        model=Surface(xyz,config.terrain);parts=[]
        for path in r['height_parts']:
            f=pd.read_parquet(path,columns=['x','y','terrain_z','terrain_status'])
            use=f.terrain_status.eq(0)&((abs(f.x-(wx+1)*200)<=1)|(abs(f.y-(wy+1)*200)<=1))
            if use.any():parts.append(f.loc[use])
        if not parts:continue
        f=pd.concat(parts,ignore_index=True)
        if len(f)>500:f=f.sample(500,random_state=design.seed)
        for dx,dy in [(1,0),(0,1)]:
            if not any(t['wx']==wx+dx and t['wy']==wy+dy for t in reports):continue
            use=(abs(f.x-(wx+1)*200)<=1) if dx else (abs(f.y-(wy+1)*200)<=1);test=f.loc[use]
            if not len(test):continue
            ground=window_ground(config,design,domain,buckets,wx+dx,wy+dy)
            try:neighbor=Surface(ground,config.terrain)
            except ValueError:continue
            z,status=query(neighbor,test[['x','y']].to_numpy(),config)
            seams.append({'window':[wx,wy],'neighbor':[wx+dx,wy+dy],'tested':len(test),'both_valid':int((status==0).sum()),
                'neighbor_lost_support':int((status!=0).sum()),'terrain_difference_m':error_metrics(z-test.terrain_z.to_numpy())})
    counts={'records':0,'valid_H':0,'negative_H':0,'H_below_minus1':0,'H_above80':0,'measurement_records':0}
    difference=[];sample_n=0;seen={};duplicate=0
    headers={r['tile']:r['declared_points'] for r in __import__('json').loads((root.parent/'raw/index.json').read_text())['sources'] if r['product']=='MDS'}
    for batch in pq.ParquetFile(height_path).iter_batches(batch_size=65536):
        f=batch.to_pandas();h=f.h.to_numpy();valid=np.isfinite(h)
        counts['records']+=len(f);counts['valid_H']+=int(valid.sum());counts['negative_H']+=int((h<0).sum())
        counts['H_below_minus1']+=int((h<config.terrain.negative_warning_m).sum());counts['H_above80']+=int((h>config.terrain.extreme_height_m).sum())
        counts['measurement_records']+=int(f.in_measurement.sum())
        for tile,part in f.groupby('source_tile'):
            tracker=seen.setdefault(tile,np.zeros(headers[tile],dtype=bool));indices=part.source_point_index.to_numpy()
            duplicate+=int(tracker[indices].sum())+len(indices)-len(np.unique(indices));tracker[indices]=True
        if valid.any() and not np.allclose(h[valid],f.z_absolute.to_numpy()[valid]-f.terrain_z.to_numpy()[valid],atol=1e-9,rtol=0):raise ValueError('H inconsistente com Z-terreno')
        if sample_n<10000:
            values=(h-f.user_data.to_numpy())[valid][:10000-sample_n];difference.append(values);sample_n+=len(values)
    if duplicate:raise ValueError('Retornos MDS com mais de um dono no corredor')
    record={'scope':'internal_consistency_and_held_out_same_sensor_terrain_not_external_accuracy',
        'selection_rule':'first3_window_SHA256(seed,wx,wy)_not_selected_by_error','windows_tested':len(sampled),'windows_total':len(reports),
        'terrain_holdout':validations,'seam_checks':seams,'height_counts':counts,'duplicate_source_id_records':duplicate,
        'H_minus_user_data_first10000_valid_records_diagnostic':error_metrics(np.concatenate(difference) if difference else np.empty(0)),
        'user_data_is_not_independent_reference':True,'external_accuracy_validated':False}
    path=root/'validation.json';atomic_write_json(path,record);atomic_write_json(seal,{'outputs':[fingerprint(path)]});return path
