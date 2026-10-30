"""Invariantes científicos da rota PyCrown original, sem referência fabricada."""
from pathlib import Path
import json
import subprocess
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from affine import Affine

from sbsr_lidar.crown_data import owned_indices,deduplicate_ground,completed,query
from sbsr_lidar.crown_metrics import choose_units
from sbsr_lidar.crown_plan import load_crown_design,crown_scenarios
from sbsr_lidar.crown_run import cache_identity
from sbsr_lidar.domain import Domain
from sbsr_lidar.storage import fingerprint,atomic_write_json
from sbsr_lidar.terrain_surface import Surface
from sbsr_lidar.indicator_support import RasterSupport,UnitAssigner
from sbsr_lidar.canopy_masks import patch_layers
from sbsr_lidar.input_qc import GridLayout

ROOT=Path(__file__).resolve().parents[2]


def domain():
    tiles=gpd.GeoDataFrame({'quadricula':['1000-001','1000-002']},geometry=[shapely.box(0,0,200,200),shapely.box(200,0,400,200)],crs=31983)
    p=shapely.box(0,0,400,200)
    return Domain('test','TEST',p,p,p,tiles,{'role':'development','block_id':'test'})


def design():return load_crown_design(ROOT/'configs/amostra_pycrown_exploratoria_v0_3_0.yaml')


def worker(tmp_path,chm,valid,**updates):
    np.savez(tmp_path/'input.npz',chm=chm,valid=valid)
    job={'input':str(tmp_path/'input.npz'),'output':str(tmp_path/'labels.npz'),'upstream_root':str(ROOT/'third_party/pycrown_upstream'),
        'resolution_m':1.,'height_m':3.,'detection_radius_m':3.,'crown_radius_m':8.,'th_seed':.7,'th_crown':.55,'algorithm':'dalponteCIRC_numba',**updates}
    (tmp_path/'job.json').write_text(json.dumps(job))
    result=subprocess.run([str(ROOT/'.venv-pycrown/bin/python'),str(ROOT/'scripts/pycrown_worker.py'),str(tmp_path/'job.json')],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    return dict(np.load(tmp_path/'labels.npz')),json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize('algorithm',['dalponteCIRC_numba','dalponte_numba'])
def test_original_pycrown_known_blob(tmp_path,algorithm):
    a=np.zeros((11,11),dtype='float32');a[3:8,3:8]=8;a[5,5]=10
    result,report=worker(tmp_path,a,np.ones(a.shape,dtype=bool),algorithm=algorithm)
    assert report['seeds']==1
    assert np.count_nonzero(result['labels'])==25
    np.testing.assert_array_equal(result['seeds'],[[5],[5]])


def test_original_pycrown_nodata_is_a_barrier_and_strict_height(tmp_path):
    a=np.full((11,11),3,dtype='float32');valid=np.ones(a.shape,dtype=bool);valid[:,5]=False
    result,report=worker(tmp_path,a,valid)
    assert report['seeds']==0 and not result['labels'].any()
    a[3:8,2:9]=8;a[5,3]=10;a[5,7]=10
    result,report=worker(tmp_path,a,valid)
    assert report['seeds']==2 and not result['labels'][:,5].any()
    assert set(np.unique(result['labels'][:,0:5])) & set(np.unique(result['labels'][:,6:]))=={0}


def test_plateau_centroid_maps_to_actual_plateau(tmp_path):
    a=np.zeros((15,15),dtype='float32');a[4:11,4:11]=8;a[7,7]=15;valid=np.ones(a.shape,dtype=bool)
    result,report=worker(tmp_path,a,valid,resolution_m=2.)
    assert report['effective_detection_radius_m']==4.
    assert report['plateau_centroids_relocated']>0
    for col,row in result['seeds'].T:assert a[row,col]>3


def test_unique_nominal_tile_ownership_including_boundaries():
    d=domain();xyz=np.array([[199,20,0],[200,20,0],[201,20,0],[450,20,0],[np.nan,20,0]])
    a=owned_indices(xyz,d,'1000-001');b=owned_indices(xyz,d,'1000-002')
    assert a.tolist()==[0,1] and b.tolist()==[2]
    assert not set(a)&set(b)


def test_ground_duplicate_median_and_conflict(config):
    a=np.array([[1,1,10],[0,0,4],[1,1,10],[1,1,10.04],[2,2,1],[2,2,2]],float)
    result=deduplicate_ground(a,config)
    np.testing.assert_allclose(result,[[0,0,4],[1,1,10.02]])


def test_adjacent_tin_contexts_same_continuous_height(config):
    x,y=np.meshgrid(np.arange(188,213,2.),np.arange(0,25,2.));z=.1*x+.2*y+40;xyz=np.column_stack([x.ravel(),y.ravel(),z.ravel()])
    points=np.array([[199.99,9.5],[200,10],[200.01,10.5]])
    a=Surface(xyz[xyz[:,0]<=210],config.terrain);b=Surface(xyz[xyz[:,0]>=190],config.terrain)
    za,sa=query(a,points,config);zb,sb=query(b,points,config)
    assert (sa==0).all() and (sb==0).all();np.testing.assert_allclose(za,zb,atol=1e-10)
    np.testing.assert_allclose(za,.1*points[:,0]+.2*points[:,1]+40,atol=1e-10)


def test_connected_patches_are_not_individual_crown_count(config):
    labels=np.zeros((5,5),dtype='int32');labels[1:4,1:3]=1;labels[1:4,3]=2
    layout=GridLayout(5,5,Affine(1,0,0,0,-1,5),1.,np.ones((5,5),bool),np.ones((5,5),bool),np.zeros((5,5),bool))
    d=domain();d.context=d.measurement=shapely.box(0,0,5,5)
    mask=(labels>0).astype('uint8');patches,_,_,summary=patch_layers(config,layout,d,mask,'test',3.,np.ones((5,5),bool))
    assert len(patches)==1 and len(np.unique(labels[labels>0]))==2
    assert summary['components_are_not_individual_trees']


def test_selection_is_reproducible_independent_of_scores():
    table=pd.DataFrame({'corridor_id':['a']*30,'unit_id':[f'U{i}' for i in range(30)],'eligible_A_plus_3D':[True]*30,'I6':np.arange(30)})
    a=choose_units(table,design());b=choose_units(table.sample(frac=1,random_state=5).assign(I6=-999),design())
    assert set(a.loc[a.selected_primary_cohort,'unit_id'])==set(b.loc[b.selected_primary_cohort,'unit_id'])
    assert a.selected_primary_cohort.sum()==15
    table.eligible_A_plus_3D=False;assert not choose_units(table,design()).selected_primary_cohort.any()


def test_checkpoint_detects_mutation(tmp_path):
    p=tmp_path/'data.txt';p.write_text('complete');seal=tmp_path/'complete.json';atomic_write_json(seal,{'outputs':[fingerprint(p)]})
    assert completed(seal);p.write_text('changed');assert completed(seal) is None


def test_data_cache_changes_with_inputs_parameters_and_domain(config):
    d=domain();key=cache_identity(config,design(),d,[{'sha256':'a'}])
    assert key!=cache_identity(config,design(),d,[{'sha256':'b'}])
    cfg=config.model_copy(update={'terrain':config.terrain.model_copy(update={'maximum_distance_m':4.})})
    assert key!=cache_identity(cfg,design(),d,[{'sha256':'a'}])
    d.context=d.context.buffer(1);assert key!=cache_identity(config,design(),d,[{'sha256':'a'}])
    d=domain();d.nominal_tiles.loc[0,'geometry']=shapely.box(0,0,199,200)
    assert key!=cache_identity(config,design(),d,[{'sha256':'a'}])


def test_protocol_rejects_shifted_grid_before_execution():
    from sbsr_lidar.config import load_config
    from sbsr_lidar.crown_run import prepare
    cfg=load_config(ROOT/'configs/terreno_congelado_etapa04.yaml');prepare(cfg,design())
    moved=cfg.model_copy(update={'grid':cfg.grid.model_copy(update={'origin_x':.25})})
    with pytest.raises(ValueError,match='origem'):prepare(moved,design())


def test_protocol_scenarios_bounded():
    scenarios=crown_scenarios();assert len(scenarios)==12
    assert len({s.scenario_id for s in scenarios})==12
    assert max(s.crown_radius_m+s.detection_radius_m for s in scenarios)<=design().halo_m
    assert not design().municipal_mode_enabled and not design().external_accuracy_claims_enabled


def test_fixed_boundary_owner_uses_canonical_pixel():
    units=gpd.GeoDataFrame({'unit_id':['left','right']},geometry=[shapely.box(0,0,2,4),shapely.box(2,0,4,4)],crs=31983)
    a=np.ones((4,4),dtype='uint8');support=RasterSupport(a,a,np.zeros_like(a),a==1,Affine(1,0,0,0,-1,4),31983)
    assigner=UnitAssigner(units,support)
    assert assigner.assign(np.array([2.,2.]),np.array([1.,2.])).tolist()==[1,1]
    assert assigner.boundary_ties==2


def test_common_support_counts_do_not_include_native_only_points(config,tmp_path):
    from sbsr_lidar.indicator_support import aggregate_returns
    p=tmp_path/'heights.parquet'
    pd.DataFrame({'x':[.5,2.5],'y':[.5,.5],'h':[5.,6.],'classification':[5,5],
        'terrain_status':[0,0],'qc_flags':[0,0]}).to_parquet(p,index=False)
    a=np.ones((2,4),dtype='uint8');support=RasterSupport(a,a,np.zeros_like(a),a==1,Affine(1,0,0,0,-1,2),31983)
    full=shapely.box(0,0,4,2);common=shapely.box(0,0,1,2)
    units=gpd.GeoDataFrame({'unit_id':['U']},geometry=[full],crs=31983)
    pools,_=aggregate_returns(config,p,{'u':units},support,full,common,observation_geometry=common)
    pool=pools['u'];assert pool['counts']['n_mds_records'].tolist()==[2]
    assert pool['counts']['n_records_common_valid_H'].tolist()==[1]
    assert pool['counts']['n_cells_observed_center'].tolist()==[2]
    assert pool['counts']['n_vegetation_records'].tolist()==[1]
    np.testing.assert_array_equal(pool['heights'][0],[5.])


