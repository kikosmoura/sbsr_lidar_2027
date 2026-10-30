"""Audita pacote de referência e recortes reais; não cria nem conclui rótulos."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio

from sbsr_lidar.annotations import PURPOSES,check_annotations
from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain
from sbsr_lidar.environment import source_digest
from sbsr_lidar.reference_sampling import corridor_groups
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import read_json,atomic_write_json,fingerprint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path('configs/terreno_congelado_etapa04.yaml'))
    parser.add_argument('--reports',type=Path,default=Path('relatorios/etapa05'))
    args=parser.parse_args();config=load_config(args.config)
    execution=read_json(args.reports/'execucao.json')
    report=read_json(Path(execution['report']));package=Path(execution['package'])
    manifest=RunManifest.model_validate(read_json(Path(execution['manifest'])))
    checks={'manifest':manifest.status=='completed' and manifest.stage=='05' and manifest.code_sha256==source_digest()}
    checks['inputs_unchanged']=all(fingerprint(Path(p.path))==p.model_dump() for p in manifest.inputs)
    plan=read_json(package/'plano_referencia.json')
    admin=pd.read_csv(package/'amostras_administracao.csv')
    public=gpd.read_file(package/'amostras.gpkg',layer='janelas')
    contexts=gpd.read_file(package/'amostras.gpkg',layer='contextos').set_index('window_id')
    checks['windows_20_unique']=len(plan['windows'])==20==len(public) and public.window_id.nunique()==20
    checks['quotas']=admin.groupby('case').size().to_dict()=={'main':12,'adversarial':8}
    regular=admin.loc[admin.intended_use!='qa']
    checks['regular_windows_have_measurement_support']=bool(
        (regular.context_area_m2>=config.reference.window_size_m**2*config.reference.minimum_regular_context_fraction).all() and
        (regular.measurement_area_m2>=config.reference.window_size_m**2*config.reference.minimum_regular_measurement_fraction).all())
    checks['no_probability_fabricated']=admin.inclusion_probability.isna().all() and all(not s['inclusion_probabilities_known'] for s in report['sampling'].values())
    checks['all_available_proxies_covered']=all(not s['not_covered_proxy_targets'] for s in report['sampling'].values())
    groups,_=corridor_groups(config)
    checks['frozen_groups_match_inputs']=groups==plan['groups']
    folds={}
    for r in groups:folds.setdefault(r['group_id'],set()).add(r['fold'])
    checks['no_group_split']=all(len(values)==1 for values in folds.values())
    checks['double_annotation']=len(plan['double_windows'])==5 and len(plan['tasks'])==100
    public_columns=set(public.columns)
    checks['blind_public_table']=not any(col.startswith('class_') or col in {'selection_proxies','fold','intended_use'} for col in public_columns)
    assessment=check_annotations(package)
    checks['all_human_labels_pending']=assessment['ok'] and assessment['completed_annotations']==0 and assessment['pending_tasks']==100
    checks['no_fake_metrics_or_training']=not assessment['precision_recall_computed'] and not assessment['supervised_training_allowed'] and assessment['independent_height_references']==0 and assessment['independent_priority_references']==0
    checks['annotation_layers_empty']=all(gpd.read_file(package/'trabalho/anotacoes.gpkg',layer=purpose).empty for purpose in PURPOSES)
    domain={case:build_domain(config,case) for case in ['main','adversarial']}
    provenance=read_json(package/'fontes_lidar.json')
    aggregate={'raw_and_height_counts':True,'original_source_records':True,'RGB_occupancy':True,'geometry':True,
               'profiles_real':True,'all_materials_present':True}
    total=0;source_samples=0
    with ExitStack() as stack:
        readers={}
        for case,entries in provenance['raw_mds'].items():
            for entry in entries:
                readers[(case,entry['source_tile_index'])]=stack.enter_context(laspy.open(entry['path']))
        for window in plan['windows']:
            folder=package/'janelas'/window['window_id'];bounds=window['bounds'];left,bottom,right,top=bounds
            effective=__import__('shapely.geometry',fromlist=['box']).box(*bounds).intersection(domain[window['case']].context)
            aggregate['geometry'] &= contexts.loc[window['window_id']].geometry.equals(effective)
            points=laspy.read(folder/'mds_rgb_original.laz')
            heights=pq.read_table(folder/'pontos_altura.parquet').to_pandas()
            expected=int(admin.loc[admin.window_id==window['window_id'],'points'].iloc[0])
            aggregate['raw_and_height_counts'] &= len(points.points)==len(heights)==expected
            aggregate['raw_and_height_counts'] &= bool(np.array_equal(points.source_point_index,heights.source_point_index.to_numpy()))
            for name,values in [('x',points.x),('y',points.y),('z_absolute',points.z)]:
                aggregate['raw_and_height_counts'] &= bool(np.allclose(values,heights[name],rtol=0,atol=1e-8))
            aggregate['raw_and_height_counts'] &= np.array_equal(points.classification,heights.classification.to_numpy())
            total+=len(heights)
            for index in sorted(set([0,len(points.points)//2,len(points.points)-1])) if len(points.points) else []:
                reader=readers[(window['case'],int(points.source_tile_index[index]))]
                reader.seek(int(points.source_point_index[index]));original=reader.read_points(1)
                aggregate['original_source_records'] &= bool(np.allclose([points.x[index],points.y[index],points.z[index]],
                    [original.x[0],original.y[0],original.z[0]],rtol=0,atol=1e-8))
                for name in ['classification','red','green','blue','nir','return_number','number_of_returns']:
                    aggregate['original_source_records'] &= points[name][index]==original[name][0]
                source_samples+=1
            with rasterio.open(folder/'rgb_pontos_lidar.tif') as image:
                values=image.read();res=image.res[0];n=image.height
                cols=np.floor((np.asarray(points.x)-left)/res).astype(int)
                rows=n-1-np.floor((np.asarray(points.y)-bottom)/res).astype(int)
                occupied=np.zeros(image.shape,dtype=bool);occupied[rows,cols]=True
                aggregate['RGB_occupancy'] &= bool(np.array_equal(occupied,values[3]>0))
                aggregate['RGB_occupancy'] &= image.tags().get('source')=='RGB_of_topmost_MDS_point_per_cell_not_orthophoto'
            profiles=pd.read_csv(folder/'perfis_pontos.csv')
            half=config.reference.profile_half_width_m
            nprofiles=int(np.sum(np.abs(heights.y-(bottom+top)/2)<=half)+np.sum(np.abs(heights.x-(left+right)/2)<=half))
            aggregate['profiles_real'] &= len(profiles)==nprofiles
            aggregate['all_materials_present'] &= all((folder/name).is_file() for name in ['ficha_cega.png','perfis_pontos.csv','rgb_pontos_lidar.tif','mds_rgb_original.laz','pontos_altura.parquet'])
    checks.update({key:bool(value) for key,value in aggregate.items()})
    alert_counts={}
    for case,source in provenance['terrain_sources'].items():
        r=read_json(Path(source['report']));alert_counts[case]=int(r['heights']['flags']['h_below_negative_warning'])
    checks['all_negative_alerts_covered']=admin.groupby('case').negative_alert_points.sum().astype(int).to_dict()==alert_counts
    qgis=read_json(package/'qgis_validacao.json')
    checks['qgis_projects_valid']=all(item['valid_layers'] for item in qgis['projects']) and len(qgis['projects'])==2 and not qgis['human_inspection_performed']
    with zipfile.ZipFile(package/'anotacao_cega.qgz') as archive:
        tree=ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.qgs'))))
    datasources=[node.text or '' for node in tree.iter('datasource')]
    checks['blind_project_sources']=not any(any(token in value for token in ['quadro_amostral','dtm_','validade_','pontos_altura']) for value in datasources)
    cache=read_json(args.reports/'cache.json')
    checks['cache_same_package']=cache['cache_hit'] and cache['package']==str(package)
    checks['no_external_reference_invented']=report['external_source_inventory']['verified_external_2020_images']==[]
    tests={'scientific_passed':int(re.search(r'(\d+) passed',(args.reports/'testes_cientificos.log').read_text()).group(1)),
           'downloader_passed':int(re.search(r'(\d+) passed',(args.reports/'downloader_regressao.log').read_text()).group(1))}
    result={'ok':all(checks.values()),'checks':{k:bool(v) for k,v in checks.items()},'run_id':execution['run_id'],
        'package':str(package),'windows':20,'points_in_crops':total,'source_records_verified':source_samples,
        'negative_alerts_covered':alert_counts,'annotation_assessment':assessment,'tests':tests}
    atomic_write_json(args.reports/'verificacoes.json',result)
    print(f'{sum(checks.values())}/{len(checks)} verificações passaram; {total} registros recortados, {source_samples} pontos conferidos nos originais.')
    if not result['ok']:raise SystemExit(1)


if __name__=='__main__':main()
