from datetime import date
from pathlib import Path
import zipfile

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyogrio
import pytest
from shapely.geometry import box
from shapely.geometry import MultiPolygon

from test_terrain import terrain_inputs
from sbsr_lidar.annotations import Annotation,PURPOSES,empty_annotations,check_annotations
from sbsr_lidar.config import Config
from sbsr_lidar.reference import reference_run
from sbsr_lidar.reference_sampling import corridor_groups,select_windows,stable_id
from sbsr_lidar.storage import atomic_write_json,read_json,fingerprint
from sbsr_lidar.terrain import terrain_run


def test_overlap_group_transitivity_prevents_train_test_leak(config):
    c=config;c.paths.corridors.parent.mkdir()
    frame=gpd.GeoDataFrame({'cd_identi0':[c.pilot.corridor_id,'connector',c.pilot.adversarial_corridor]},
        geometry=[box(0,0,2,2),box(1,0,4,2),box(3,0,5,2)],crs=c.grid.epsg)
    frame.to_file(c.paths.corridors)
    with pytest.raises(ValueError,match='mesmo grupo'):corridor_groups(c)
    frame.loc[2,'geometry']=box(10,0,12,2)
    frame.to_file(c.paths.corridors)
    rows,mapping=corridor_groups(c)
    assert mapping[c.pilot.corridor_id]==mapping['connector']
    assert mapping[c.pilot.adversarial_corridor]!=mapping['connector']
    assert {r['fold'] for r in rows if r['corridor_id']=='connector'}=={'treino'}


def test_stable_ids_depend_on_spatial_key_not_run():
    assert stable_id('W05_','corridor',31983,20,1,2)==stable_id('W05_','corridor',31983,20,1,2)
    assert stable_id('W05_','corridor',31983,20,1,2)!=stable_id('W05_','corridor',31983,20,2,2)


def test_intentional_selection_preserves_alerts_and_unknown_probability():
    rows=[]
    for i in range(6):
        rows.append({'window_id':str(i),'negative_alert_points':1 if i==0 else 0,'points':100,'valid_h_points':100,
            'regular_eligible':i!=0,
            'low_h_points':i,'high_h_points':i,'empty_cells':0,'invalid_terrain_cells':0,'edge':False,
            'density_records_m2':i+1,'fold':'treino',**{f'class_{k}':int(k==3 or i==k%6) for k in [1,2,3,4,5,6,8]},
            'geometry':box(i*20,0,i*20+20,20)})
    f=gpd.GeoDataFrame(rows,crs=31983)
    a,info=select_windows(f,3,2027);b,_=select_windows(f.iloc[::-1],3,2027)
    assert a.window_id.tolist()==b.window_id.tolist() and '0' in set(a.window_id)
    assert a.inclusion_probability.isna().all() and not info['inclusion_probabilities_known']
    assert a.loc[a.window_id=='0','intended_use'].iloc[0]=='qa'
    assert all(a.loc[a.intended_use!='qa','regular_eligible'])


def test_completed_record_requires_actual_metadata_and_does_not_guess_labels():
    base={'annotation_id':'id','task_id':'task','window_id':'window','purpose':'vegetacao','reviewer_slot':'A'}
    assert Annotation.model_validate(base).label is None
    with pytest.raises(ValueError):Annotation.model_validate({**base,'state':'concluido','label':'arvore_copa'})


@pytest.fixture
def annotation_package(tmp_path):
    directory=tmp_path/'package';directory.mkdir();(directory/'trabalho').mkdir()
    windows=[{'window_id':'w1','fold':'treino','intended_use':'treino'},
             {'window_id':'w2','fold':'teste','intended_use':'teste'}]
    tasks=[{'task_id':f'{w["window_id"]}_{slot}','window_id':w['window_id'],'purpose':'vegetacao','reviewer_slot':slot,
            'review_state':'pendente','observer':'','review_date':'','notes':''} for w in windows for slot in ['A','B']]
    atomic_write_json(directory/'plano_referencia.json',{'epsg':31983,'windows':windows,'tasks':tasks})
    gpd.GeoDataFrame({'window_id':['w1','w2']},geometry=[box(0,0,10,10),box(30,0,40,10)],crs=31983).to_file(directory/'amostras.gpkg',layer='contextos')
    for purpose in PURPOSES:
        pyogrio.write_dataframe(empty_annotations(31983,purpose),directory/'trabalho/anotacoes.gpkg',layer=purpose,
                                geometry_type='Point' if purpose=='altura' else 'MultiPolygon')
    pd.DataFrame(tasks).to_csv(directory/'trabalho/tarefas.csv',index=False)
    (directory/'evidence.txt').write_text('Fonte sintética de teste, não observação humana real.')
    atomic_write_json(directory/'trabalho/fontes_referencia.json',{'sources':{'raw':{'available':True,'path':'evidence.txt',
        'year':2020,'kind':'raw_lidar','independent_algorithm':True,'independent_sensor':False}}})
    return directory


def add_annotation(package,**overrides):
    raw={'annotation_id':'a1','task_id':'w1_A','window_id':'w1','purpose':'vegetacao','reviewer_slot':'A',
        'state':'concluido','observer':'Pessoa A (teste sintético)','annotation_date':date.today().isoformat(),'confidence':'alta',
        'source_id':'raw','source_year':2020,'temporal_compatible':'sim','method':'manual','label':'arvore_copa'}
    raw.update({k:v for k,v in overrides.items() if k!='geometry'})
    geometry=overrides.get('geometry',box(0,0,10,10))
    if geometry.geom_type=='Polygon':geometry=MultiPolygon([geometry])
    row={k:raw.get(k) for k in Annotation.model_fields}
    gpd.GeoDataFrame([row],geometry=[geometry],crs=31983).to_file(package/'trabalho/anotacoes.gpkg',layer=raw['purpose'],mode='a')


def sign_task(package,task_id,observer='Pessoa A (teste sintético)'):
    path=package/'trabalho/tarefas.csv';frame=pd.read_csv(path,keep_default_na=False)
    use=frame.task_id==task_id
    frame.loc[use,'review_state']='concluido';frame.loc[use,'observer']=observer;frame.loc[use,'review_date']=date.today().isoformat()
    frame.to_csv(path,index=False)


def test_pending_package_is_valid_without_precision_or_training(annotation_package):
    r=check_annotations(annotation_package)
    assert r['ok'] and r['pending_tasks']==4 and not r['human_labeling_complete']
    assert not r['supervised_training_allowed'] and not r['precision_recall_computed']


@pytest.mark.parametrize('change', ['prediction','wrong_year','outside','unknown_task','fake_observer','availability_string','independence_string'])
def test_invalid_truth_is_rejected(annotation_package,change):
    kwargs={}
    if change=='prediction':
        p=annotation_package/'trabalho/fontes_referencia.json';catalog=read_json(p)
        catalog['sources']['raw']['kind']='model_prediction';atomic_write_json(p,catalog)
    if change in {'availability_string','independence_string'}:
        p=annotation_package/'trabalho/fontes_referencia.json';catalog=read_json(p)
        catalog['sources']['raw']['available' if change=='availability_string' else 'independent_algorithm']='true'
        atomic_write_json(p,catalog)
    if change=='wrong_year':kwargs.update(source_year=2026,temporal_compatible='sim')
    if change=='outside':kwargs['geometry']=box(0,0,20,20)
    if change=='unknown_task':kwargs['task_id']='foreign'
    if change=='fake_observer':kwargs['observer']='LLM'
    add_annotation(annotation_package,**kwargs)
    assert not check_annotations(annotation_package)['ok']


def test_uncertain_completed_review_is_not_truth(annotation_package):
    add_annotation(annotation_package,label='incerto');sign_task(annotation_package,'w1_A')
    r=check_annotations(annotation_package)
    assert r['ok'] and r['reviewed_tasks']==1 and r['uncertain_annotations']==1
    assert r['eligible_vegetation_annotations']['treino']==0 and not r['supervised_training_allowed']


def test_review_completion_requires_full_context_and_signature(annotation_package):
    add_annotation(annotation_package,geometry=box(0,0,3,3));sign_task(annotation_package,'w1_A')
    r=check_annotations(annotation_package)
    assert not r['ok'] and any('todo contexto' in s for s in r['errors'])


def test_same_interpreter_cannot_double_annotate(annotation_package):
    add_annotation(annotation_package)
    add_annotation(annotation_package,annotation_id='a2',task_id='w1_B',reviewer_slot='B')
    r=check_annotations(annotation_package)
    assert not r['ok'] and any('distintos' in s for s in r['errors'])


def test_conflicting_labels_in_same_revision_are_rejected(annotation_package):
    add_annotation(annotation_package)
    add_annotation(annotation_package,annotation_id='a2',label='arbusto')
    r=check_annotations(annotation_package)
    assert not r['ok'] and any('conflitantes' in s for s in r['errors'])


def test_reference_real_materials_no_labels_and_mutable_cache(terrain_inputs,monkeypatch):
    raw=terrain_inputs.model_dump()
    raw['reference'].update(window_size_m=4.,main_windows=3,adversarial_windows=3,double_annotation_fraction=.25)
    c=Config.model_validate(raw)
    c.paths.project_root.joinpath('docs/guia_anotacao_etapa05.md').write_text('# Guia sintético de teste\n')
    # Mesmo XYZ com offsets diferentes entre duas fontes MDS.
    path=c.paths.data_root/'MDS_2020/MDS_3313-324_1000.laz'
    data=laspy.read(path);data.change_scaling(offsets=np.array([320100.,7390010.,0.]));data.write(path)
    records={case:terrain_run(c,case,requested_method='tin') for case in ['main','adversarial']}
    state=read_json(c.paths.state_file);state['etapas']['04']['status']='concluida'
    state['terreno_altura_piloto']={'principal':records['main'],'adverso':records['adversarial']};atomic_write_json(c.paths.state_file,state)
    originals=[fingerprint(p) for p in c.paths.data_root.rglob('*.laz')]
    result=reference_run(c)
    directory=Path(result['package']);report=read_json(Path(result['report']));plan=read_json(directory/'plano_referencia.json')
    assert report['windows']==6 and report['double_windows']==2 and report['tasks']==32
    assert report['human_labels_created']==0 and not report['annotation_assessment']['supervised_training_allowed']
    assert len({w['window_id'] for w in plan['windows']})==6
    admin=pd.read_csv(directory/'amostras_administracao.csv')
    regular=admin[admin.intended_use!='qa']
    assert (regular.measurement_area_m2>=c.reference.window_size_m**2*c.reference.minimum_regular_measurement_fraction).all()
    for purpose in PURPOSES: assert gpd.read_file(directory/'trabalho/anotacoes.gpkg',layer=purpose).empty
    source_index=read_json(directory/'fontes_lidar.json')['raw_mds']
    for window in plan['windows']:
        folder=directory/'janelas'/window['window_id']
        heights=pq.read_table(folder/'pontos_altura.parquet').to_pandas()
        points=laspy.read(folder/'mds_rgb_original.laz')
        assert len(heights)==len(points.points)
        if len(points.points):
            idx=int(points.source_tile_index[0]);entry=source_index[window['case']][idx]
            with laspy.open(entry['path']) as source:
                source.seek(int(points.source_point_index[0]));original=source.read_points(1)
                assert np.allclose([points.x[0],points.y[0],points.z[0]],[original.x[0],original.y[0],original.z[0]],atol=1e-9,rtol=0)
                assert points.classification[0]==original.classification[0] and points.red[0]==original.red[0]
        assert (folder/'ficha_cega.png').is_file()
    if (directory/'anotacao_cega.qgz').exists():
        with zipfile.ZipFile(directory/'anotacao_cega.qgz') as z:
            xml=z.read(next(n for n in z.namelist() if n.endswith('.qgs'))).decode()
        assert 'quadro_amostral' not in xml and 'dtm_tin' not in xml and 'pontos_altura' not in xml
        assert read_json(directory/'qgis_validacao.json')['human_inspection_performed'] is False
    assert [fingerprint(Path(p['path'])) for p in originals]==originals
    work=directory/'trabalho/tarefas.csv';edited=work.read_text()+'\n';work.write_text(edited)
    monkeypatch.setattr('sbsr_lidar.reference.clip_heights',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Não reprocessar cache')))
    again=reference_run(c)
    assert again['cache_hit'] and Path(again['package'])==directory and work.read_text()==edited
