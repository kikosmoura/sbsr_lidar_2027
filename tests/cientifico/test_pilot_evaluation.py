"""Invariantes de seleção, dependência e orçamento da etapa 11."""
from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError
from shapely.geometry import box, MultiPolygon

from sbsr_lidar.pilot_planning import load_design, StudyDesign, connected_blocks, choose_candidates, geometric_units
from sbsr_lidar.pilot_evidence import cost_projection
from sbsr_lidar.pilot_evaluation import failure_inventory, assessment_criteria


def test_design_cannot_enable_execution_or_municipal_batch():
    design = load_design(Path('configs/amostra_cientifica_v0_2_0.yaml'))
    assert design.evaluation_corridors*design.target_units_per_corridor == 120
    for field in ['execution_enabled','municipal_mode_enabled']:
        data=design.model_dump(); data[field]=True
        with pytest.raises(ValidationError): StudyDesign.model_validate(data)
    data=design.model_dump(); data['target_evaluation_units']=150
    with pytest.raises(ValidationError): StudyDesign.model_validate(data)


def test_blocks_use_transitive_proximity_not_centroid_distance_and_are_order_invariant():
    f=gpd.GeoDataFrame({'corridor_id':['a','b','c','d']},geometry=[box(0,0,1,1),box(2,0,3,1),box(4,0,5,1),box(20,0,21,1)],crs=31983)
    m=connected_blocks(f,1.)
    assert m['a']==m['b']==m['c'] and m['d']!=m['a']
    assert m==connected_blocks(f.iloc[::-1],1.)
    assert connected_blocks(f,0)['a']!=connected_blocks(f,0)['b']


def test_geometric_capacity_counts_disconnected_fragments_and_is_not_observed_support():
    geometry=MultiPolygon([box(1,1,6,6),box(8,1,13,6)])
    assert geometric_units(geometry,50,25)==2
    assert geometric_units(geometry,50,26)==0
    assert geometric_units(box(0,0,100,50),50,25)==2


def test_candidate_order_keeps_whole_block_in_one_role_and_does_not_use_outcomes():
    design=load_design(Path('configs/amostra_cientifica_v0_2_0.yaml'))
    f=pd.DataFrame({'corridor_id':[f'c{i}' for i in range(20)],'block_id':[f'b{i//2}' for i in range(20)],
        'stratum':['EN','WN','ES','WS']*5,'planning_eligible':[True]*20,'selection_priority':[f'{i:02d}' for i in range(20)],'I6':range(20)})
    a=choose_candidates(f,design); f['I6']=np.arange(20)[::-1]
    b=choose_candidates(f.sample(frac=1,random_state=31),design)
    assert a.equals(b) and a.selected_for_planning.sum()==10
    chosen=f.merge(a,on='corridor_id')
    assert chosen.block_id.is_unique
    assert chosen.proposed_role.eq('avaliacao').sum()==8 and chosen.proposed_role.eq('desenvolvimento').sum()==2
    assert a.actual_eligible_units.isna().all()


def test_validation_absence_is_an_impediment_and_failures_have_cache_resolution():
    reports={(stage,case):{'run_id':f'{stage}-{case}'} for stage in ['03','04','06','07','08','09','10'] for case in ['main','adversarial']}
    c=assessment_criteria(reports,{'completed_annotations':0,'independent_priority_references':0},True).set_index('criterion_id')
    assert c.loc['C11_03','status']=='dependencia_impeditiva'
    assert c.loc['C11_10','status']=='nao_demonstrada'
    failures=failure_inventory()
    assert failures.failure_id.is_unique and failures.concrete_resolution.str.len().min()>40
    assert failures.cache_invalidation.notna().all()


def test_cost_uses_measured_records_repeated_visits_and_explicit_budget_factor():
    design=load_design(Path('configs/amostra_cientifica_v0_2_0.yaml'))
    rows=[]; reports={}
    for case in ['main','adversarial']:
        for stage in ['03','04','06','07','08','09','10']:
            rows.append({'stage':stage,'case':case,'elapsed_seconds':10.,'output_bytes':1000,'peak_rss_mib':100.})
        reports[('03',case)]={'clouds':[{'points_read':1000000}], 'domain':{'context_area_m2':1000.,'halo_m':10.}}
    ids=[f'c{i}' for i in range(12)]
    proposal=gpd.GeoDataFrame({'corridor_id':ids,'candidate_order':range(1,13),'selected_for_planning':[True]*10+[False]*2},geometry=[box(i*100,0,i*100+10,10) for i in range(12)],crs=31983)
    links=pd.DataFrame({'corridor_id':ids,'tile':['t']*12})
    files=pd.DataFrame({'tile':['t','t'],'product':['MDT','MDS'],'exists':[True,True],'declared_points':[500000,500000]})
    calibration, projection=cost_projection(pd.DataFrame(rows),reports,design,proposal,links,files)
    row=projection.loc[projection.primary_design].iloc[0]
    assert row.declared_records_unique_files==1000000 and row.declared_record_visits_per_corridor==10000000
    assert row.estimated_baseline_seconds_low==60 and row.estimated_baseline_seconds_budget==1800
    assert pd.isna(row.download_seconds) and pd.isna(row.human_annotation_seconds)
    assert row.cost_type.startswith('uncalibrated')
