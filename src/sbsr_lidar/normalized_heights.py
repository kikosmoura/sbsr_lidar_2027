"""H flutuante por ponto, preservando elevação/classificação e NoData explícito."""
import os
from collections import Counter
from pathlib import Path

import laspy
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from .input_qc import _count_update
from .terrain_inputs import check_header, selected_indices, qc_mask
from .terrain_surface import normalize_z, error_metrics

HEIGHT_FLAGS={1:'no_terrain',2:'input_excluded_by_qc',4:'negative_h',8:'h_below_negative_warning',
              16:'h_above_extreme_warning',32:'measurement_edge',64:'LAS_water_class_9',128:'LAS_bridge_class_17'}


class ClassSample:
    """Amostra uniforme por prioridade aleatória; contagens são integrais."""
    def __init__(self,limit,seed):
        self.limit=limit
        self.rng=np.random.default_rng(seed)
        self.n=0
        self.values=np.empty((0,5)) # x,y,z,H,user_data
        self.priorities=np.empty(0)
        self.negative=self.severe_negative=self.extreme=0

    def add(self,values,negative_warning,extreme_warning):
        self.n+=len(values)
        self.negative+=int(np.sum(values[:,3]<0))
        self.severe_negative+=int(np.sum(values[:,3]<negative_warning))
        self.extreme+=int(np.sum(values[:,3]>extreme_warning))
        priorities=np.concatenate([self.priorities,self.rng.random(len(values))])
        pool=np.concatenate([self.values,values])
        keep=np.arange(len(pool)) if len(pool)<=self.limit else np.argpartition(priorities,self.limit-1)[:self.limit]
        self.values=pool[keep]
        self.priorities=priorities[keep]

    def summary(self):
        levels=[0,.05,.5,.95,1]
        return {'valid_points':self.n,'negative_h':self.negative,'below_negative_warning':self.severe_negative,
                'above_extreme_warning':self.extreme,'sample_n':len(self.values),'sample_scheme':'seeded_uniform_random_priority',
                'quantile_levels':levels,'h_quantiles_m':np.quantile(self.values[:,3],levels).tolist(),
                'h_minus_user_data_quantiles_m':np.quantile(self.values[:,3]-self.values[:,4],levels).tolist(),
                'h_minus_user_data_sample_error':error_metrics(self.values[:,3]-self.values[:,4])}


def stream_heights(config,domain,rows,model,method,layout,directory,event):
    fields=[('source_tile',pa.string()),('source_point_index',pa.int64()),
            *[(name,pa.float64()) for name in ['x','y','z_absolute','terrain_z','h']],
            *[(name,pa.uint8()) for name in ['classification','user_data','return_number','number_of_returns','terrain_status']],
            ('in_measurement',pa.bool_()),('qc_flags',pa.uint16())]
    schema=pa.schema(fields,metadata={b'stage':b'04',b'height_formula':b'H = original_absolute_Z - continuous_DTM(X,Y)',
        b'crs':f'EPSG:{config.grid.epsg}'.encode(),b'unit':b'metre',b'method':method.encode(),
        b'null_meaning':b'no_valid_height_not_zero',b'ownership':b'nominal_tile_lexicographic_shared_boundary'})
    path=directory/'alturas_pontos.parquet'
    temp=directory/'.alturas_pontos.parquet.part'
    samples={}
    headers=[]
    counts=Counter()
    flags_counts=Counter()
    all_cells=np.zeros(layout.shape,dtype=np.uint64)
    valid_cells=np.zeros_like(all_cells)
    negative_cells=np.zeros_like(all_cells)
    flagged=[]
    try:
        with pq.ParquetWriter(temp,schema,compression='zstd') as writer:
            for row in rows:
                if row['produto']!='MDS': continue
                event('normalize_mds',tile=row['quadricula'],method=method)
                with laspy.open(Path(row['selected_laz']),read_evlrs=False) as reader:
                    header=check_header(reader.header,config)
                    header.update(path=row['selected_laz'],tile=row['quadricula'],product='MDS')
                    headers.append(header)
                    source_offset=0
                    for points in reader.chunk_iterator(config.resources.chunk_points):
                        xyz=np.column_stack([points.x,points.y,points.z])
                        idx=selected_indices(xyz,domain,row['quadricula'])
                        source_indices=source_offset+idx
                        source_offset+=len(points)
                        if not len(idx): continue
                        xyz=xyz[idx]
                        cls=np.asarray(points.classification)[idx]
                        user=np.asarray(points.user_data)[idx]
                        rn=np.asarray(points.return_number)[idx]
                        nr=np.asarray(points.number_of_returns)[idx]
                        eligible=qc_mask(points,config)[idx]
                        in_measurement=shapely.intersects_xy(domain.measurement,xyz[:,0],xyz[:,1])
                        interior=domain.measurement.buffer(-config.input_preparation.edge_width_m)
                        edge=in_measurement & ~shapely.intersects_xy(interior,xyz[:,0],xyz[:,1])
                        for start in range(0,len(xyz),config.terrain.query_points):
                            stop=min(start+config.terrain.query_points,len(xyz))
                            sl=slice(start,stop)
                            q=model.query(xyz[sl,:2],config.terrain.maximum_distance_m)
                            dtm=q[method]
                            status=q[method+'_status'].copy()
                            status[~eligible[sl]]=6
                            dtm[~eligible[sl]]=np.nan
                            h=normalize_z(xyz[sl,2],dtm)
                            valid=np.isfinite(h)
                            measured=in_measurement[sl]
                            flags=np.zeros(len(h),dtype=np.uint16)
                            flags[q[method+'_status']!=0]|=1
                            flags[~eligible[sl]]|=2
                            flags[valid & (h<0)]|=4
                            flags[valid & (h<config.terrain.negative_warning_m)]|=8
                            flags[valid & (h>config.terrain.extreme_height_m)]|=16
                            flags[edge[sl]]|=32
                            flags[cls[sl]==9]|=64
                            flags[cls[sl]==17]|=128
                            for bit,label in HEIGHT_FLAGS.items(): flags_counts[label]+=int(np.sum((flags & bit)!=0))
                            counts['context_points']+=len(h)
                            counts['context_valid_h']+=int(valid.sum())
                            counts['measurement_points']+=int(measured.sum())
                            counts['measurement_valid_h']+=int(np.sum(valid & measured))
                            counts['measurement_without_terrain']+=int(np.sum(measured & (q[method+'_status']!=0)))
                            counts['measurement_input_excluded']+=int(np.sum(measured & ~eligible[sl]))
                            data={'source_tile':[row['quadricula']]*len(h),'source_point_index':source_indices[sl],
                                  'x':xyz[sl,0],'y':xyz[sl,1],'z_absolute':xyz[sl,2],
                                  'terrain_z':pa.array(dtm,mask=~valid),'h':pa.array(h,mask=~valid),
                                  'classification':cls[sl],'user_data':user[sl],'return_number':rn[sl],
                                  'number_of_returns':nr[sl],'terrain_status':status,'in_measurement':measured,'qc_flags':flags}
                            writer.write_table(pa.Table.from_pydict(data,schema=schema))
                            for code in np.unique(cls[sl][valid & measured]):
                                use=valid & measured & (cls[sl]==code)
                                sample=samples.setdefault(int(code),ClassSample(config.terrain.height_sample_per_class,
                                                                                 config.resources.seed+int(code)))
                                sample.add(np.column_stack([xyz[sl][use],h[use],user[sl][use]]),
                                           config.terrain.negative_warning_m,config.terrain.extreme_height_m)
                            _count_update(all_cells,layout,xyz[sl,0],xyz[sl,1])
                            _count_update(valid_cells,layout,xyz[sl][valid,0],xyz[sl][valid,1])
                            _count_update(negative_cells,layout,xyz[sl][valid & (h<config.terrain.negative_warning_m),0],
                                          xyz[sl][valid & (h<config.terrain.negative_warning_m),1])
                            if len(flagged)<1000:
                                for i in np.flatnonzero((flags & (8|16|64|128))!=0)[:1000-len(flagged)]:
                                    flagged.append({'source_tile':row['quadricula'],'source_point_index':int(source_indices[sl][i]),
                                        'x':float(xyz[sl][i,0]),'y':float(xyz[sl][i,1]),'z_absolute':float(xyz[sl][i,2]),
                                        'h':float(h[i]) if valid[i] else None,'classification':int(cls[sl][i]),'qc_flags':int(flags[i])})
                    if source_offset!=header['declared_points']: raise ValueError('MDS lido diverge do cabeçalho')
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)
    comparison={}
    if 8 in samples:
        values=samples[8].values
        distances,indices=model.tree.query(values[:,:2]-model.origin,k=1)
        deltas=values[:,2]-model.xyz[indices,2]
        exact_xy=distances<=1e-7
        comparison={'direction':'sample_MDS_class8_to_context_MDT_nearest_XY','sample_n':len(values),
            'exact_xy_n':int(exact_xy.sum()),'exact_xyz_within_2mm_n':int(np.sum(exact_xy & (np.abs(deltas)<=.002))),
            'z_difference_at_exact_xy':error_metrics(deltas[exact_xy]),
            'not_independent_absolute_accuracy':True}
    return {'headers':headers,'counts':dict(counts),'flags':dict(flags_counts),'flag_definitions':HEIGHT_FLAGS,
            'class_statistics_measurement':{str(k):v.summary() for k,v in sorted(samples.items())},
            'mds_mdt_xyz_consistency':comparison,'bridge_water_manual_validation':'not_performed_no_reference',
            'sampling_note':'Counts integral; height/user_data quantiles from bounded uniform samples per class in measurement',
            'within_file_duplicate_records_removed':False},path,(all_cells,valid_cells,negative_cells),flagged
