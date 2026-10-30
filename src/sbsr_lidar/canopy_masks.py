"""Máscaras comparáveis e manchas em contexto; incerteza não vira ausência."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import shapely
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape

UNCERTAINTY={1:'class1_high_potential_omission',2:'vegetation_class_without_valid_point_H',
    4:'isolated_single_candidate_record',8:'planar_structure_class_conflict',16:'thin_linear_structure_candidate',
    32:'height_threshold_sensitivity',64:'geometry_not_reliable_for_candidate',
    128:'LAS_water_class_hint',256:'LAS_bridge_class_hint'}
OBSERVATION={1:'observed_with_valid_terrain_and_point_H',2:'no_MDS_observation',
             3:'no_valid_terrain_or_no_valid_point_H',4:'only_QC_excluded_MDS_records',255:'outside_context'}
CLASSIFICATION={0:'observed_without_detected_candidate',1:'observed_with_candidate_crown',
                2:'classification_uncertain',3:'no_observation',4:'no_terrain_support',
                5:'only_excluded_records',255:'outside_context'}


def observation_mask(layout,counts,terrain_valid):
    status=np.full(layout.shape,255,dtype=np.uint8)
    status[layout.context_mask]=2
    present=layout.context_mask&(counts['all']>0)
    status[present]=4
    usable=present&(counts['usable']>0)
    status[usable]=3
    valid=usable&terrain_valid&(counts['valid_h']>0)
    status[valid]=1
    return status,valid


def make_masks(config,layout,counts,candidates,class1,geometry,valid):
    masks={};flags={}
    high=min(candidates);low=max(candidates)
    sensitivity=(candidates[high]>0)!=(candidates[low]>0)
    denominator=counts['above_geometry']
    single_fraction=np.divide(denominator-counts['multiple'],denominator,
                              out=np.full(layout.shape,np.nan),where=denominator>0)
    structure_fraction=np.divide(counts['structure'],denominator,
                                out=np.zeros(layout.shape),where=denominator>0)
    reliable=np.isfinite(geometry['planarity'])
    for height,n in sorted(candidates.items()):
        baseline=np.full(layout.shape,255,dtype=np.uint8)
        baseline[valid]=0
        candidate=valid&(n>=config.vegetation.minimum_points_per_cell)
        baseline[candidate]=1
        # Apenas consulta de vizinhança: nenhum pixel é adicionado à copa.
        neighbors=ndimage.convolve(candidate.astype(np.uint8),np.ones((3,3),dtype=np.uint8),mode='constant',cval=0)
        isolated=candidate&(n==1)&(neighbors==1)
        planar=candidate&reliable&(geometry['planarity']>=config.vegetation.planar_threshold)&(
            geometry['roughness_m']<=config.vegetation.planar_max_roughness_m)&(
            structure_fraction>=config.vegetation.structure_fraction_threshold)
        thin=candidate&reliable&(geometry['linearity']>=config.vegetation.linear_threshold)&(
            geometry['xy_spread_m']<=config.vegetation.thin_max_xy_spread_m)&(
            single_fraction>=config.vegetation.thin_min_single_return_fraction)
        potential_omission=valid&(class1[height]>0)
        missing=valid&(counts['candidate_missing_h']>0)
        values=np.zeros(layout.shape,dtype=np.uint16)
        for bit,mask in [(1,potential_omission),(2,missing),(4,isolated),(8,planar),(16,thin),
                         (32,valid&sensitivity),(64,candidate&~reliable),
                         (128,valid&(counts['water_class']>0)),(256,valid&(counts['bridge_class']>0))]:
            values[mask]|=bit
        values[~valid]=np.iinfo(np.uint16).max
        refined=baseline.copy()
        uncertain=valid&(isolated|planar|thin|missing|((baseline==0)&potential_omission))
        refined[uncertain]=2
        masks[height]={'baseline':baseline,'refinada':refined};flags[height]=values
    return masks,flags,{'single_return_fraction_above_lowest_height':single_fraction,
                       'structure_fraction_above_lowest_height':structure_fraction}


def classification_status(observation,mask):
    status=np.full(mask.shape,255,dtype=np.uint8)
    status[observation==2]=3;status[observation==3]=4;status[observation==4]=5
    valid=observation==1
    status[valid]=mask[valid]
    return status


def _polygonal(geom):
    if geom.is_empty:return geom
    if not geom.is_valid:geom=shapely.make_valid(geom)
    if geom.geom_type in {'Polygon','MultiPolygon'}:return geom
    return shapely.union_all([g for g in getattr(geom,'geoms',[]) if g.geom_type in {'Polygon','MultiPolygon'}])


def observed_geometry(layout,valid,domain):
    polygons=[_polygonal(shape(geom).intersection(domain.context).intersection(domain.measurement))
              for geom,value in shapes(valid.astype(np.uint8),mask=valid,transform=layout.transform,connectivity=4)]
    polygons=[g for g in polygons if not g.is_empty and g.area>0]
    return shapely.union_all(polygons) if polygons else shapely.GeometryCollection()


def patch_layers(config,layout,domain,mask,version,height,valid):
    crown=mask==1
    structure=ndimage.generate_binary_structure(2,2 if config.vegetation.connectivity==8 else 1)
    labels,n=ndimage.label(crown,structure=structure)
    parts={}
    # Polygonizar com 4 evita anéis inválidos nas conexões diagonais de rótulos 8.
    for geometry,label in shapes(labels.astype(np.int32),mask=crown,transform=layout.transform,connectivity=4):
        parts.setdefault(int(label),[]).append(shape(geometry))
    near_invalid=ndimage.convolve((~valid).astype(np.uint8),np.ones((3,3),dtype=np.uint8),mode='constant',cval=1)>0
    censored=ndimage.maximum(near_invalid,labels,index=np.arange(1,n+1)) if n else np.empty(0)
    rows=[];core=[]
    for label,geoms in sorted(parts.items()):
        full=_polygonal(shapely.union_all(geoms).intersection(domain.context))
        if full.is_empty or full.area<=0:continue
        measurement=_polygonal(full.intersection(domain.measurement))
        patch_id=f'P06_{domain.case}_{version}_h{height:g}_{label:06d}'
        item={'patch_id':patch_id,'component_label':label,'case':domain.case,'corridor_id':domain.corridor_id,
              'version':version,'height_m':height,'context_area_m2':float(full.area),
              'measurement_area_m2':float(measurement.area),
              'crosses_measurement_boundary':bool(full.intersects(domain.measurement.boundary)),
              'touches_context_limit':bool(full.distance(domain.context.boundary)<1e-7),
              'touches_invalid_support':bool(censored[label-1]),
              'classification_validated':False,'geometry':full}
        rows.append(item)
        if not measurement.is_empty and measurement.area>0:core.append({**item,'geometry':measurement})
    columns=['patch_id','component_label','case','corridor_id','version','height_m','context_area_m2','measurement_area_m2',
             'crosses_measurement_boundary','touches_context_limit','touches_invalid_support','classification_validated','geometry']
    context=gpd.GeoDataFrame(rows,columns=columns,crs=config.grid.epsg)
    measured=gpd.GeoDataFrame(core,columns=columns,crs=config.grid.epsg)
    summary={'components_context':len(context),'components_intersecting_measurement':len(measured),
             'candidate_cells_context':int(crown.sum()),
             'candidate_cells_measurement_center':int(np.sum(crown&layout.measurement_mask)),
             'candidate_area_context_m2':float(context.context_area_m2.sum()) if len(context) else 0.,
             'candidate_area_measurement_exact_m2':float(measured.measurement_area_m2.sum()) if len(measured) else 0.,
             'uncertain_cells_measurement_center':int(np.sum((mask==2)&layout.measurement_mask)),
             'components_are_not_individual_trees':True}
    return context,measured,labels,summary
