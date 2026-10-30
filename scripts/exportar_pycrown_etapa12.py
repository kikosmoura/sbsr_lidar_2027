"""GeoPackage consolidado para revisão no QGIS; preserva IDs e contexto."""
from pathlib import Path
import geopandas as gpd
import pandas as pd
import shapely
from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json


def main():
    result=read_json(Path('relatorios/etapa12/execucao.json'));root=Path(result['products_root'])
    selection=gpd.read_parquet(root/'selecao_corredores_congelada.parquet').set_index('corridor_id')
    layers={k:[] for k in ['copas_contexto','copas_no_corredor','sementes_chm','apices_retornos_Z']}
    for cid,record in result['case_results'].items():
        base=Path(record['root']);p=selection.loc[cid].geometry
        crowns=gpd.read_parquet(base/'primary/copas_estimadas.parquet');tops=gpd.read_parquet(base/'primary/topos_estimados.parquet')
        crowns['role']=record['role'];tops['role']=record['role']
        measured=crowns.copy();measured.geometry=measured.geometry.intersection(p)
        measured=measured.loc[(~measured.geometry.is_empty)&(measured.geometry.area>0)].copy()
        # GeometryCollections may retain zero-area tangencies after clipping.
        from sbsr_lidar.spatial_units import polygonal
        measured.geometry=measured.geometry.map(polygonal)
        apices=tops.loc[tops.apex_return_x.notna()&tops.apex_return_y.notna()].copy()
        apices.geometry=gpd.points_from_xy(apices.apex_return_x,apices.apex_return_y,z=apices.apex_return_z_absolute,crs=tops.crs)
        apices['apex_return_inside_P']=apices.intersects(p)
        for name,frame in [('copas_contexto',crowns),('copas_no_corredor',measured),('sementes_chm',tops),('apices_retornos_Z',apices)]:
            layers[name].append(frame)
    package=root/'produtos_pycrown.gpkg';counts={}
    for name,frames in layers.items():
        frame=gpd.GeoDataFrame(pd.concat(frames,ignore_index=True),geometry='geometry',crs=31983)
        if not frame.geometry.is_valid.all():raise ValueError(f'Geometria inválida em {name}')
        frame.to_file(package,layer=name,driver='GPKG');counts[name]=len(frame)
    for name,file in [('unidades_50m','todas_unidades_50m.parquet'),('amostra_50m','coorte_selecionada.parquet')]:
        frame=gpd.read_parquet(root/file);frame.to_file(package,layer=name,driver='GPKG');counts[name]=len(frame)
    inventory=gpd.list_layers(package)
    if set(inventory.name)!=set(counts):raise ValueError('Camadas consolidadas não conferem')
    reopened={name:len(gpd.read_file(package,layer=name)) for name in counts}
    if reopened!=counts:raise ValueError('Contagens GeoPackage não conferem após reabrir')
    atomic_write_json(Path('relatorios/etapa12/exportacao_qgis.json'),{'package':fingerprint(package),'layers':counts,
        'reopened_counts_verified':True,'accuracy_external_evaluated':False,'segment_counts_are_not_verified_tree_counts':True})
    print(package);print(counts)


if __name__=='__main__':main()
