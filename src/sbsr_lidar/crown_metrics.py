"""Métricas e coortes exploratórias; seleção por identidade, nunca por ranking."""
import hashlib
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import rasterio.windows
from rasterio.features import shapes
from shapely.geometry import shape
from .spatial_units import regular_grid,partition_check,polygonal
from .indicator_support import aggregate_returns,UnitAssigner
from .indicator_metrics import area_metrics,height_metrics
from .comparison_scores import score_variants,ranked_variant,compare_rankings,primary_variant


def selection_key(seed,identity):return hashlib.sha256(f'{seed}:{identity}'.encode()).hexdigest()


def choose_units(table,design):
    result=table.copy();result['selection_hash']=[selection_key(design.seed,i) for i in result.unit_id]
    result['selected_primary_cohort']=False
    for _,group in result.groupby('corridor_id'):
        eligible=group.loc[group.eligible_A_plus_3D].sort_values(['selection_hash','unit_id'])
        result.loc[eligible.head(design.target_units_per_corridor).index,'selected_primary_cohort']=True
    return result


def auxiliary_areas(geometry,support):
    window=rasterio.windows.from_bounds(*geometry.bounds,transform=support.transform)
    r0=max(0,int(np.floor(window.row_off)));c0=max(0,int(np.floor(window.col_off)))
    r1=min(support.observation.shape[0],int(np.ceil(window.row_off+window.height)))
    c1=min(support.observation.shape[1],int(np.ceil(window.col_off+window.width)))
    o=support.observation[r0:r1,c0:c1];u=support.uncertainty[r0:r1,c0:c1]
    transform=support.transform*rasterio.Affine.translation(c0,r0)
    result={}
    for key,mask in [('area_MDS_observed_m2',(o!=2)&(o!=255)),('area_MDS_usable_m2',(o==1)|(o==3)),
                     ('area_classification_uncertain_m2',(u!=65535)&(u!=0))]:
        geoms=[shape(g) for g,_ in shapes(mask.astype('uint8'),mask=mask,transform=transform)] if mask.size else []
        result[key]=polygonal(shapely.union_all(geoms).intersection(geometry)) if geoms else shapely.Polygon()
    return result


def physical_table(config,domain,height_path,support,observed,patches,tops,scales,canonical,event,common=None):
    empty=shapely.Polygon();effective=observed if common is None else polygonal(observed.intersection(common))
    clipped=patches.copy()
    if common is not None:clipped.geometry=clipped.geometry.intersection(common)
    clipped=clipped.loc[~clipped.geometry.is_empty & (clipped.geometry.area>0)].copy()
    crown=polygonal(shapely.union_all(clipped.geometry.to_numpy()).intersection(effective))
    rows=[];checks=[]
    for scale in scales:
        units=regular_grid(config,domain,empty,empty,scale).sort_values('unit_id').reset_index(drop=True)
        check=partition_check(units,domain.measurement,config.segmentation.area_tolerance_m2)
        if not check['ok']:raise ValueError('Partição de unidades não conserva domínio')
        checks.append({'scale':scale,**check})
        pools,audit=aggregate_returns(config,height_path,{'units':units},support,domain.measurement,crown,event,assignment_support=canonical,observation_geometry=effective)
        pool=pools['units'];assigner=UnitAssigner(units,canonical)
        usable_tops=tops.loc[tops.seed_in_measurement.astype(bool)] if len(tops) else tops
        if common is not None and len(usable_tops):usable_tops=usable_tops.loc[usable_tops.intersects(common)]
        owner=assigner.assign(usable_tops.geometry.x.to_numpy(),usable_tops.geometry.y.to_numpy()) if len(usable_tops) else np.empty(0,dtype=int)
        ntop=np.bincount(owner[owner>=0],minlength=len(units))
        for i,unit in enumerate(units.itertuples()):
            local=shapely.box(*unit.geometry.bounds)
            v=polygonal(effective.intersection(local))
            extras=auxiliary_areas(unit.geometry,support)
            area,links=area_metrics(unit.geometry,v,clipped,extras,config)
            heights=pool['heights'][i];height=height_metrics(heights,area,config)
            nintersect=sum(1 for index in tops.sindex.query(unit.geometry,predicate='intersects')) if len(tops) else 0
            row={**unit._asdict(),**area,**height,**{k:int(a[i]) for k,a in pool['counts'].items()},
                'eligible_area_observation':area['eligible_A'],
                'case':domain.corridor_id,'role':domain.metadata['role'],'block_id':domain.metadata['block_id'],
                'eligible_B':False,'eligible_B_plus_3D':False,'longitudinal_missing_reason':'eixo_nao_revalidado_nesta_amostra',
                'n_estimated_chm_seeds_owned':int(ntop[i]),'estimated_seed_density_per_ha':int(ntop[i])*10000/area['area_observed_m2'] if area['area_observed_m2'] else None,
                'n_estimated_seed_points_touching_unit_including_ties':nintersect,
                'uncertainty_screen':'class1_high_only; other_shape_conflicts_not_screened_in_this_branch',
                'auxiliary_support_areas_omitted':False,'external_accuracy_validated':False,'protocol_version':'0.3.0'}
            if row['n_vegetation_records']!=len(heights):raise ValueError('Contagem de retornos e alturas divergem')
            rows.append(row)
        checks[-1]['aggregation']=audit
    return gpd.GeoDataFrame(rows,geometry='geometry',crs=config.grid.epsg),checks


def paired_rank_stability(left,right,config,fixed_ids):
    a=left.loc[left.unit_id.isin(fixed_ids)&left.eligible_A_plus_3D].set_index('unit_id')
    b=right.loc[right.unit_id.isin(fixed_ids)&right.eligible_A_plus_3D].set_index('unit_id')
    ids=sorted(set(a.index)&set(b.index));result={'frozen_primary_units':len(fixed_ids),'paired_eligible_units':len(ids),'excluded_after_common_support':len(fixed_ids)-len(ids)}
    if not ids:return {**result,'spearman_rho':None,'reason':'no_eligible_common_support'}
    rankings=[]
    for frame in [a.loc[ids].reset_index(),b.loc[ids].reset_index()]:
        normal,variants=score_variants(frame,config)
        v=next(v for v in variants if v['variant_id']==primary_variant(config))
        rankings.append(ranked_variant(frame,frame.iloc[:0],v,normal,config,'conditional_canopy'))
    measures,_,_=compare_rankings(*rankings,config.comparison.primary_top_fraction,config)
    return {**result,**measures,'reason':None,'comparison':'within_pair_common_observed_geometry_and_identical_unit_IDs'}
