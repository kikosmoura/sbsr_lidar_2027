"""Verificar máscaras reais, fonte por ponto, domínio comum e recorte das manchas."""
import argparse
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pyarrow.parquet as pq
import rasterio

from sbsr_lidar.annotations import check_annotations
from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path('configs/terreno_congelado_etapa04.yaml'))
    parser.add_argument('--reports',type=Path,default=Path('relatorios/etapa06'))
    args=parser.parse_args();config=load_config(args.config)
    state=read_json(config.paths.state_file);checks={};summary={}
    assessment=check_annotations(Path(state['referencia_anotacao']['package']))
    checks['reference_still_pending_no_fake_labels']=assessment['ok'] and assessment['completed_annotations']==0 and not assessment['supervised_training_allowed']
    for case in ['main','adversarial']:
        e=read_json(args.reports/f'execucao_{case}.json');r=read_json(Path(e['report']))
        manifest=RunManifest.model_validate(read_json(Path(e['manifest'])))
        checks[f'{case}:manifest']=manifest.status=='completed' and manifest.stage=='06' and manifest.code_sha256==source_digest()
        checks[f'{case}:inputs_preserved']=all(fingerprint(Path(p.path))==p.model_dump() for p in manifest.inputs)
        products={Path(p).name:Path(p) for p in r['products']};domain=build_domain(config,case)
        with rasterio.open(products['observabilidade.tif']) as ds:
            observation=ds.read(1);transform=ds.transform;shape=ds.shape;crs=ds.crs
        valid=observation==1;context=observation!=255
        candidate={h:np.zeros(shape,dtype=np.uint32) for h in r['heights_m']}
        source=next(Path(p.path) for p in manifest.inputs if Path(p.path).name=='alturas_pontos.parquet')
        for batch in pq.ParquetFile(source).iter_batches(batch_size=65536):
            b=batch.to_pandas()
            col=np.floor((b.x.to_numpy()-transform.c)/transform.a).astype(int)
            row=np.floor((transform.f-b.y.to_numpy())/(-transform.e)).astype(int)
            inside=(row>=0)&(row<shape[0])&(col>=0)&(col<shape[1])
            flat=np.clip(row*shape[1]+col,0,np.prod(shape)-1)
            inside &= context.ravel()[flat]
            accepted=inside&b.classification.isin([3,4,5]).to_numpy()&b.h.notna().to_numpy()&(
                (b.qc_flags.to_numpy()&2)==0)&b.terrain_status.eq(0).to_numpy()
            for h in r['heights_m']:
                use=accepted&(b.h.to_numpy()>=h)
                candidate[h].ravel()[:]+=np.bincount(flat[use],minlength=np.prod(shape)).astype(np.uint32)
        aligned=True;source_counts=True;domains_common=True;baseline_exact=True;refinement=True;polygons_valid=True;exact_clip=True;areas=True
        baseline_masks=[];baseline_areas=[]
        polygons=products['mascaras_manchas.gpkg']
        observed=gpd.read_file(polygons,layer='suporte_observado')
        observed_area=float(observed.geometry.area.sum())
        areas &= np.isclose(observed_area,r['observation']['exact_observed_area_in_measurement_m2'],atol=1e-6,rtol=0)
        for path in products.values():
            if path.suffix=='.tif':
                with rasterio.open(path) as ds:
                    aligned &= ds.shape==shape and ds.transform==transform and ds.crs==crs and ds.tags().get('stage')=='06'
        for height in r['heights_m']:
            label=f'{height:g}'
            with rasterio.open(products[f'contagem_candidatos_h{label}.tif']) as ds:
                source_counts &= np.array_equal(ds.read(1)[context],candidate[height][context])
            with rasterio.open(products[f'copa_baseline_h{label}_contexto.tif']) as ds:base=ds.read(1)
            with rasterio.open(products[f'copa_refinada_h{label}_contexto.tif']) as ds:refined=ds.read(1)
            domains_common &= np.array_equal(base!=255,valid) and np.array_equal(refined!=255,valid)
            baseline_exact &= np.array_equal(base==1,valid&(candidate[height]>=config.vegetation.minimum_points_per_cell))
            baseline_masks.append(base==1)
            refinement &= not np.any((refined==1)&(base!=1)) and set(np.unique(refined)).issubset({0,1,2,255})
            with rasterio.open(products[f'incerteza_h{label}.tif']) as ds:flags=ds.read(1)
            refinement &= np.all((flags[refined==2]&(1|2|4|8|16))!=0)
            for version in ['baseline','refinada']:
                key=f'{version}_h{label}'
                full=gpd.read_file(polygons,layer=key+'_contexto');core=gpd.read_file(polygons,layer=key+'_medicao')
                polygons_valid &= bool(full.geometry.is_valid.all() and core.geometry.is_valid.all())
                areas &= np.isclose(core.geometry.area.sum(),r['scenarios'][key]['candidate_area_measurement_exact_m2'],atol=1e-6,rtol=0)
                areas &= float(core.geometry.area.sum())<=observed_area+1e-6
                full_lookup=dict(zip(full.patch_id,full.geometry))
                for row in core.itertuples():
                    expected=full_lookup[row.patch_id].intersection(domain.measurement)
                    exact_clip &= row.geometry.symmetric_difference(expected).area<1e-6
                    exact_clip &= row.geometry.difference(domain.measurement).area<1e-6
                if version=='baseline':baseline_areas.append(float(core.geometry.area.sum()))
        checks[f'{case}:aligned_grid']=bool(aligned)
        checks[f'{case}:counts_from_original_H_points']=bool(source_counts)
        checks[f'{case}:baseline_exact_rule']=bool(baseline_exact)
        checks[f'{case}:identical_observation_domain']=bool(domains_common)
        checks[f'{case}:refined_unknown_not_promoted']=bool(refinement)
        checks[f'{case}:valid_patch_geometries']=bool(polygons_valid)
        checks[f'{case}:exact_measurement_intersections']=bool(exact_clip)
        checks[f'{case}:area_preserved_and_within_observed']=bool(areas)
        checks[f'{case}:height_monotonicity']=bool(np.all(np.diff(baseline_areas)<=1e-6) and all(not np.any(b&~a) for a,b in zip(baseline_masks,baseline_masks[1:])))
        quality=r['quality']
        checks[f'{case}:no_fake_accuracy_or_training']=not quality['supervised_classifier_trained'] and all(quality[k] is None for k in ['confusion_matrix','precision','recall','F1','IoU'])
        checks[f'{case}:auxiliary_not_spectral_classifier']=r['spectral']['used_as_classification_threshold'] is False
        checks[f'{case}:analysis_provisional']=r['analysis_version']=='baseline_h3' and r['selection']['provisional'] and not r['selection']['quality_measured']
        qa=gpd.read_file(polygons,layer='celulas_qa')
        checks[f'{case}:qa_pending']=bool(qa.manual_status.eq('pendente').all())
        cache=read_json(args.reports/f'cache_{case}.json')
        checks[f'{case}:cache']=cache['cache_hit'] and cache['report']==e['report']
        summary[case]={'run_id':e['run_id'],'analysis_version':r['analysis_version'],'observation':r['observation'],
            'scenarios':r['scenarios'],'QA':r['QA'],'elapsed_seconds':r['elapsed_seconds'],'peak_process_rss_mib':r['peak_process_rss_mib']}
    tests={'scientific_passed':int(re.search(r'(\d+) passed',(args.reports/'testes_cientificos.log').read_text()).group(1)),
           'downloader_passed':int(re.search(r'(\d+) passed',(args.reports/'downloader_regressao.log').read_text()).group(1))}
    result={'ok':all(checks.values()),'checks':{k:bool(v) for k,v in checks.items()},'summary':summary,'tests':tests}
    atomic_write_json(args.reports/'verificacoes.json',result)
    print(f'{sum(checks.values())}/{len(checks)} verificações dos produtos reais passaram.')
    if not result['ok']:raise SystemExit(1)


if __name__=='__main__':main()
