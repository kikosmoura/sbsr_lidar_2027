"""Definição legada de CRS não é migração; um datum diferente deve ser rejeitado."""
from pathlib import Path
import sys
import geopandas as gpd
import pytest
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from diagnosticar_retomada_etapa16 import horizontal_crs


@pytest.mark.parametrize('name', ['corredor_verde/corredor_verde.shp', 'quadricula_folha_mdt_mds_2020/quadricula_folha_mdt_mds_2020.shp'])
def test_legacy_TOWGS84_binding_preserves_native_SIRGAS_projection(name):
    checked = horizontal_crs(ROOT/'files'/name)
    assert checked['epsg'] == 31983
    assert checked['raw_wkt_is_bound']
    assert checked['native_horizontal_authority'] == ('EPSG', '31983')
    assert not checked['coordinate_transform_applied']


def test_same_UTM_zone_but_wrong_datum_is_rejected(tmp_path):
    path = tmp_path/'wrong_datum.shp'
    gpd.GeoDataFrame({'id': [1]}, geometry=[box(330000, 7400000, 330010, 7400010)], crs=32723).to_file(path)
    with pytest.raises(ValueError, match='CRS horizontal'):
        horizontal_crs(path)
