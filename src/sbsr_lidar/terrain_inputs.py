"""Referências/unidades e seleção MDT/MDS com propriedade espacial por folha."""
from pathlib import Path

import laspy
import numpy as np
import shapely


def check_header(header, config):
    crs=header.parse_crs()
    if crs is None or crs.to_epsg()!=config.grid.epsg:
        raise ValueError('CRS horizontal incompatível no par MDT/MDS')
    units={}
    vertical=[]
    for vlr in header.vlrs:
        if vlr.user_id=='LASF_Projection' and vlr.record_id==34735:
            units.update({int(k.id):int(k.value_offset) for k in vlr.geo_keys if k.tiff_tag_location==0})
        if vlr.user_id=='VertDatum-Geoid': vertical.append(vlr.description)
    if units.get(3076)!=9001 or units.get(4099)!=9001:
        raise ValueError('Cabeçalho deve declarar unidades XY e Z em metros (GeoKeys 3076/4099=9001)')
    if vertical != [config.terrain.expected_vertical_datum]:
        raise ValueError(f'Referência vertical não confirmada: {vertical}')
    if not np.isfinite(header.scales).all() or np.any(header.scales<=0) or not np.isfinite(header.offsets).all():
        raise ValueError('Escalas/offsets inválidos')
    return {'epsg':crs.to_epsg(),'xy_unit_epsg':units[3076],'z_unit_epsg':units[4099],
            'vertical_datum':vertical[0],'scales':header.scales.tolist(),'offsets':header.offsets.tolist(),
            'declared_points':int(header.point_count),'point_format':header.point_format.id,
            'z_bounds':[float(header.mins[2]),float(header.maxs[2])],
            'geoid_correction_applied':False}


def selected_indices(xyz, domain, code):
    """Folhas ordenadas possuem a própria área nominal; borda comum vai à menor chave."""
    xmin,ymin,xmax,ymax=domain.context.bounds
    mask=np.isfinite(xyz).all(axis=1) & (xyz[:,0]>=xmin) & (xyz[:,0]<=xmax) & (xyz[:,1]>=ymin) & (xyz[:,1]<=ymax)
    indices=np.flatnonzero(mask)
    if not len(indices): return indices
    inside=shapely.intersects_xy(domain.context,xyz[indices,0],xyz[indices,1])
    indices=indices[inside]
    owner=np.full(len(indices),'',dtype='U8')
    for tile in domain.nominal_tiles.itertuples():
        eligible=(owner=='') & shapely.intersects_xy(tile.geometry,xyz[indices,0],xyz[indices,1])
        owner[eligible]=tile.quadricula
    return indices[owner==code]


def qc_mask(points, config):
    rn=np.asarray(points.return_number)
    nr=np.asarray(points.number_of_returns)
    return (~np.asarray(points.withheld).astype(bool) & (rn>=1) & (rn<=nr) &
            ~np.isin(np.asarray(points.classification),config.input_preparation.excluded_noise_classes))


def load_ground(config, domain, rows, event):
    parts=[]
    classes=set()
    headers=[]
    raw_context_count=0
    for row in rows:
        if row['produto']!='MDT': continue
        path=Path(row['selected_laz'])
        event('load_mdt',tile=row['quadricula'])
        with laspy.open(path,read_evlrs=False) as reader:
            header=check_header(reader.header,config)
            header.update(path=str(path),tile=row['quadricula'],product='MDT')
            headers.append(header)
            for points in reader.chunk_iterator(config.resources.chunk_points):
                xyz=np.column_stack([points.x,points.y,points.z])
                idx=selected_indices(xyz,domain,row['quadricula'])
                idx=idx[qc_mask(points,config)[idx]]
                if not len(idx): continue
                classes.update(np.unique(np.asarray(points.classification)[idx]).tolist())
                raw_context_count+=len(idx)
                if raw_context_count>config.terrain.max_support_points or raw_context_count*2048>config.resources.max_ram_gib*2**30:
                    raise ValueError('MDT da janela excede orçamento explícito de triangulação; reduzir janela')
                parts.append(xyz[idx])
    if not parts: raise ValueError('Sem pontos MDT elegíveis no contexto')
    xyz=np.concatenate(parts)
    keys=np.rint(xyz/config.terrain.coordinate_key_m).astype(np.int64)
    _,first=np.unique(keys,axis=0,return_index=True)
    duplicate_xyz=len(xyz)-len(first)
    xyz=xyz[first]
    keys=keys[first]
    _,starts,counts=np.unique(keys[:,:2],axis=0,return_index=True,return_counts=True)
    # np.unique(XYZ) ordenou por X/Y/Z: todos os membros de um XY são contíguos.
    zmin=np.minimum.reduceat(xyz[:,2],starts)
    zmax=np.maximum.reduceat(xyz[:,2],starts)
    ground=xyz[starts].copy()
    for start,count,index in zip(starts[counts>1],counts[counts>1],np.flatnonzero(counts>1)):
        ground[index,2]=np.median(xyz[start:start+count,2])
    conflicted=(zmax-zmin)>config.terrain.maximum_xy_z_spread_m
    ground=ground[~conflicted]
    if len(ground)<3: raise ValueError('Suporte MDT insuficiente após QC de XY')
    return ground, {'headers':headers,'source_classes':sorted(classes),'owned_context_records':raw_context_count,
        'duplicate_xyz_keys_removed':duplicate_xyz,'xy_groups_multiple_z':int(np.sum(counts>1)),
        'xy_groups_excluded_z_conflict':int(conflicted.sum()),'support_vertices':len(ground),
        'coordinate_key_m':config.terrain.coordinate_key_m,
        'xy_z_aggregation':'median_of_unique_xyz_within_xy_key; exclude_spread_above_limit',
        'ownership':'nominal_tile; shared_boundary_lexicographically_first_tile; export_halo_discarded',
        'class_remapping':False}
