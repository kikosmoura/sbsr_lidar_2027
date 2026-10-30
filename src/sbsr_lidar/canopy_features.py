"""Contagens integrais e atributos auxiliares; nenhum atributo é rótulo humano."""
from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.spatial import cKDTree

from .terrain_inputs import check_header


def point_cells(layout,x,y):
    cols=np.floor((x-layout.transform.c)/layout.resolution).astype(np.int64)
    rows=np.floor((layout.transform.f-y)/layout.resolution).astype(np.int64)
    inside=(cols>=0)&(cols<layout.width)&(rows>=0)&(rows<layout.height)
    flat=np.maximum(0,np.minimum(rows*layout.width+cols,layout.width*layout.height-1))
    inside &= layout.context_mask.ravel()[flat]
    return flat,inside


def _add(target,cells,select):
    target.ravel()[:]+=np.bincount(cells[select],minlength=target.size).astype(target.dtype)


def accumulate_points(config,layout,source,heights):
    names=['all','usable','valid_h','above_geometry','multiple','first','structure','water_class','bridge_class','candidate_missing_h']
    counts={name:np.zeros(layout.shape,dtype=np.uint32) for name in names}
    candidates={h:np.zeros(layout.shape,dtype=np.uint32) for h in heights}
    class1={h:np.zeros(layout.shape,dtype=np.uint32) for h in heights}
    geometry=[];geometry_n=0;lookup={};class_stats={}
    geometry_height=min(heights)
    outside=0
    for batch in pq.ParquetFile(source).iter_batches(batch_size=65536):
        b=batch.to_pandas()
        cell,inside=point_cells(layout,b.x.to_numpy(),b.y.to_numpy())
        outside+=int((~inside).sum())
        h=b.h.to_numpy();cls=b.classification.to_numpy()
        usable=(b.qc_flags.to_numpy() & 2)==0
        valid=np.isfinite(h)&usable&(b.terrain_status.to_numpy()==0)
        above=valid & (h>=geometry_height)
        veg=np.isin(cls,config.vegetation.classes)
        masks={'all':inside,'usable':inside&usable,'valid_h':inside&valid,'above_geometry':inside&above,
            'multiple':inside&above&(b.number_of_returns.to_numpy()>1),
            'first':inside&above&(b.return_number.to_numpy()==1),
            'structure':inside&above&(cls==6),'water_class':inside&(cls==9),'bridge_class':inside&(cls==17),
            'candidate_missing_h':inside&usable&veg&~valid}
        for name,mask in masks.items():_add(counts[name],cell,mask)
        for threshold in heights:
            _add(candidates[threshold],cell,inside&valid&veg&(h>=threshold))
            _add(class1[threshold],cell,inside&valid&(cls==1)&(h>=threshold))
        use=inside&above
        geometry_n+=int(use.sum())
        if geometry_n>config.vegetation.max_geometry_points or geometry_n*256>config.resources.max_ram_gib*2**30:
            raise ValueError('Nuvem de vizinhança excede orçamento; reduzir janela antes de calcular geometria')
        if use.any():geometry.append(b.loc[use,['x','y','z_absolute']].to_numpy())
        for tile,part in b.loc[inside].groupby('source_tile',sort=False):
            indices=part.index.to_numpy()
            lookup.setdefault(tile,[]).append({'index':part.source_point_index.to_numpy(),
                'cell':cell[indices],'h':part.h.to_numpy(),'classification':part.classification.to_numpy(),
                'eligible':valid[indices]})
        for code in np.unique(cls):
            use=cls==code;good=use&valid;values=h[good]
            item=class_stats.setdefault(int(code),{'class':int(code),'points_context':0,'points_measurement':0,
                'valid_h_points':0,'min_h_m':None,'max_h_m':None,**{f'points_h_ge_{t:g}m':0 for t in heights}})
            item['points_context']+=int(use.sum());item['points_measurement']+=int(np.sum(use&b.in_measurement.to_numpy()))
            item['valid_h_points']+=len(values)
            if len(values):
                item['min_h_m']=float(values.min()) if item['min_h_m'] is None else min(item['min_h_m'],float(values.min()))
                item['max_h_m']=float(values.max()) if item['max_h_m'] is None else max(item['max_h_m'],float(values.max()))
            for t in heights:item[f'points_h_ge_{t:g}m']+=int(np.sum(values>=t))
    merged={}
    for tile,parts in lookup.items():
        merged[tile]={key:np.concatenate([p[key] for p in parts]) for key in parts[0]}
        if np.any(np.diff(merged[tile]['index'])<=0):raise ValueError('Índices MDS duplicados ou fora da ordem no produto de H')
    xyz=np.concatenate(geometry) if geometry else np.empty((0,3))
    return counts,candidates,class1,xyz,merged,{'classes':list(class_stats.values()),
        'geometry_input_records':geometry_n,'points_outside_center_context_grid':outside,
        'count_unit':'records_not_independent_pulses; no_MDS_within_file_deduplication'}


def local_geometry(config,layout,xyz,query_mask,event):
    names=['planarity','linearity','roughness_m','xy_spread_m','neighbor_count']
    result={name:np.full(layout.shape,np.nan,dtype=np.float32) for name in names}
    if not len(xyz):return result,{'input_points':0,'voxel_points':0,'reliable_cells':0}
    keys=np.floor(xyz/config.vegetation.geometry_voxel_m).astype(np.int64)
    _,first=np.unique(keys,axis=0,return_index=True)
    xyz=xyz[np.sort(first)]
    tree=cKDTree(xyz[:,:2]);rows,cols=np.nonzero(query_mask)
    reliable_n=0
    for start in range(0,len(rows),config.vegetation.geometry_query_cells):
        rr=rows[start:start+config.vegetation.geometry_query_cells];cc=cols[start:start+config.vegetation.geometry_query_cells]
        xy=np.column_stack([layout.transform.c+(cc+.5)*layout.resolution,layout.transform.f-(rr+.5)*layout.resolution])
        distances,indices=tree.query(xy,k=config.vegetation.geometry_neighbors,
            distance_upper_bound=config.vegetation.geometry_radius_m,workers=1)
        valid=np.isfinite(distances)&(indices<len(xyz));n=valid.sum(axis=1)
        safe=np.minimum(indices,len(xyz)-1)
        neighborhood=xyz[safe].copy()
        neighborhood[:,:,:2]-=xy[:,None,:]
        neighborhood[:,:,2]-=xyz[safe[:,0],2,None]
        mean=(neighborhood*valid[:,:,None]).sum(axis=1)/np.maximum(n,1)[:,None]
        centered=(neighborhood-mean[:,None,:])*valid[:,:,None]
        covariance=np.einsum('nki,nkj->nij',centered,centered)/np.maximum(n-1,1)[:,None,None]
        eigenvalues=np.maximum(np.linalg.eigvalsh(covariance),0)
        xy_eigen=np.maximum(np.linalg.eigvalsh(covariance[:,:2,:2]),0)
        reliable=(n>=config.vegetation.geometry_min_neighbors)&(eigenvalues[:,2]>1e-10)
        a,b,c=eigenvalues.T
        denominator=np.maximum(c,1e-10)
        features={'planarity':(b-a)/denominator,'linearity':(c-b)/denominator,
                  'roughness_m':np.sqrt(a),'xy_spread_m':np.sqrt(xy_eigen[:,1]),'neighbor_count':n}
        for name,values in features.items():
            values=np.asarray(values,dtype=np.float32)
            if name!='neighbor_count':values[~reliable]=np.nan
            result[name][rr,cc]=values
        reliable_n+=int(reliable.sum())
    event('local_geometry',voxel_points=len(xyz),query_cells=len(rows),reliable_cells=reliable_n)
    return result,{'input_points_before_voxel':len(keys),'voxel_points':len(xyz),
        'voxel_size_m':config.vegetation.geometry_voxel_m,'reliable_cells':reliable_n,
        'neighbor_radius_xy_m':config.vegetation.geometry_radius_m,'maximum_neighbors':config.vegetation.geometry_neighbors,
        'minimum_neighbors':config.vegetation.geometry_min_neighbors,'point_selection':'valid_H_at_least_lowest_tested_height',
        'features_are_diagnostic_not_calibrated_class_labels':True}


def spectral_features(config,layout,lookup,raw_paths,event):
    sums={key:np.zeros(layout.shape,dtype=np.float64) for key in ['nir_red','excess_green','brightness']}
    n={key:np.zeros(layout.shape,dtype=np.uint32) for key in sums}
    records=0;by_class={}
    for tile,path in raw_paths.items():
        if tile not in lookup:continue
        data=lookup[tile];offset=0
        event('read_spectral_auxiliary',tile=tile)
        with laspy.open(path,read_evlrs=False) as reader:
            check_header(reader.header,config)
            for points in reader.chunk_iterator(config.resources.chunk_points):
                lo=np.searchsorted(data['index'],offset);hi=np.searchsorted(data['index'],offset+len(points))
                if lo==hi:offset+=len(points);continue
                index=data['index'][lo:hi]-offset
                if not np.array_equal(np.asarray(points.classification)[index],data['classification'][lo:hi]):
                    raise ValueError('Classe do LAZ diverge do Parquet de H')
                h=data['h'][lo:hi];eligible=data['eligible'][lo:hi]&(h>=min(config.sensitivity.heights_m+[config.vegetation.minimum_height_m]))
                cell=data['cell'][lo:hi]
                r=np.asarray(points.red)[index].astype(float);g=np.asarray(points.green)[index].astype(float)
                b=np.asarray(points.blue)[index].astype(float);nir=np.asarray(points.nir)[index].astype(float)
                fields={'nir_red':np.divide(nir-r,nir+r,out=np.full(len(r),np.nan),where=nir+r>0),
                        'excess_green':np.divide(2*g-r-b,r+g+b,out=np.full(len(r),np.nan),where=r+g+b>0),
                        'brightness':(r+g+b)/(3*65535)}
                for name,values in fields.items():
                    use=eligible&np.isfinite(values)
                    sums[name].ravel()[:]+=np.bincount(cell[use],weights=values[use],minlength=sums[name].size)
                    n[name].ravel()[:]+=np.bincount(cell[use],minlength=n[name].size).astype(np.uint32)
                for code in np.unique(data['classification'][lo:hi]):
                    use=eligible&(data['classification'][lo:hi]==code)&np.isfinite(fields['nir_red'])
                    item=by_class.setdefault(int(code),{'class':int(code),'n':0,'sum_nir_red':0.})
                    item['n']+=int(use.sum());item['sum_nir_red']+=float(fields['nir_red'][use].sum())
                records+=len(index);offset+=len(points)
        if len(data['index']) and offset<=int(data['index'][-1]):raise ValueError('Índices de H excedem registros do LAZ')
    result={name:np.divide(values,n[name],out=np.full(layout.shape,np.nan),where=n[name]>0).astype(np.float32) for name,values in sums.items()}
    return result,{'records_matched_to_raw':records,'by_class':[{'class':k,'n':v['n'],
        'mean_nir_red_aux':v['sum_nir_red']/v['n'] if v['n'] else None} for k,v in sorted(by_class.items())],
        'index_name':'(NIR-red)/(NIR+red)_uncalibrated_auxiliary_not_validated_NDVI',
        'used_as_classification_threshold':False,'zero_denominator_is_nodata':True,
        'colorization_photographic_epoch':'not_verified'}
