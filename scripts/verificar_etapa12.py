"""Auditoria dos produtos reais, separada do executor; somente leitura no HD."""
from pathlib import Path
import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio
import shapely
from scipy import ndimage

from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json


def verify(execution):
    result=read_json(execution);root=Path(result['products_root']);checks=[]
    def check(name,value,**details):
        checks.append({'check':name,'ok':bool(value),**details})
        if not value:raise ValueError(f'Etapa12: {name}: {details}')
    cases=result['case_results'];check('ten_frozen_corridors',len(cases)==10)
    table=gpd.read_parquet(root/'indicadores_multiescala.parquet')
    cohort=gpd.read_parquet(root/'coorte_selecionada.parquet')
    all50=gpd.read_parquet(root/'todas_unidades_50m.parquet')
    check('unique_unit_ids',not table.unit_id.duplicated().any())
    check('CRS',table.crs.to_epsg()==31983)
    expected_blocks={c['block_id'] for c in cases.values() if c['selected_units']>0}
    check('sample_roles',set(cohort.role)<={'development','evaluation'} and set(cohort.block_id)==expected_blocks)
    check('frozen_cohort_subset',set(cohort.unit_id)==set(all50.loc[all50.selected_primary_cohort,'unit_id']))
    check('cohort_eligible_no_imputation',cohort.eligible_A_plus_3D.all() and np.isfinite(cohort[['I1','I4','I6','I7']].to_numpy()).all())
    check('per_corridor_quota',cohort.groupby('corridor_id').size().max()<=15)
    sample=[]
    for cid,record in cases.items():
        base=Path(record['root']);seal=read_json(base/'complete.json')
        check(f'{cid}:artifact_hashes',all(fingerprint(Path(p['path']))==p for p in seal['outputs']),files=len(seal['outputs']))
        qc=read_json(base/'qc.json');v=read_json(Path(qc['internal_validation']['path']))
        check(f'{cid}:validation_hash',fingerprint(Path(qc['internal_validation']['path']))==qc['internal_validation'])
        check(f'{cid}:unique_MDS_ownership',v['duplicate_source_id_records']==0)
        check(f'{cid}:full_LAZ_decode',all(r['decoded_points']==r['declared_points'] for r in qc['sources']))
        check(f'{cid}:archive_CRC',all(r['archive_crc_checked'] for r in qc['sources']))
        with rasterio.open(base/'primary/labels.tif') as ds:labels=ds.read(1);transform=ds.transform
        with rasterio.open(base/'rasters_r1_f1/observation.tif') as ds:obs=ds.read(1);check(f'{cid}:aligned',ds.transform==transform)
        check(f'{cid}:NoData_not_absence',np.array_equal(labels==-1,obs!=1))
        check(f'{cid}:positive_labels_observed',np.all(obs[labels>0]==1))
        crowns=gpd.read_parquet(base/'primary/copas_estimadas.parquet');tops=gpd.read_parquet(base/'primary/topos_estimados.parquet')
        patches=gpd.read_parquet(base/'primary/manchas_conectadas.parquet')
        _,n_components=ndimage.label(labels>0,structure=np.ones((3,3),dtype='uint8'))
        check(f'{cid}:connected_components_recomputed',len(patches)==n_components)
        check(f'{cid}:crown_geometries',crowns.geometry.is_valid.all() and (crowns.geometry.area>0).all())
        check(f'{cid}:one_top_per_segment',not crowns.crown_id.duplicated().any() and set(crowns.crown_id)==set(tops.crown_id))
        check(f'{cid}:seed_inside_own_segment',all(g.covers(p) for g,p in zip(crowns.geometry,tops.geometry)))
        check(f'{cid}:source_apex_provenance',tops.apex_return_source_tile.notna().all() and tops.apex_return_source_point_index.notna().all())
        check(f'{cid}:unvalidated_not_truth',not crowns.tree_identity_validated.any() and not crowns.classification_validated.any())
        original=gpd.read_parquet(root/'selecao_corredores_congelada.parquet').set_index('corridor_id').loc[cid].geometry
        z=table.loc[table.corridor_id.eq(cid)]
        for scale,g in z.groupby('nominal_size_m'):
            union=shapely.union_all(g.geometry.to_numpy())
            check(f'{cid}:partition_{scale:g}',union.symmetric_difference(original).area<1e-4 and abs(g.geometry.area.sum()-original.area)<1e-4)
            check(f'{cid}:area_order_{scale:g}',((g.area_canopy_m2>=0)&(g.area_canopy_m2<=g.area_observed_m2+1e-4)&(g.area_observed_m2<=g.area_total_m2+1e-4)).all())
            observed=g.area_observed_m2.to_numpy();use=observed>0
            check(f'{cid}:I1_formula_{scale:g}',np.allclose(g.I1.to_numpy()[use],g.area_canopy_m2.to_numpy()[use]/observed[use]))
            check(f'{cid}:I4_is_patch_density_{scale:g}',np.allclose(g.I4.to_numpy()[use],g.n_patches.to_numpy()[use]*10000/observed[use]))
            check(f'{cid}:heights_not_filled_{scale:g}',g.loc[~g.height_support_sufficient,['I5','I6','I7']].isna().all().all())
            check(f'{cid}:areal_eligibility_consistent_{scale:g}',(g.eligible_area_observation==g.eligible_A).all())
            check(f'{cid}:H_support_{scale:g}',(g.loc[g.height_support_sufficient,'n_vegetation_records']>=50).all())
            check(f'{cid}:seed_count_conservation_{scale:g}',g.n_estimated_chm_seeds_owned.sum()==record['primary']['estimated_seeds_inside_P'])
        check(f'{cid}:patch_vs_crown_union',shapely.union_all(crowns.geometry.to_numpy()).symmetric_difference(shapely.union_all(patches.geometry.to_numpy())).area<1e-4)
        counts={int(label):0 for label in tops.label};minimum={int(label):np.inf for label in tops.label};maximum={int(label):-np.inf for label in tops.label}
        max_id={};normalized=Path(record['normalized_source']);height_error=0.;n=0
        for batch in pq.ParquetFile(normalized).iter_batches(batch_size=65536):
            f=batch.to_pandas();valid=f.terrain_status.eq(0).to_numpy()&np.isfinite(f.h.to_numpy())
            if valid.any():height_error=max(height_error,float(np.max(np.abs((f.z_absolute-f.terrain_z-f.h).to_numpy()[valid]))))
            col=np.floor((f.x.to_numpy()-transform.c)/transform.a).astype(int);row=np.floor((transform.f-f.y.to_numpy())/-transform.e).astype(int)
            inside=(col>=0)&(row>=0)&(row<labels.shape[0])&(col<labels.shape[1]);idx=np.flatnonzero(inside)
            lab=np.zeros(len(f),dtype=int);lab[idx]=labels[row[idx],col[idx]]
            use=(lab>0)&valid&((f.qc_flags.to_numpy()&2)==0)&f.classification.isin([3,4,5]).to_numpy()&(f.h.to_numpy()>3)
            ff=f.loc[use].copy();ff['label']=lab[use]
            for label,group in ff.groupby('label'):
                counts[int(label)]+=len(group)
                cand=group.sort_values(['z_absolute','source_tile','source_point_index'],ascending=[False,True,True]).iloc[0]
                identity=(-float(cand.z_absolute),cand.source_tile,int(cand.source_point_index))
                if int(label) not in max_id or identity<max_id[int(label)]:max_id[int(label)]=identity
            n+=len(f)
        check(f'{cid}:continuous_H_formula',height_error<1e-9,records=n,max_error=height_error)
        check(f'{cid}:apex_is_maximum_absolute_Z',all(max_id[int(r.label)]==(-float(r.apex_return_z_absolute),r.apex_return_source_tile,int(r.apex_return_source_point_index)) for r in tops.itertuples()))
        check(f'{cid}:apex_return_counts',all(counts[int(r.label)]==r.candidate_returns_in_segment for r in tops.itertuples()))
        selected=cohort.loc[cohort.corridor_id.eq(cid)]
        sample.append({'corridor_id':cid,'role':record['role'],'block_id':record['block_id'],'selected_units_50m':len(selected),
            'eligible_units_50m':record['eligible_units_50m'],'P_m2':original.area,'observed_m2':record['primary']['observed_area_m2'],
            'observed_fraction':record['primary']['observed_area_m2']/original.area,'segments_intersecting_P':record['primary']['estimated_segments_intersecting_P'],
            'seeds_inside_P':record['primary']['estimated_seeds_inside_P'],'connected_patches_intersecting_P':record['primary']['patches']['components_intersecting_measurement']})
    sens=pd.read_parquet(root/'sensibilidade_cenarios.parquet')
    check('110_sensitivity_pairs',len(sens)==110 and len(sens.groupby('corridor_id'))==10)
    check('same_support_area',((sens.common_observed_m2<=sens.observed_primary_m2+1e-4)&(sens.common_observed_m2<=sens.observed_scenario_m2+1e-4)).all())
    controls=pd.read_parquet(root/'controles.parquet');check('no_invented_inference',not controls.p_values_computed.any() and not controls.surrogate_permutations_performed.any())
    scores=pd.read_parquet(root/'escores_rankings.parquet')
    for (case,scope),g in scores.groupby(['case','scope']):
        a=g.loc[g.variant_id.eq('A')].set_index('unit_id')
        for variant,h in g.groupby('variant_id'):
            check(f'same_cohort:{case}:{scope}:{variant}',set(h.unit_id)==set(a.index))
            if variant.endswith('w0'):check(f'zero_weight:{case}:{scope}:{variant}',np.allclose(a.score_for_ranking,h.set_index('unit_id').loc[a.index].score_for_ranking))
    resources=read_json(root/'resources.json');check('RAM_budget',not resources['exceeded'],peak_rss_gib=resources['peak_rss_gib'])
    for path,sha in [('baixar_lidar_geosampa.py','a4f566f39cc06ab931617720c1a8a4fa8391f40b85c4fd04ae69d1e8972df3ca'),
                     ('tests/test_baixar_lidar_geosampa.py','28b216ac967c08ce55fbc3b88bf9e9eb7dad5ea54f3ffc7f83930b8b7848aed0'),
                     ('requirements.txt','fd72dd0bc564965c8e021b2b0f38452c00bd290e47fae16df7bc28ce60aedc92')]:
        check(f'protected:{path}',fingerprint(Path(path))['sha256']==sha)
    return {'ok':all(r['ok'] for r in checks),'checks':checks,'sample':sample,'execution':fingerprint(execution),
        'accuracy_external_evaluated':False,'independent_groups_certified':None,'resources':{k:v for k,v in resources.items() if k!='samples'}}


if __name__=='__main__':
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path('relatorios/etapa12/execucao.json')
    result=verify(path);atomic_write_json(Path('relatorios/etapa12/verificacao_independente.json'),result)
    print(json.dumps({'ok':result['ok'],'checks':len(result['checks']),'sample':result['sample']},ensure_ascii=False,indent=2))
