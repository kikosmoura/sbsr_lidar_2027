"""Primeira passagem integral LAZ e normalização por janelas com propriedade única."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import zipfile

import laspy
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from .terrain_inputs import check_header,qc_mask
from .terrain_surface import Surface
from .storage import atomic_write_json,fingerprint,read_json,canonical_json


def digest(value):return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def completed(path):
    if not path.is_file():return None
    try:
        record=read_json(path)
        return record if record.get('outputs') and all(fingerprint(Path(p['path']))==p for p in record['outputs']) else None
    except FileNotFoundError:
        # Um checkpoint incompleto precisa ser recalculado, inclusive se um
        # derivado foi removido entre a leitura do selo e sua autenticação.
        return None


def write_frame(frame,path):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.part.parquet')
    frame.to_parquet(temporary,index=False,compression='zstd');temporary.replace(path)


def owned_indices(xyz,domain,code):
    tile=domain.nominal_tiles.loc[domain.nominal_tiles.quadricula.eq(code)].iloc[0].geometry
    x0,y0,x1,y1=tile.bounds
    keep=np.isfinite(xyz).all(axis=1)&(xyz[:,0]>=x0)&(xyz[:,0]<=x1)&(xyz[:,1]>=y0)&(xyz[:,1]<=y1)
    idx=np.flatnonzero(keep)
    if not len(idx):return idx
    x,y=xyz[idx,:2].T
    keep=shapely.intersects_xy(tile,x,y)&shapely.intersects_xy(domain.context,x,y)
    # Somente vizinhos que tocam a folha podem disputar seus pontos de borda.
    for other in domain.nominal_tiles.iloc[domain.nominal_tiles.sindex.query(tile,predicate='intersects')].itertuples():
        if other.quadricula<code:keep&=~shapely.intersects_xy(other.geometry,x,y)
    return idx[keep]


def extract_case(config,design,domain,rows,root,event):
    root.mkdir(parents=True,exist_ok=True);all_buckets=[];qc=[]
    for item in rows:
        code,product=item['quadricula'],item['produto'];folder=root/f'{product}_{code}'
        seal=folder/'complete.json';record=completed(seal)
        if record:
            all_buckets+=record['buckets'];qc.append(record['qc']);event('raw_source_cache',product=product,tile=code);continue
        folder.mkdir(parents=True,exist_ok=True)
        archive=item.get('archive');crc=False
        if archive:
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None:raise ValueError(f'CRC inválido: {archive}')
                crc=True
        count=owned=0;buckets=[];paths=[];classes=Counter()
        event('decode_laz',corridor=domain.corridor_id,product=product,tile=code)
        with laspy.open(item['selected_laz'],read_evlrs=False) as reader:
            header=check_header(reader.header,config)
            for chunk_no,points in enumerate(reader.chunk_iterator(config.resources.chunk_points)):
                xyz=np.column_stack([points.x,points.y,points.z]);idx=owned_indices(xyz,domain,code)
                source_index=count+idx;count+=len(points)
                classes.update({int(k):int(v) for k,v in zip(*np.unique(np.asarray(points.classification),return_counts=True))})
                if not len(idx):continue
                owned+=len(idx);xy=xyz[idx,:2]
                frame=pd.DataFrame({'source_tile':code,'source_point_index':source_index,'x':xy[:,0],'y':xy[:,1],
                    'z_absolute':xyz[idx,2],'classification':np.asarray(points.classification)[idx],
                    'user_data':np.asarray(points.user_data)[idx], 'return_number':np.asarray(points.return_number)[idx],
                    'number_of_returns':np.asarray(points.number_of_returns)[idx],
                    'qc_flags':np.where(qc_mask(points,config)[idx],0,2).astype('uint16')})
                wx=np.floor(xy[:,0]/design.window_size_m).astype(int);wy=np.floor(xy[:,1]/design.window_size_m).astype(int)
                for key in sorted(set(zip(wx,wy))):
                    use=(wx==key[0])&(wy==key[1]);path=folder/f'part_{chunk_no:05d}_{key[0]}_{key[1]}.parquet'
                    write_frame(frame.loc[use],path);paths.append(path)
                    buckets.append({'product':product,'wx':int(key[0]),'wy':int(key[1]),'path':str(path),'rows':int(use.sum())})
        if count!=header['declared_points']:raise ValueError(f'Quantidade decodificada difere do cabeçalho: {code}/{product}')
        report={'product':product,'tile':code,'declared_points':header['declared_points'],'decoded_points':count,
            'owned_context_records':owned,'classes_whole_file':dict(classes),'archive_crc_checked':crc,
            'header':header,'integrity':'all_declared_records_decoded; CRC_checked_if_archive_available',
            'originals_modified':False}
        record={'qc':report,'buckets':buckets,'outputs':[fingerprint(p) for p in paths]}
        # Uma fonte sem pontos no ROI também é checkpoint legítimo.
        if not paths:
            marker=folder/'empty.json';atomic_write_json(marker,{'owned_context_records':0});record['outputs']=[fingerprint(marker)]
        atomic_write_json(seal,record);all_buckets+=buckets;qc.append(report)
    atomic_write_json(root/'index.json',{'buckets':all_buckets,'sources':qc})
    return all_buckets,qc


def deduplicate_ground(xyz,config):
    keys=np.rint(xyz/config.terrain.coordinate_key_m).astype(np.int64)
    _,first=np.unique(keys,axis=0,return_index=True);xyz=xyz[first];keys=keys[first]
    _,starts,counts=np.unique(keys[:,:2],axis=0,return_index=True,return_counts=True)
    lo=np.minimum.reduceat(xyz[:,2],starts);hi=np.maximum.reduceat(xyz[:,2],starts)
    result=xyz[starts].copy()
    for start,count,i in zip(starts[counts>1],counts[counts>1],np.flatnonzero(counts>1)):
        result[i,2]=np.median(xyz[start:start+count,2])
    return result[(hi-lo)<=config.terrain.maximum_xy_z_spread_m]


def query(surface,xy,config):
    z=np.full(len(xy),np.nan);status=np.full(len(xy),7,dtype=np.uint8)
    if surface is None:return z,status
    for start in range(0,len(xy),config.terrain.query_points):
        end=start+config.terrain.query_points;values=surface.query(xy[start:end],config.terrain.maximum_distance_m)
        z[start:end]=values['tin'];status[start:end]=values['tin_status']
    return z,status


def normalize_case(config,design,domain,buckets,root,event):
    root.mkdir(parents=True,exist_ok=True)
    coordinates=sorted({(r['wx'],r['wy']) for r in buckets})
    outputs=[];reports=[]
    for wx,wy in coordinates:
        folder=root/f'W{wx}_{wy}';seal=folder/'complete.json';record=completed(seal)
        if record:outputs+=record['outputs'];reports.append(record['qc']);event('window_cache',window=f'{wx}_{wy}');continue
        folder.mkdir(parents=True,exist_ok=True);size=design.window_size_m;pad=design.terrain_context_m
        core=shapely.box(wx*size,wy*size,(wx+1)*size,(wy+1)*size)
        region=core.buffer(pad,join_style='mitre').intersection(domain.context)
        if region.is_empty:continue
        ground=[];mds=[]
        for row in buckets:
            if row['product']=='MDS' and (row['wx'],row['wy'])==(wx,wy):mds.append(row['path'])
            if row['product']!='MDT' or abs(row['wx']-wx)>1 or abs(row['wy']-wy)>1:continue
            f=pd.read_parquet(row['path']);xy=f[['x','y']].to_numpy()
            keep=((f.qc_flags.to_numpy()&2)==0)&shapely.intersects_xy(region,xy[:,0],xy[:,1])
            if keep.any():ground.append(f.loc[keep,['x','y','z_absolute']].to_numpy())
        n_ground=sum(len(p) for p in ground)
        if n_ground>design.maximum_ground_vertices_per_window:raise ValueError('Janela MDT excede orçamento')
        xyz=deduplicate_ground(np.concatenate(ground),config) if n_ground else np.empty((0,3))
        model=None;reason=None
        if len(xyz)>=3:
            try:model=Surface(xyz,config.terrain)
            except ValueError:reason='degenerate_ground_geometry'
        else:reason='insufficient_ground_vertices'
        paths=[];n_points=0;valid_points=0
        h_parts=[]
        for n,path in enumerate(sorted(mds)):
            f=pd.read_parquet(path);n_points+=len(f)
            if n_points>design.maximum_roi_records_per_window:raise ValueError('Janela MDS excede orçamento')
            xy=f[['x','y']].to_numpy();z,status=query(model,xy,config)
            excluded=(f.qc_flags.to_numpy()&2)!=0;z[excluded]=np.nan;status[excluded]=6
            h=f.z_absolute.to_numpy()-z;flags=f.qc_flags.to_numpy().astype('uint16')
            flags[(status!=0)&~excluded]|=1;flags[np.isfinite(h)&(h<0)]|=4
            flags[np.isfinite(h)&(h<config.terrain.negative_warning_m)]|=8
            flags[np.isfinite(h)&(h>config.terrain.extreme_height_m)]|=16
            f['terrain_z']=z;f['h']=h;f['terrain_status']=status;f['qc_flags']=flags
            f['in_measurement']=shapely.intersects_xy(domain.measurement,xy[:,0],xy[:,1])
            dest=folder/f'H_{n:04d}.parquet';write_frame(f,dest);paths.append(dest);h_parts.append(str(dest));valid_points+=int((status==0).sum())
        centers={}
        for res in design.resolutions_m:
            xmin,ymin,xmax,ymax=region.bounds
            ix0=max(int(wx*size/res),int(np.floor(xmin/res)));ix1=min(int((wx+1)*size/res),int(np.ceil(xmax/res)))
            iy0=max(int(wy*size/res),int(np.floor(ymin/res)));iy1=min(int((wy+1)*size/res),int(np.ceil(ymax/res)))
            xx,yy=np.meshgrid((np.arange(ix0,ix1)+.5)*res,(np.arange(iy0,iy1)+.5)*res)
            xy=np.column_stack([xx.ravel(),yy.ravel()]);use=shapely.intersects_xy(domain.context,xy[:,0],xy[:,1]);xy=xy[use]
            z,status=query(model,xy,config)
            dest=folder/f'centers_{res:g}.parquet'
            write_frame(pd.DataFrame({'x':xy[:,0],'y':xy[:,1],'z':z,'status':status}),dest);paths.append(dest);centers[f'{res:g}']=str(dest)
        qc={'wx':wx,'wy':wy,'mds_records':n_points,'valid_H_records':valid_points,'unique_ground_vertices':len(xyz),
            'ground_missing_reason':reason,'height_parts':h_parts,'centers':centers,
            'tile_count':int(domain.nominal_tiles.intersects(region).sum()),'point_ownership':'floor_XY/200m; one owner; exact nominal tile ownership',
            'terrain_context_m':pad,'geoid_correction_applied':False}
        if qc['tile_count']>config.resources.max_pilot_tiles:raise ValueError('Janela excede orçamento de folhas')
        record={'qc':qc,'outputs':[fingerprint(p) for p in paths]};atomic_write_json(seal,record)
        outputs+=record['outputs'];reports.append(qc)
        event('normalized_window',corridor=domain.corridor_id,window=f'{wx}_{wy}',records=n_points,vertices=len(xyz))
    # Uma única tabela de alturas, gravada por blocos, alimenta as métricas sem carregar o corredor em RAM.
    target=root/'alturas_pontos.parquet';merge_seal=root/'merge_complete.json'
    merge=completed(merge_seal)
    if not merge:
        temp=target.with_suffix('.part.parquet');writer=None;rows=0
        try:
            for report in reports:
                for path in report['height_parts']:
                    for batch in pq.ParquetFile(path).iter_batches(batch_size=65536):
                        table=pa.Table.from_batches([batch])
                        if writer is None:writer=pq.ParquetWriter(temp,table.schema,compression='zstd')
                        writer.write_table(table);rows+=len(table)
            if writer is None:raise ValueError('Corredor sem MDS no contexto')
        finally:
            if writer is not None:writer.close()
        temp.replace(target);atomic_write_json(merge_seal,{'rows':rows,'outputs':[fingerprint(target)]})
    atomic_write_json(root/'normalization.json',{'windows':reports,'records':sum(r['mds_records'] for r in reports),
        'unique_ground_vertices_summed_across_overlapping_contexts_not_unique_case':sum(r['unique_ground_vertices'] for r in reports),
        'formula':'H=Z_absolute-TIN5(X,Y); MDT contexts overlap; MDS owned cores never overlap',
        'cross_window_crown_policy':'whole_corridor_CHM_mosaic_before_PyCrown; windows_never_split_crown_IDs'})
    return target,reports
