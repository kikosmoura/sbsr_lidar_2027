"""Confere produtos reais, fórmula de H e amostras ligadas aos LAZ originais."""
import argparse
import re
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pyarrow.parquet as pq
import rasterio

from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain
from sbsr_lidar.environment import source_digest
from sbsr_lidar.input_qc import grid_layout
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import read_json,atomic_write_json,fingerprint
from sbsr_lidar.terrain_surface import Surface


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path('configs/piloto.yaml'))
    parser.add_argument('--reports',type=Path,default=Path('relatorios/etapa04'))
    args=parser.parse_args()
    c=load_config(args.config)
    checks={};summary={};sample_records=[]
    for case in ['main','adversarial']:
        e=read_json(args.reports/f'execucao_{case}.json')
        r=read_json(Path(e['report']))
        m=RunManifest.model_validate(read_json(Path(e['manifest'])))
        checks[f'{case}:manifest']=m.status=='completed' and m.stage=='04' and m.code_sha256==source_digest()
        checks[f'{case}:inputs_preserved']=all(fingerprint(Path(p.path))==p.model_dump() for p in m.inputs)
        products={Path(p).name:Path(p) for p in r['products']}
        d=build_domain(c,case);g=grid_layout(c,d)
        aoi=gpd.read_file(products['dominios.gpkg'],layer='medicao')
        checks[f'{case}:geometry']=aoi.geometry.iloc[0].equals_exact(d.measurement,0)
        aligned=True;support=True;limits=True
        for radius in r['radii_m']:
            for method in ['tin','idw']:
                key=f'{method}_r{radius:g}'
                with rasterio.open(products[f'dtm_{key}_contexto.tif']) as ds:
                    values=ds.read(1,masked=True)
                    aligned &= ds.transform==g.transform and ds.shape==g.shape and ds.crs.to_epsg()==c.grid.epsg
                    outside=~g.context_mask
                    support &= bool(np.all(values.mask[outside]))
                    count=int(np.sum(g.measurement_mask & ~values.mask))
                    support &= count==r['support'][key]['medicao']['valid_cells']
                    with rasterio.open(products[f'validade_{key}.tif']) as valid:
                        status=valid.read(1)
                        support &= np.array_equal((status==0)&g.context_mask,~values.mask)
                    with rasterio.open(products[f'dtm_{key}_medicao.tif']) as core:
                        arr=core.read(1,masked=True)
                        support &= bool(np.all(arr.mask[~g.measurement_mask]))
                        support &= np.array_equal(arr.data[~arr.mask],values.data[~arr.mask])
        checks[f'{case}:aligned']=bool(aligned)
        checks[f'{case}:support_nodata']=bool(support)
        # Fórmula completa em todos os registros preservados, sem carregar a nuvem inteira.
        n=nv=nmv=0;formula=True;sample=[];seen=set()
        for batch in pq.ParquetFile(products['alturas_pontos.parquet']).iter_batches(batch_size=65536):
            b=batch.to_pandas()
            valid=b.h.notna().to_numpy()
            formula &= np.allclose((b.z_absolute-b.terrain_z).to_numpy()[valid],b.h.to_numpy()[valid],atol=1e-12,rtol=0)
            formula &= bool(b.loc[~valid,'h'].isna().all() and b.loc[valid,'terrain_status'].eq(0).all())
            n+=len(b);nv+=int(valid.sum());nmv+=int(np.sum(valid & b.in_measurement.to_numpy()))
            for (tile,cls),group in b.groupby(['source_tile','classification']):
                if (tile,cls) not in seen:
                    seen.add((tile,cls));sample.append(group.iloc[0].to_dict())
        checks[f'{case}:H_formula']=bool(formula)
        checks[f'{case}:point_counts']=n==r['heights']['counts']['context_points'] and nv==r['heights']['counts']['context_valid_h'] and nmv==r['heights']['counts']['measurement_valid_h']
        raw_preserved=True
        for item in sample:
            source=next(h['path'] for h in r['heights']['headers'] if h['tile']==item['source_tile'])
            with laspy.open(source) as reader:
                reader.seek(int(item['source_point_index']))
                p=reader.read_points(1)
                raw_preserved &= bool(np.allclose([p.x[0],p.y[0],p.z[0]],[item['x'],item['y'],item['z_absolute']],atol=1e-10,rtol=0))
                raw_preserved &= int(p.classification[0])==int(item['classification'])
                raw_preserved &= int(p.user_data[0])==int(item['user_data'])
        checks[f'{case}:original_Z_class_sample']=bool(raw_preserved)
        sample_records.append({'case':case,'records_checked':len(sample),'scheme':'first_preserved_record_per_source_tile_and_class'})
        # Reconstrói a superfície a partir do produto serializado e recalcula H da amostra.
        vertices=pq.read_table(products['vertices_terreno.parquet']).to_pandas().to_numpy()
        model=Surface(vertices,c.terrain)
        coordinates=np.array([[s['x'],s['y']] for s in sample])
        q=model.query(coordinates,r['primary_radius_m'])
        expected=np.array([s['z_absolute'] for s in sample])-q[r['selected_method']]
        saved=np.array([s['h'] for s in sample])
        checks[f'{case}:H_reproducible_from_vertices']=bool(np.allclose(expected,saved,equal_nan=True,rtol=0,atol=1e-9))
        cache=read_json(args.reports/f'cache_{case}.json')
        checks[f'{case}:cache']=cache['cache_hit'] and cache['report']==e['report']
        summary[case]={'run_id':e['run_id'],'method':r['selected_method'],'support':r['support'],
            'validation':r['validation'],'counts':r['heights']['counts'],'edge':r['edge_comparison'],
            'elapsed_seconds':r['elapsed_seconds'],'peak_process_rss_mib':r['peak_process_rss_mib']}
    checks['same_method_both_cases']=summary['main']['method']==summary['adversarial']['method']
    scientific=(args.reports/'testes_cientificos.log').read_text()
    downloader=(args.reports/'downloader_regressao.log').read_text()
    tests={'scientific_passed':int(re.search(r'(\d+) passed',scientific).group(1)),
           'downloader_passed':int(re.search(r'(\d+) passed',downloader).group(1))}
    result={'ok':all(checks.values()),'checks':checks,'summary':summary,'raw_sample_verification':sample_records,'tests':tests}
    atomic_write_json(args.reports/'verificacoes.json',result)
    print(f'{sum(checks.values())}/{len(checks)} verificações de produtos reais passaram.')
    if not result['ok']: raise SystemExit(1)


if __name__=='__main__': main()
