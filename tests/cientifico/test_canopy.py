from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import rasterio
from shapely.geometry import box

from test_terrain import terrain_inputs
from test_reference import annotation_package
from sbsr_lidar.canopy import canopy_run
from sbsr_lidar.canopy_features import accumulate_points,local_geometry
from sbsr_lidar.canopy_masks import (observation_mask,make_masks,classification_status,observed_geometry,patch_layers)
from sbsr_lidar.domain import Domain
from sbsr_lidar.input_qc import grid_layout
from sbsr_lidar.storage import fingerprint,read_json,atomic_write_json
from sbsr_lidar.terrain import terrain_run


def domain_layout(config,measurement=None):
    context=box(0,0,4,4)
    measurement=context if measurement is None else measurement
    domain=Domain('main','synthetic',measurement,measurement,context,
                  gpd.GeoDataFrame(geometry=[],crs=config.grid.epsg),{})
    return domain,grid_layout(config,domain)


def counts_template(layout):
    names=['all','usable','valid_h','above_geometry','multiple','first','structure','water_class','bridge_class','candidate_missing_h']
    return {name:np.zeros(layout.shape,dtype=np.uint32) for name in names}


def feature_template(layout):
    return {name:np.full(layout.shape,value) for name,value in
            [('planarity',.4),('linearity',.2),('roughness_m',.3),('xy_spread_m',1.),('neighbor_count',8)]}


def test_class3_retained_by_height_and_ground_building_never_promoted(config,tmp_path):
    d,g=domain_layout(config)
    table=pd.DataFrame({'x':[.5,1.5,2.5,3.5],'y':[3.5]*4,'z_absolute':[102.5,107,110,115],
        'h':[2.5,7.,10.,15.],'classification':[3,3,2,6],'qc_flags':[0]*4,'terrain_status':[0]*4,
        'source_tile':['3313-333']*4,'source_point_index':range(4),'number_of_returns':[1]*4,
        'return_number':[1]*4,'in_measurement':[True]*4})
    path=tmp_path/'points.parquet';pq.write_table(pa.Table.from_pandas(table,preserve_index=False),path)
    counts,candidate,class1,xyz,lookup,report=accumulate_points(config,g,path,[2.,3.,5.])
    observation,valid=observation_mask(g,counts,np.ones(g.shape,dtype=bool))
    masks,flags,_=make_masks(config,g,counts,candidate,class1,feature_template(g),valid)
    assert masks[2.]['baseline'][0,:].tolist()==[1,1,0,0]
    assert masks[3.]['baseline'][0,:].tolist()==[0,1,0,0]
    assert masks[5.]['baseline'][0,:].tolist()==[0,1,0,0]
    assert flags[3.][0,0]&32 # sensibilidade de altura, sem reclassificar classe 3 como arbusto


def test_no_tree_detection_distinct_from_no_observation_no_terrain_and_excluded(config):
    d,g=domain_layout(config);counts=counts_template(g)
    counts['all'][0,:]=[1,0,1,1];counts['usable'][0,:]=[1,0,1,0];counts['valid_h'][0,:]=[1,0,0,0]
    obs,valid=observation_mask(g,counts,np.ones(g.shape,dtype=bool))
    assert obs[0,:].tolist()==[1,2,3,4]
    candidates={3.:np.zeros(g.shape,dtype=np.uint32)}
    masks,_,_=make_masks(config,g,counts,candidates,candidates,feature_template(g),valid)
    assert masks[3.]['baseline'][0,:].tolist()==[0,255,255,255]
    states=classification_status(obs,masks[3.]['baseline'])
    assert states[0,:].tolist()==[0,3,4,5]


def test_single_small_candidate_preserved_in_baseline_uncertain_in_refined(config):
    d,g=domain_layout(config);counts=counts_template(g)
    for name in ['all','usable','valid_h']:counts[name][:]=1
    candidate={3.:np.zeros(g.shape,dtype=np.uint32)};candidate[3.][1,1]=1
    cls1={3.:np.zeros(g.shape,dtype=np.uint32)}
    masks,flags,_=make_masks(config,g,counts,candidate,cls1,feature_template(g),np.ones(g.shape,dtype=bool))
    assert np.sum(masks[3.]['baseline']==1)==1
    assert masks[3.]['refinada'][1,1]==2 and flags[3.][1,1]&4
    assert np.array_equal(masks[3.]['baseline']!=255,masks[3.]['refinada']!=255)


def test_class1_omission_and_planar_conflict_are_unknown_not_truth(config):
    d,g=domain_layout(config);counts=counts_template(g)
    counts['above_geometry'][:]=10;counts['multiple'][:]=5;counts['structure'][1,1]=8
    candidate={3.:np.zeros(g.shape,dtype=np.uint32)};candidate[3.][1,1]=2
    cls1={3.:np.zeros(g.shape,dtype=np.uint32)};cls1[3.][2,2]=3
    geometry=feature_template(g);geometry['planarity'][:]=.95;geometry['roughness_m'][:]=.02
    masks,flags,_=make_masks(config,g,counts,candidate,cls1,geometry,np.ones(g.shape,dtype=bool))
    assert masks[3.]['baseline'][1,1]==1 and masks[3.]['refinada'][1,1]==2 and flags[3.][1,1]&8
    assert masks[3.]['baseline'][2,2]==0 and masks[3.]['refinada'][2,2]==2 and flags[3.][2,2]&1
    assert not np.any((masks[3.]['refinada']==1)&(masks[3.]['baseline']!=1))


def test_covariance_plane_and_vertical_column_are_diagnostic(config):
    d,g=domain_layout(config)
    xx,yy=np.meshgrid(np.arange(.6,2.5,.3),np.arange(.6,2.5,.3))
    xyz=np.c_[xx.ravel(),yy.ravel(),np.full(xx.size,100.)]
    query=np.zeros(g.shape,dtype=bool);query[2,1]=True # XY=(1.5,1.5)
    features,report=local_geometry(config,g,xyz,query,lambda *a,**k:None)
    assert features['planarity'][2,1]>.8 and features['roughness_m'][2,1]<1e-6
    xyz=np.c_[np.full(12,1.5),np.full(12,1.5),np.arange(12)*.5+100]
    features,_=local_geometry(config,g,xyz,query,lambda *a,**k:None)
    assert features['linearity'][2,1]>.99 and features['xy_spread_m'][2,1]<1e-6


def test_patch_context_before_exact_measurement_clip_and_area_stability(config):
    d,g=domain_layout(config,box(1.5,0,4,4))
    mask=np.zeros(g.shape,dtype=np.uint8);mask[1,:3]=1
    context,core,labels,stats=patch_layers(config,g,d,mask,'baseline',3.,np.ones(g.shape,dtype=bool))
    assert len(context)==len(core)==1
    assert context.iloc[0].context_area_m2==3.
    assert core.geometry.iloc[0].area==stats['candidate_area_measurement_exact_m2']==1.5
    assert core.iloc[0].patch_id==context.iloc[0].patch_id
    assert labels[1,0]>0 # parte externa não foi apagada antes de conectar
    assert core.geometry.iloc[0].difference(d.measurement).area==0
    _,_,_,again=patch_layers(config,g,d,mask,'baseline',3.,np.ones(g.shape,dtype=bool))
    assert again==stats


def test_diagonal_connectivity_valid_multigeometry_and_zero_area_touch(config):
    d,g=domain_layout(config)
    mask=np.zeros(g.shape,dtype=np.uint8);mask[1,1]=mask[2,2]=1
    context,core,_,stats=patch_layers(config,g,d,mask,'baseline',3.,np.ones(g.shape,dtype=bool))
    assert stats['components_context']==1 and context.geometry.is_valid.all() and context.geometry.area.sum()==2
    d,g=domain_layout(config,box(1,0,4,4));mask=np.zeros(g.shape,dtype=np.uint8);mask[1,0]=1
    context,core,_,stats=patch_layers(config,g,d,mask,'baseline',3.,np.ones(g.shape,dtype=bool))
    assert len(context)==1 and core.empty and stats['candidate_area_measurement_exact_m2']==0


def test_missing_candidate_H_does_not_become_confirmed_absence(config):
    d,g=domain_layout(config);counts=counts_template(g);counts['candidate_missing_h'][0,0]=1
    candidate={3.:np.zeros(g.shape,dtype=np.uint32)}
    masks,flags,_=make_masks(config,g,counts,candidate,candidate,feature_template(g),np.ones(g.shape,dtype=bool))
    assert masks[3.]['refinada'][0,0]==2 and flags[3.][0,0]&2


def test_full_pipeline_no_labels_cache_and_empty_crown_case(terrain_inputs,annotation_package,monkeypatch):
    c=terrain_inputs
    sources={case:terrain_run(c,case,requested_method='tin') for case in ['main','adversarial']}
    state=read_json(c.paths.state_file)
    state['etapas']['04']['status']='concluida';state['etapas']['05']={'nome':'referencia','status':'concluida','artefatos':[]}
    state['terreno_altura_piloto']={'principal':sources['main'],'adverso':sources['adversarial']}
    state['referencia_anotacao']={'package':str(annotation_package)};atomic_write_json(c.paths.state_file,state)
    atomic_write_json(annotation_package/'integridade_plano.json',{'files':{name:fingerprint(annotation_package/name) for name in ['amostras.gpkg','plano_referencia.json']}})
    originals=[fingerprint(p) for p in c.paths.data_root.rglob('*.laz')]
    annotation_before=fingerprint(annotation_package/'trabalho/anotacoes.gpkg')
    for case in ['main','adversarial']:
        result=canopy_run(c,case);report=read_json(Path(result['report']))
        assert not report['quality']['supervised_classifier_trained'] and report['quality']['confusion_matrix'] is None
        assert report['quality']['precision'] is None and report['selection']['provisional']
        products={Path(p).name:Path(p) for p in report['products']}
        profiles=[]
        for name,path in products.items():
            if path.suffix=='.tif':
                with rasterio.open(path) as ds:
                    profiles.append((ds.shape,ds.transform,ds.crs));assert ds.tags()['stage']=='06'
        assert len(set(profiles))==1
        with rasterio.open(products['copa_baseline_h3_contexto.tif']) as a,rasterio.open(products['copa_refinada_h3_contexto.tif']) as b:
            assert np.array_equal(a.read(1)!=255,b.read(1)!=255)
            assert set(np.unique(a.read(1))).issubset({0,1,255})
        if case=='adversarial':
            assert report['scenarios']['baseline_h3']['candidate_area_measurement_exact_m2']==0
            assert gpd.read_file(products['mascaras_manchas.gpkg'],layer='baseline_h3_medicao').empty
        assert not report['spectral']['used_as_classification_threshold']
        assert report['spectral']['zero_denominator_is_nodata']
        cached=canopy_run(c,case);assert cached['cache_hit'] and cached['report']==result['report']
    assert [fingerprint(Path(p['path'])) for p in originals]==originals
    assert fingerprint(annotation_package/'trabalho/anotacoes.gpkg')==annotation_before


def test_stale_raw_H_inputs_are_rejected(terrain_inputs,annotation_package):
    c=terrain_inputs
    sources={case:terrain_run(c,case,requested_method='tin') for case in ['main','adversarial']}
    s=read_json(c.paths.state_file);s['etapas']['04']['status']='concluida';s['etapas']['05']={'nome':'ref','status':'concluida','artefatos':[]}
    s['referencia_anotacao']={'package':str(annotation_package)}
    s['terreno_altura_piloto']={'principal':sources['main'],'adverso':sources['adversarial']};atomic_write_json(c.paths.state_file,s)
    c.paths.protocol_file.write_text('Protocolo alterado depois de H\n')
    with pytest.raises(ValueError,match='mudaram desde a etapa 04'):canopy_run(c,'main')
