"""CHM sem preenchimento, backend PyCrown original isolado e produtos espaciais."""
from pathlib import Path
from dataclasses import asdict
import json
import subprocess
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from rasterio.features import shapes
from scipy import ndimage
import shapely
from shapely.geometry import shape,Point

from .input_qc import grid_layout,write_raster
from .canopy_features import point_cells
from .canopy_masks import observation_mask,patch_layers,observed_geometry
from .indicator_support import RasterSupport
from .spatial_units import polygonal,frame
from .sensitivity_scenarios import thinning_uniform
from .storage import atomic_write_json,fingerprint,read_json
from .crown_data import completed


def thin_source(source,dest,fraction,seed):
    if fraction==1:return source
    if completed(dest.with_suffix('.json')):return dest
    dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_suffix('.part.parquet');writer=None;rows=0
    try:
        for batch in pq.ParquetFile(source).iter_batches(batch_size=65536):
            f=batch.to_pandas();keep=thinning_uniform(f.source_tile,f.source_point_index,seed)<fraction
            table=pa.Table.from_pandas(f.loc[keep],preserve_index=False)
            if writer is None:writer=pq.ParquetWriter(temp,table.schema,compression='zstd')
            writer.write_table(table);rows+=len(table)
    finally:
        if writer is not None:writer.close()
    temp.replace(dest);atomic_write_json(dest.with_suffix('.json'),{'fraction':fraction,'seed':seed,'rows':rows,'outputs':[fingerprint(dest)]})
    return dest


def raster_inputs(config,design,domain,height_path,reports,resolution,root):
    cfg=config.model_copy(update={'grid':config.grid.model_copy(update={'resolution_m':resolution})})
    layout=grid_layout(cfg,domain)
    if layout.width*layout.height>design.maximum_raster_cells:raise ValueError('CHM excede orçamento de células')
    seal=root/'complete.json'
    if not completed(seal):
        root.mkdir(parents=True,exist_ok=True)
        counts={k:np.zeros(layout.shape,dtype=np.uint32) for k in ['all','usable','valid_h']}
        chm=np.full(layout.shape,-np.inf,dtype=np.float32);class1=np.zeros(layout.shape,dtype=bool)
        outside=0;total=0
        for batch in pq.ParquetFile(height_path).iter_batches(batch_size=65536):
            f=batch.to_pandas();cell,inside=point_cells(layout,f.x.to_numpy(),f.y.to_numpy());outside+=int((~inside).sum());total+=len(f)
            h=f.h.to_numpy();usable=(f.qc_flags.to_numpy()&2)==0
            valid=usable&np.isfinite(h)&f.terrain_status.eq(0).to_numpy()
            for k,use in [('all',inside),('usable',inside&usable),('valid_h',inside&valid)]:
                np.add.at(counts[k].ravel(),cell[use],1)
            use=inside&valid&f.classification.isin(config.vegetation.classes).to_numpy()
            np.maximum.at(chm.ravel(),cell[use],h[use].astype('float32'))
            use=inside&valid&f.classification.eq(1).to_numpy()&(h>=2)
            class1.ravel()[cell[use]]=True
        terrain=np.full(layout.shape,np.nan,dtype=np.float32);terrain_valid=np.zeros(layout.shape,dtype=bool)
        for item in reports:
            f=pd.read_parquet(item['centers'][f'{resolution:g}']);cell,inside=point_cells(layout,f.x.to_numpy(),f.y.to_numpy())
            use=inside&f.status.eq(0).to_numpy();terrain.ravel()[cell[use]]=f.z.to_numpy()[use];terrain_valid.ravel()[cell[use]]=True
        obs,valid=observation_mask(layout,counts,terrain_valid)
        chm[valid&~np.isfinite(chm)]=0.;chm[~valid]=np.nan
        flags=np.zeros(layout.shape,dtype='uint16');flags[valid&class1]|=1;flags[~valid]=65535
        tags={'stage':'12','protocol_version':'0.3.0','accuracy_validated':'false','gap_filling':'none','height_formula':'Z_absolute-continuous_TIN5(X,Y)'}
        outputs=[]
        for name,a,dtype,nodata in [('chm',chm,'float32',np.nan),('terrain',terrain,'float32',np.nan),
            ('terrain_valid',terrain_valid,'uint8',255),('observation',obs,'uint8',255),('uncertainty',flags,'uint16',65535)]:
            path=root/f'{name}.tif';write_raster(path,[a],layout,epsg=config.grid.epsg,dtype=dtype,nodata=nodata,descriptions=[name],tags=tags);outputs.append(path)
        path=root/'counts.tif';write_raster(path,list(counts.values()),layout,epsg=config.grid.epsg,dtype='uint32',nodata=4294967295,descriptions=list(counts),tags=tags);outputs.append(path)
        atomic_write_json(seal,{'source_records':total,'records_outside_center_context_grid':outside,'outputs':[fingerprint(p) for p in outputs]})
    arrays={}
    for name in ['chm','terrain','terrain_valid','observation','uncertainty']:
        with rasterio.open(root/f'{name}.tif') as ds:arrays[name]=ds.read(1)
    return layout,arrays


def run_worker(config,design,layout,arrays,scenario,root,event):
    root.mkdir(parents=True,exist_ok=True);seal=root/'worker_complete.json';record=completed(seal)
    if record:event('pycrown_cache',scenario=scenario.scenario_id);return root/'labels.npz',record['worker']
    source=root/'input.npz';np.savez_compressed(source,chm=arrays['chm'],valid=arrays['observation']==1)
    job={**asdict(scenario),'input':str(source),'output':str(root/'labels.npz'),
        'upstream_root':str((config.paths.project_root/design.upstream_root).resolve()),'th_seed':design.th_seed,'th_crown':design.th_crown}
    atomic_write_json(root/'job.json',job)
    command=[str(config.paths.project_root/design.worker_python),str(config.paths.project_root/design.worker_script),str(root/'job.json')]
    event('pycrown_start',scenario=scenario.scenario_id,cells=layout.width*layout.height)
    process=subprocess.run(command,capture_output=True,text=True,timeout=1800)
    (root/'worker_stdout.txt').write_text(process.stdout);(root/'worker_stderr.txt').write_text(process.stderr)
    if process.returncode:raise RuntimeError(f'PyCrown falhou: {process.stderr[-4000:]}')
    report=json.loads(process.stdout.strip().splitlines()[-1]);event('pycrown_complete',scenario=scenario.scenario_id,**report)
    atomic_write_json(seal,{'worker':report,'outputs':[fingerprint(root/'labels.npz'),fingerprint(root/'job.json')]})
    return root/'labels.npz',report


def crown_vectors(config,layout,domain,labels,seeds,original,corrections,valid,scenario):
    pieces={}
    for geom,label in shapes(labels,mask=labels>0,transform=layout.transform,connectivity=4):pieces.setdefault(int(label),[]).append(shape(geom))
    near_invalid=ndimage.maximum_filter((~valid).astype('uint8'),size=3,mode='constant',cval=1)
    flags=ndimage.maximum(near_invalid,labels,index=np.arange(1,seeds.shape[1]+1)) if seeds.shape[1] else []
    rows=[];tops=[]
    for label,parts in sorted(pieces.items()):
        geom=polygonal(shapely.union_all(parts).intersection(domain.context));col,row=seeds[:,label-1]
        x,y=layout.transform*(float(col)+.5,float(row)+.5);ox,oy=layout.transform*tuple(original[label-1])
        identity=f'{domain.corridor_id}_{scenario.scenario_id}_C{label:06d}'
        item={'crown_id':identity,'label':label,'corridor_id':domain.corridor_id,'scenario_id':scenario.scenario_id,
            'area_context_m2':geom.area,'area_measurement_m2':geom.intersection(domain.measurement).area,
            'touches_invalid_support':bool(flags[label-1]),'touches_context_limit':geom.distance(domain.context.boundary)<1e-7,
            'crosses_measurement_boundary':geom.intersects(domain.measurement.boundary),'classification_validated':False,
            'tree_identity_validated':False,'plateau_seed_relocated':label-1 in corrections}
        rows.append({**item,'geometry':geom});tops.append({**item,'x_chm_seed':x,'y_chm_seed':y,
            'original_plateau_centroid_x':ox,'original_plateau_centroid_y':oy,'seed_in_measurement':domain.measurement.covers(Point(x,y)),
            'geometry':Point(x,y)})
    columns=['crown_id','label','corridor_id','scenario_id','area_context_m2','area_measurement_m2',
        'touches_invalid_support','touches_context_limit','crosses_measurement_boundary','classification_validated','tree_identity_validated','plateau_seed_relocated']
    return frame(rows,config.grid.epsg,columns),frame(tops,config.grid.epsg,columns+['seed_in_measurement'])


def source_apices(config,layout,height_path,labels,tops,threshold,valid):
    best={};counts={}
    for batch in pq.ParquetFile(height_path).iter_batches(batch_size=65536):
        f=batch.to_pandas();cell,inside=point_cells(layout,f.x.to_numpy(),f.y.to_numpy());lab=labels.ravel()[cell]
        use=inside&(lab>0)&valid.ravel()[cell]&f.classification.isin(config.vegetation.classes).to_numpy()&(
            (f.qc_flags.to_numpy()&2)==0)&f.terrain_status.eq(0).to_numpy()&(f.h.to_numpy()>threshold)
        f=f.loc[use].copy();f['label']=lab[use]
        for label,part in f.groupby('label',sort=False):
            counts[int(label)]=counts.get(int(label),0)+len(part)
            row=part.sort_values(['z_absolute','source_tile','source_point_index'],ascending=[False,True,True]).iloc[0]
            old=best.get(int(label))
            if old is None or (-row.z_absolute,row.source_tile,int(row.source_point_index))<(-old['z_absolute'],old['source_tile'],old['source_point_index']):
                best[int(label)]={key:row[key].item() if isinstance(row[key],np.generic) else row[key] for key in ['x','y','z_absolute','h','source_tile','source_point_index']}
    result=tops.copy()
    for key in ['x','y','z_absolute','h','source_tile','source_point_index']:
        result[f'apex_return_{key}']=[best.get(int(label),{}).get(key) for label in result.label]
    result['candidate_returns_in_segment']=[counts.get(int(label),0) for label in result.label]
    result['apex_estimand']='maximum_absolute_Z_candidate_return_inside_estimated_segment'
    return result


def scenario_support(config,layout,domain,arrays,labels,scenario):
    valid=arrays['observation']==1;mask=np.where(valid,(labels>0).astype('uint8'),255).astype('uint8')
    support=RasterSupport(arrays['observation'],mask,arrays['uncertainty'],arrays['terrain_valid'].astype(bool),layout.transform,config.grid.epsg)
    observed=polygonal(observed_geometry(layout,valid,domain))
    patches,_,_,summary=patch_layers(config,layout,domain,mask,f'pycrown_{domain.corridor_id}_{scenario.scenario_id}',scenario.height_m,valid)
    return support,observed,patches,summary
