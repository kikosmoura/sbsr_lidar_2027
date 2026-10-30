from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import rasterio
import yaml
from laspy.vlrs.geotiff import GeoKeyEntryStruct
from laspy.vlrs.known import GeoKeyDirectoryVlr
from pyproj import CRS
from shapely.geometry import box

from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain, input_plan
from sbsr_lidar.input_qc import grid_layout
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json
from sbsr_lidar.terrain import terrain_run
from sbsr_lidar.terrain_inputs import check_header, selected_indices, load_ground
from sbsr_lidar.terrain_surface import Surface, normalize_z
from sbsr_lidar.terrain_validation import reserved_splits, validate_surfaces, choose_method


def plane(x,y): return 100 + .1*(x-330000)+.02*(y-7390000)


def header(product,epsg=31983):
    h=laspy.LasHeader(version='1.4' if product=='MDS' else '1.2',point_format=8 if product=='MDS' else 1)
    h.add_crs(CRS.from_epsg(epsg))
    h.offsets=np.array([320000.,7390000.,0.] if product=='MDS' else [310000.,7340000.,0.])
    h.scales=np.array([.001]*3)
    if not any(v.record_id==34735 for v in h.vlrs):
        v=GeoKeyDirectoryVlr()
        v.geo_keys=[GeoKeyEntryStruct(1024,0,1,1),GeoKeyEntryStruct(3072,0,1,epsg)]
        h.vlrs.append(v)
    for v in h.vlrs:
        if v.record_id==34735:
            v.geo_keys.append(GeoKeyEntryStruct(3076,0,1,9001))
            v.geo_keys.append(GeoKeyEntryStruct(4099,0,1,9001))
            v.geo_keys_header.number_of_keys=len(v.geo_keys)
    h.vlrs.append(laspy.VLR(user_id='VertDatum-Geoid',record_id=1,
                           description='Maregr.Imbituba(SC)-MAPGEO2015',record_data=b''))
    return h


@pytest.fixture
def terrain_inputs(config_file,monkeypatch):
    raw=yaml.safe_load(config_file.read_text())
    raw['pilot'].update(core_tiles=['3313-333'],context_tiles=['3313-324'],sensitivity_tiles=[],halo_m=2.)
    raw['terrain'].update(maximum_distance_m=1.,validation_block_m=2.,minimum_common_validation=3,query_points=100)
    raw['sensitivity']['terrain_distances_m']=[.5,1.,2.]
    raw['resources']['chunk_points']=173
    config_file.write_text(yaml.safe_dump(raw))
    c=load_config(config_file)
    monkeypatch.setattr(Path,'is_mount',lambda p:p==c.paths.mount_root)
    c.paths.corridors.parent.mkdir()
    gpd.GeoDataFrame({'cd_identi0':[c.pilot.corridor_id,c.pilot.adversarial_corridor]},
        geometry=[box(330002,7390002,330009,7390009),box(330032,7390002,330039,7390009)],crs=c.grid.epsg).to_file(c.paths.corridors)
    codes=['3313-333','3313-324','3312-431']
    tiles=[box(330000,7390000,330010,7390020),box(330010,7390000,330020,7390020),box(330030,7390000,330040,7390020)]
    gpd.GeoDataFrame({'cd_quadric':codes},geometry=tiles,crs=c.grid.epsg).to_file(c.paths.grid)
    for code,nominal in zip(codes,tiles):
        left=nominal.bounds[0]
        xx,yy=np.meshgrid(np.arange(left-1+.25,left+11,.5),np.arange(7390000+.25,7390020,.5))
        x,y=xx.ravel(),yy.ravel()
        keep=~((x>330005)&(x<330008)&(y>7390005)&(y<7390008))
        x,y=x[keep],y[keep]
        for product in ['MDT','MDS']:
            path=c.paths.data_root/f'{product}_2020'/f'{product}_{code}_1000.laz'
            path.parent.mkdir(exist_ok=True)
            data=laspy.LasData(header(product))
            z=plane(x,y)
            if product=='MDT':
                data.x=x;data.y=y;data.z=z
                data.classification=np.full(len(x),8,dtype=np.uint8)
            else:
                extra_x=np.array([330002.25,330002.25,330002.25,330006.5])
                extra_y=np.array([7390002.25,7390002.25,7390002.25,7390006.5])
                data.x=np.r_[x,extra_x]
                data.y=np.r_[y,extra_y]
                data.z=np.r_[z,plane(extra_x,extra_y)+[5,-2,100,9]]
                data.classification=np.r_[np.full(len(x),8),[3,1,6,3]].astype(np.uint8)
                data.user_data=np.r_[np.zeros(len(x)),[5,0,100,9]].astype(np.uint8)
            data.return_number=np.ones(len(data.points),dtype=np.uint8)
            data.number_of_returns=np.ones(len(data.points),dtype=np.uint8)
            data.write(path)
    c.paths.protocol_file.parent.mkdir(exist_ok=True)
    c.paths.protocol_file.write_text('Protocolo sintético\n')
    atomic_write_json(c.paths.state_file,{'schema_version':'0.1.0','etapa_atual':'03','status':'etapa_03_concluida',
        'etapas':{'03':{'nome':'insumos','status':'concluida','artefatos':[]},'04':{'nome':'terreno','status':'nao_iniciada','artefatos':[]}},
        'piloto_executado':False,'pipeline_cientifico_implementado':False})
    return c


def test_tin_plane_exact_and_offsets_do_not_change_geometry(config):
    x,y=np.meshgrid(np.arange(0,7),np.arange(0,7))
    xyz=np.column_stack([x.ravel()+330000,y.ravel()+7390000,100+.1*x.ravel()+.2*y.ravel()])
    model=Surface(xyz,config.terrain)
    query=np.array([[330002.3,7390002.7],[330003.5,7390003.5]])
    q=model.query(query,5)
    assert np.allclose(q['tin'],100+.1*(query[:,0]-330000)+.2*(query[:,1]-7390000),atol=1e-9)
    assert np.all(q['tin_status']==0) and np.all(np.isfinite(q['idw']))


def test_outside_hull_is_not_extrapolated_even_with_close_neighbor(config):
    model=Surface(np.array([[0,0,100],[1,0,100],[0,1,100]]),config.terrain)
    q=model.query(np.array([[1.01,0.],[.1,.1]]),5)
    assert q['nearest'][0]<5
    assert np.isnan(q['tin'][0]) and np.isnan(q['idw'][0])
    assert q['tin_status'][0]==1


def test_large_triangle_rejected_and_exact_observation_preserved(config):
    xyz=np.array([[0,0,100],[20,0,101],[0,20,102]])
    q=Surface(xyz,config.terrain).query(np.array([[.2,.2],[0,0]]),5)
    assert q['nearest'][0]<5 and q['count'][0]==1
    assert np.isnan(q['tin'][0]) and np.isnan(q['idw'][0])
    assert q['tin_status'][0]==3
    assert q['tin'][1]==q['idw'][1]==100


def test_zero_negative_and_nan_not_clipped_or_double_normalized():
    result=normalize_z(np.array([105.,100.,98.,110.]),np.array([100.,100.,100.,np.nan]))
    assert np.array_equal(result[:3],[5.,0.,-2.])
    assert np.isnan(result[3])


@pytest.mark.parametrize('failure',['vertical_unit','datum','crs'])
def test_header_reference_checks(config,failure):
    h=header('MDT',31982 if failure=='crs' else 31983)
    if failure=='vertical_unit':
        for v in h.vlrs:
            if v.record_id==34735: v.geo_keys[-1].value_offset=9002
    if failure=='datum':
        h.vlrs[-1]=laspy.VLR(user_id='VertDatum-Geoid',record_id=1,description='unknown',record_data=b'')
    with pytest.raises(ValueError): check_header(h,config)


def test_nominal_ownership_removes_export_halo_and_assigns_seam_once(terrain_inputs):
    d=build_domain(terrain_inputs,'main')
    xyz=np.array([[330009.75,7390005,100],[330010,7390005,100],[330010.25,7390005,100]])
    a=selected_indices(xyz,d,'3313-333')
    b=selected_indices(xyz,d,'3313-324')
    assert set(a).isdisjoint(b) and set(a)|set(b)=={0,1,2}
    assert 1 in b # 3313-324 precede 3313-333 na borda compartilhada


def test_mdt_context_load_preserves_classes_and_distinct_offsets(terrain_inputs):
    c=terrain_inputs
    d=build_domain(c,'main')
    ground,report=load_ground(c,d,input_plan(c,d),lambda *a,**k:None)
    assert np.allclose(ground[:,2],plane(ground[:,0],ground[:,1]),atol=.00051)
    assert report['source_classes']==[8] and not report['class_remapping']
    assert all(h['offsets']==[310000.,7340000.,0.] for h in report['headers'])


def test_reserved_block_split_has_no_training_xy_leak(terrain_inputs):
    c=terrain_inputs
    d=build_domain(c,'main')
    ground,_=load_ground(c,d,input_plan(c,d),lambda *a,**k:None)
    splits=reserved_splits(ground,c)
    assert np.array_equal(splits['reserved_blocks'],reserved_splits(ground,c)['reserved_blocks'])
    held=splits['reserved_blocks']
    blocks=np.floor(ground[:,:2]/c.terrain.validation_block_m).astype(int)
    assert set(map(tuple,blocks[held])).isdisjoint(set(map(tuple,blocks[~held])))
    validation,_=validate_surfaces(ground,c,[.5,1.,2.],lambda *a,**k:None)
    selected,decision=choose_method(validation,c,'auto')
    assert selected in {'tin','idw'} and decision['rule']=='minimum_common_support_RMSE_at_fixed_radius'


@pytest.mark.parametrize('resolution',[.5,1.,2.])
def test_grid_origin_remains_aligned_for_supported_resolutions(terrain_inputs,resolution):
    raw=terrain_inputs.model_dump()
    raw['grid']['resolution_m']=resolution
    c=type(terrain_inputs).model_validate(raw)
    g=grid_layout(c,build_domain(c,'main'))
    assert g.transform.c/resolution==round(g.transform.c/resolution)
    assert g.transform.f/resolution==round(g.transform.f/resolution)


def test_full_terrain_height_pipeline_and_cache(terrain_inputs,monkeypatch):
    c=terrain_inputs
    original=[fingerprint(p) for p in c.paths.data_root.rglob('*.laz')]
    result=terrain_run(c,'main',requested_method='tin')
    report=read_json(Path(result['report']))
    assert report['stage']=='04' and len(report['validation']['metrics'])==12
    assert report['heights']['headers'][0]['offsets']!=report['ground']['headers'][0]['offsets']
    products={Path(p).name:Path(p) for p in report['products']}
    heights=pq.read_table(products['alturas_pontos.parquet']).to_pandas()
    assert np.allclose(heights.z_absolute-heights.terrain_z,heights.h,equal_nan=True)
    tree=heights[(heights.classification==3) & heights.h.notna()]
    assert np.allclose(tree.h,5.,atol=.001) and np.all(tree.user_data==5)
    assert (heights.h<0).any() and (heights.h>80).any() and heights.h.isna().any()
    assert np.any(np.isclose(heights.h,0))
    assert heights.loc[heights.h.isna(),'terrain_status'].ne(0).all()
    assert report['heights']['mds_mdt_xyz_consistency']['exact_xyz_within_2mm_n']>0
    profiles=[]
    for path in products.values():
        if path.suffix=='.tif':
            with rasterio.open(path) as ds:
                profiles.append((ds.shape,ds.transform,ds.crs))
                assert ds.tags()['stage']=='04'
    assert len(set(profiles))==1
    assert [fingerprint(Path(p['path'])) for p in original]==original
    def no_reprocess(*a,**k): raise AssertionError('Cache não deveria reprocessar MDT')
    monkeypatch.setattr('sbsr_lidar.terrain.load_ground',no_reprocess)
    again=terrain_run(c,'main',requested_method='tin')
    assert again['cache_hit'] and again['report']==result['report']
    assert read_json(Path(again['manifest']))['source_run_id']==result['run_id']


def test_terrain_failure_does_not_complete_stage(terrain_inputs,monkeypatch):
    def fail(*a,**k): raise ValueError('Falha simulada de suporte')
    monkeypatch.setattr('sbsr_lidar.terrain.load_ground',fail)
    with pytest.raises(ValueError,match='simulada'): terrain_run(terrain_inputs,'main')
    state=read_json(terrain_inputs.paths.state_file)
    assert state['ultima_execucao']['status']=='failed' and state['etapas']['04']['status']=='nao_iniciada'
