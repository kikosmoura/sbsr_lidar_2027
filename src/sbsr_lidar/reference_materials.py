"""Recortes reais de pontos, RGB derivado dos pontos e perfis para inspeção."""
from contextlib import ExitStack
from pathlib import Path

import laspy
import numpy as np
import pyarrow.parquet as pq
import rasterio
import shapely
from rasterio.transform import from_origin

from .terrain_inputs import selected_indices,check_header


def window_mask(x,y,bounds):
    left,bottom,right,top=bounds
    return (x>=left)&(x<right)&(y>=bottom)&(y<top)


def clip_heights(config,frame,source,directory):
    outputs=[];counts={r.window_id:0 for r in frame.itertuples()}
    schema=pq.ParquetFile(source).schema_arrow
    with ExitStack() as stack:
        writers={}
        for row in frame.itertuples():
            target=directory/'janelas'/row.window_id/'pontos_altura.parquet'
            target.parent.mkdir(parents=True,exist_ok=True)
            writers[row.window_id]=stack.enter_context(pq.ParquetWriter(target,schema,compression='zstd'))
            outputs.append(target)
        for batch in pq.ParquetFile(source).iter_batches(batch_size=65536):
            x=batch.column(batch.schema.get_field_index('x')).to_numpy()
            y=batch.column(batch.schema.get_field_index('y')).to_numpy()
            for row in frame.itertuples():
                keep=window_mask(x,y,row.geometry.bounds)
                if not keep.any():continue
                selected=batch.filter(keep)
                counts[row.window_id]+=len(selected)
                if counts[row.window_id]>config.reference.max_points_per_window:raise ValueError('Janela excede limite de pontos; não subamostrar silenciosamente')
                writers[row.window_id].write_batch(selected)
    return outputs,counts


def clip_lidar_rgb(config,domain,frame,input_rows,directory,event):
    size=config.reference.window_size_m;res=config.reference.rgb_resolution_m
    n=int(np.ceil(size/res))
    arrays={r.window_id:(np.full((n,n),-np.inf),np.zeros((4,n,n),dtype=np.uint8)) for r in frame.itertuples()}
    counts={r.window_id:0 for r in frame.itertuples()}
    outputs=[];source_index=[]
    mds_rows=[r for r in input_rows if r['produto']=='MDS']
    with ExitStack() as stack:
        writers={}
        for row in frame.itertuples():
            with laspy.open(Path(mds_rows[0]['selected_laz']),read_evlrs=False) as source:
                header=source.header.copy()
            header.add_extra_dim(laspy.ExtraBytesParams(name='source_point_index',type=np.uint64))
            header.add_extra_dim(laspy.ExtraBytesParams(name='source_tile_index',type=np.uint16))
            path=directory/'janelas'/row.window_id/'mds_rgb_original.laz'
            writers[row.window_id]=stack.enter_context(laspy.open(path,mode='w',header=header))
            outputs.append(path)
        for source_number,item in enumerate(mds_rows):
            path=Path(item['selected_laz']);source_offset=0
            source_index.append({'source_tile_index':source_number,'tile':item['quadricula'],'path':str(path)})
            event('clip_raw_mds',tile=item['quadricula'],windows=len(frame))
            with laspy.open(path,read_evlrs=False) as reader:
                check_header(reader.header,config)
                for points in reader.chunk_iterator(config.resources.chunk_points):
                    xyz=np.column_stack([points.x,points.y,points.z])
                    owned=selected_indices(xyz,domain,item['quadricula'])
                    for row in frame.itertuples():
                        use=owned[window_mask(xyz[owned,0],xyz[owned,1],row.geometry.bounds)]
                        if not len(use):continue
                        writer=writers[row.window_id]
                        output=laspy.ScaleAwarePointRecord.zeros(len(use),header=writer.header)
                        # Copiar dimensões originais, escalando XYZ pelo cabeçalho de saída.
                        for name in points.point_format.dimension_names:
                            if name not in {'X','Y','Z'}:output[name]=np.asarray(points[name])[use]
                        output.x=xyz[use,0];output.y=xyz[use,1];output.z=xyz[use,2]
                        output.source_point_index=source_offset+use
                        output.source_tile_index=np.full(len(use),source_number,dtype=np.uint16)
                        writer.write_points(output)
                        counts[row.window_id]+=len(use)
                        if counts[row.window_id]>config.reference.max_points_per_window:raise ValueError('LAZ de janela excede limite de pontos')
                        left,bottom,right,top=row.geometry.bounds
                        cols=np.floor((xyz[use,0]-left)/res).astype(int)
                        rows=n-1-np.floor((xyz[use,1]-bottom)/res).astype(int)
                        inside=(cols>=0)&(cols<n)&(rows>=0)&(rows<n)
                        indices=use[inside];cols=cols[inside];rows=rows[inside]
                        flat=rows*n+cols
                        order=np.lexsort((-xyz[indices,2],flat))
                        _,first=np.unique(flat[order],return_index=True)
                        selected=order[first]
                        indices=indices[selected];cols=cols[selected];rows=rows[selected]
                        z,image=arrays[row.window_id]
                        higher=xyz[indices,2]>z[rows,cols]
                        indices=indices[higher];cols=cols[higher];rows=rows[higher]
                        z[rows,cols]=xyz[indices,2]
                        for band,name in enumerate(['red','green','blue']):
                            image[band,rows,cols]=np.rint(np.asarray(points[name])[indices]/257).astype(np.uint8)
                        image[3,rows,cols]=255
                    source_offset+=len(points)
    for row in frame.itertuples():
        left,bottom,right,top=row.geometry.bounds
        z,image=arrays[row.window_id]
        path=directory/'janelas'/row.window_id/'rgb_pontos_lidar.tif'
        with rasterio.open(path,'w',driver='GTiff',width=n,height=n,count=4,dtype='uint8',crs=f'EPSG:{config.grid.epsg}',
                           transform=from_origin(left,top,res,res),compress='deflate') as ds:
            ds.write(image)
            ds.colorinterp=(rasterio.enums.ColorInterp.red,rasterio.enums.ColorInterp.green,
                            rasterio.enums.ColorInterp.blue,rasterio.enums.ColorInterp.alpha)
            ds.update_tags(stage='05',source='RGB_of_topmost_MDS_point_per_cell_not_orthophoto',
                           calibrated_reflectance='not_verified',color_scale='uint16_divided_by_257',
                           empty_cell='transparent_not_shadow_or_ground_truth')
        outputs.append(path)
    return outputs,counts,source_index


def render_window_profiles(config,frame,directory):
    import os
    os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr_mpl_etapa05')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    outputs=[]
    for row in frame.itertuples():
        folder=directory/'janelas'/row.window_id
        table=pq.read_table(folder/'pontos_altura.parquet',columns=['x','y','z_absolute','h']).to_pandas()
        xmid,ymid=row.geometry.centroid.coords[0]
        profiles=[]
        for direction,coordinate,keep in [('E_W','x',np.abs(table.y-ymid)<=config.reference.profile_half_width_m),
                                           ('N_S','y',np.abs(table.x-xmid)<=config.reference.profile_half_width_m)]:
            part=table.loc[keep].copy()
            part['profile']=direction;profiles.append(part)
        import pandas as pd
        combined=pd.concat(profiles,ignore_index=True)
        csv=folder/'perfis_pontos.csv';combined.to_csv(csv,index=False);outputs.append(csv)
        # Visão cega: RGB e Z bruto. H e classes ficam fora desta figura inicial.
        fig,axes=plt.subplots(1,3,figsize=(12,3.7),layout='constrained')
        with rasterio.open(folder/'rgb_pontos_lidar.tif') as rgb:
            image=rgb.read().transpose(1,2,0)
            axes[0].imshow(image,extent=[*row.geometry.bounds[::2],*row.geometry.bounds[1::2]],interpolation='nearest')
        axes[0].set_title('RGB dos pontos — não é ortofoto',fontsize=9)
        for ax,part,direction,coordinate in zip(axes[1:],profiles,['E_W','N_S'],['x','y']):
            ax.scatter(part[coordinate],part.z_absolute,s=1,color='#43586c',alpha=.5,rasterized=True)
            ax.set_title('Perfil '+direction+' — Z absoluto',fontsize=9)
            ax.set_ylabel('Elevação (m)')
            ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(labelsize=7,axis='x',rotation=30)
        fig.suptitle(row.window_id+' · rótulos pendentes · sem ranking',fontsize=11)
        png=folder/'ficha_cega.png';fig.savefig(png,dpi=140);plt.close(fig);outputs.append(png)
    return outputs
