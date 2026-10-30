import stat
import zipfile
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pytest
import rasterio
import yaml
from pyproj import CRS
from shapely.geometry import box

from sbsr_lidar.acquisition import ensure_inputs, extract_laz, validate_endpoint
from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain, cloud_path, input_plan
from sbsr_lidar.input_qc import audit_cloud, grid_layout
from sbsr_lidar.preparation import plan_inputs, prepare_inputs
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json


@pytest.fixture
def pilot_inputs(config_file, monkeypatch):
    raw = yaml.safe_load(config_file.read_text())
    raw['pilot'].update(core_tiles=['3313-333'], context_tiles=['3313-324'],
                        sensitivity_tiles=[], halo_m=1.0)
    raw['resources']['chunk_points'] = 2
    config_file.write_text(yaml.safe_dump(raw))
    config = load_config(config_file)
    monkeypatch.setattr(Path, 'is_mount', lambda p: p == config.paths.mount_root)
    config.paths.corridors.parent.mkdir()
    gpd.GeoDataFrame({'cd_identi0': [config.pilot.corridor_id, config.pilot.adversarial_corridor]},
        geometry=[box(330001,7390001,330004,7390004), box(330019,7390001,330023,7390004)],
        crs=config.grid.epsg).to_file(config.paths.corridors)
    codes = ['3313-333','3313-324','3312-431']
    tiles = [box(330000,7390000,330004.5,7390006), box(330004.5,7390000,330010,7390006),
             box(330020,7390000,330026,7390006)]
    gpd.GeoDataFrame({'cd_quadric': codes}, geometry=tiles, crs=config.grid.epsg).to_file(config.paths.grid)
    for code, tile in zip(codes, tiles):
        for product in ['MDT','MDS']:
            path = config.paths.data_root / f'{product}_2020' / f'{product}_{code}_1000.laz'
            path.parent.mkdir(exist_ok=True)
            header = laspy.LasHeader(version='1.4' if product == 'MDS' else '1.2', point_format=8 if product == 'MDS' else 1)
            header.add_crs(CRS.from_epsg(config.grid.epsg))
            header.offsets = np.array([330000.,7390000.,0.])
            header.scales = np.array([0.001]*3)
            data = laspy.LasData(header)
            dx = tile.bounds[0]-330000
            xs = np.array([1.5,1.6,2.5,3.5,2.6,3.6])+330000+dx
            if code == '3313-324':
                xs = np.full(6,330004.75)
            data.x = xs
            data.y = np.full(6,7390002.5)
            data.z = np.arange(6.)
            data.classification = np.array([3,8,7,5,3,3],dtype=np.uint8)
            data.return_number = np.array([1,1,1,1,0,2],dtype=np.uint8)
            data.number_of_returns = np.ones(6,dtype=np.uint8)
            data.withheld = np.array([0,0,0,1,0,0],dtype=np.uint8)
            data.write(path)
    config.paths.protocol_file.parent.mkdir(exist_ok=True)
    config.paths.protocol_file.write_text('Protocolo sintético\n')
    atomic_write_json(config.paths.state_file, {'schema_version':'0.1.0','etapa_atual':'02','status':'etapa_02_concluida',
        'etapas': {'03': {'nome':'insumos','status':'nao_iniciada','artefatos':[]}},
        'piloto_executado':False,'pipeline_cientifico_implementado':False})
    return config


def test_domain_exact_official_buffer_and_readonly_plan(pilot_inputs):
    config = pilot_inputs
    original = fingerprint(config.paths.corridors)
    domain = build_domain(config, 'main')
    assert domain.measurement.equals_exact(domain.official, 0)
    assert domain.context.equals_exact(domain.official.buffer(1), 0)
    assert domain.metadata['tiles'] == ['3313-324','3313-333']
    assert not domain.metadata['context_clipped_to_tile']
    assert not any(x['needs_download'] for x in plan_inputs(config, 'main')['files'])
    assert not config.paths.output_root.exists() and not config.paths.runs_root.exists()
    assert fingerprint(config.paths.corridors) == original


def test_adversarial_is_separate_and_explicitly_clipped(pilot_inputs):
    domain = build_domain(pilot_inputs, 'adversarial')
    tile = domain.nominal_tiles.geometry.iloc[0]
    assert domain.measurement.equals(domain.official.intersection(tile))
    assert domain.metadata['context_clipped_to_tile']
    assert domain.metadata['requested_context_omitted_m2'] > 0
    assert domain.context.difference(tile).area == 0
    assert domain.metadata['tiles'] == ['3312-431']


def test_changed_tile_configuration_rejected(pilot_inputs):
    raw = pilot_inputs.model_dump()
    raw['pilot']['context_tiles'] = []
    with pytest.raises(ValueError, match='Plano derivado'):
        build_domain(type(pilot_inputs).model_validate(raw), 'main')


def test_missing_downloads_bounded_and_requires_flag(pilot_inputs):
    config = pilot_inputs
    for product in ['MDT','MDS']:
        cloud_path(config, product, '3313-324').unlink()
    plan = input_plan(config, build_domain(config,'main'))
    assert sum(x['needs_download'] for x in plan) == 2
    with pytest.raises(ValueError, match='download-missing'):
        ensure_inputs(config,plan,download_missing=False)
    cloud_path(config,'MDT','3313-333').unlink()
    with pytest.raises(ValueError, match='limite'):
        input_plan(config, build_domain(config,'main'))


def test_full_chunk_audit_class3_flags_and_spectral_absence(pilot_inputs):
    config = pilot_inputs
    domain = build_domain(config,'main')
    layout = grid_layout(config,domain)
    nominal = domain.nominal_tiles.loc[domain.nominal_tiles.quadricula == '3313-333'].geometry.iloc[0]
    for product in ['MDT','MDS']:
        counts = np.zeros(layout.shape,dtype=np.uint64)
        usable = np.zeros_like(counts)
        report = audit_cloud(cloud_path(config,product,'3313-333'),product,'3313-333',nominal,domain,layout,counts,usable,config)
        assert report['points_read'] == report['declared_points'] == 6
        assert report['classes'] == {'3':3,'5':1,'7':1,'8':1}
        assert report['flags']['withheld'] == 1 and report['flags']['invalid_return'] == 2
        assert report['usable_points_in_context'] == 2
        assert counts.sum() == 6 and usable.sum() == 2
        assert ('nir' in report['spectra']) == (product == 'MDS')
        assert report['classification_scope'] == 'whole_file'
        assert layout.transform.c % config.grid.resolution_m == 0


def test_incompatible_cloud_crs_rejected(pilot_inputs):
    config = pilot_inputs
    domain = build_domain(config,'main')
    path = cloud_path(config,'MDT','3313-333')
    data = laspy.read(path)
    data.header.add_crs(CRS.from_epsg(31982))
    data.write(path)
    layout = grid_layout(config,domain)
    with pytest.raises(ValueError,match='CRS'):
        audit_cloud(path,'MDT','3313-333',domain.official,domain,layout,np.zeros(layout.shape,dtype=np.uint64),
                    np.zeros(layout.shape,dtype=np.uint64),config)


@pytest.mark.parametrize('bad', ['../evil','/absolute','folder/../../evil','back\\..\\..\\evil','symlink'])
def test_unsafe_archive_rejected_before_extract(tmp_path,bad):
    archive = tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('expected.laz',b'LASFpayload')
        item = zipfile.ZipInfo(bad)
        if bad == 'symlink':
            item.create_system = 3
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(item,b'bad')
    target = tmp_path/'output/expected.laz'
    with pytest.raises(ValueError,match='inseguro'):
        extract_laz(archive,target,'expected.laz')
    assert not target.exists()


@pytest.mark.parametrize('payload', [b'',b'not a LAS file'])
def test_invalid_member_never_published(tmp_path,payload):
    archive = tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('expected.laz',payload)
    target = tmp_path/'output/expected.laz'
    with pytest.raises(ValueError):
        extract_laz(archive,target,'expected.laz')
    assert not target.exists()
    assert not list(target.parent.glob('*.part'))


def test_expected_member_required(tmp_path):
    archive = tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('different.laz',b'LASFother')
    with pytest.raises(ValueError,match='membro esperado'):
        extract_laz(archive,tmp_path/'expected.laz','expected.laz')


def test_reuse_zip_extracts_only_complementary_and_once(pilot_inputs):
    config = pilot_inputs
    path = cloud_path(config,'MDT','3313-324')
    payload = path.read_bytes()
    with zipfile.ZipFile(path.parent/'3313-324.zip','w') as z:
        z.writestr(path.name,payload)
    path.unlink()
    plan = input_plan(config,build_domain(config,'main'))
    rows = ensure_inputs(config,plan,download_missing=False)
    row = next(x for x in rows if x['produto']=='MDT' and x['quadricula']=='3313-324')
    assert not row['needs_download']
    assert Path(row['selected_laz']).is_relative_to(config.paths.output_root)
    assert Path(row['selected_laz']).read_bytes() == payload
    assert not path.exists() and len(rows) == 4
    assert cloud_path(config,'MDT','3313-324') == Path(row['selected_laz'])


@pytest.mark.parametrize('payload,kind,accepted', [(b'PK\x03\x04','application/zip',True),
    (b'<htm','text/html',False),(b'{err','application/json',False),(b'PK\x03\x04','text/html',False)])
def test_endpoint_requires_binary_zip_signature(payload,kind,accepted):
    class Response:
        status_code = 200
        headers = {'Content-Type':kind}
        def raise_for_status(self): pass
        def iter_content(self,n): return iter([payload])
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class Session:
        def get(self,*args,**kwargs):
            assert kwargs['stream'] and kwargs['headers']['Range']=='bytes=0-3'
            return Response()
    if accepted:
        assert validate_endpoint(Session(),'https://example.test/file',1)['zip_signature']
    else:
        with pytest.raises(ValueError): validate_endpoint(Session(),'https://example.test/file',1)


def test_prepare_roundtrip_cache_and_raw_preservation(pilot_inputs, monkeypatch):
    config = pilot_inputs
    originals = [fingerprint(p) for p in config.paths.data_root.rglob('*.laz')]
    first = prepare_inputs(config,'main')
    report = read_json(Path(first['report']))
    assert first['ok'] and not first['cache_hit'] and report['new_downloads']==0
    assert len(report['clouds']) == 4 and sum(x['points_read'] for x in report['clouds'])==24
    products = [Path(p) for p in report['products']]
    aoi = next(p for p in products if p.name == 'dominios.gpkg')
    assert set(gpd.list_layers(aoi).name) == {'corredor_oficial','medicao','contexto','quadriculas'}
    assert gpd.read_file(aoi,layer='corredor_oficial').geometry.iloc[0].equals(build_domain(config,'main').official)
    profiles = []
    for path in products:
        if path.suffix != '.tif': continue
        with rasterio.open(path) as ds:
            profiles.append((ds.shape,ds.transform,ds.crs))
            if path.name.endswith('suporte_xy.tif'):
                assert {1,2,3}.issubset(set(np.unique(ds.read(1))))
                assert ds.nodata == 255
                assert np.array_equal(ds.read(1)==255,~grid_layout(config,build_domain(config,'main')).context_mask)
    assert len(set(profiles)) == 1
    def no_audit(*a,**kw): raise AssertionError('Cache deveria evitar nova leitura integral')
    monkeypatch.setattr('sbsr_lidar.preparation.support_products',no_audit)
    second = prepare_inputs(config,'main')
    assert second['cache_hit'] and second['report']==first['report']
    assert read_json(Path(second['manifest']))['source_run_id']==first['run_id']
    assert [fingerprint(Path(p['path'])) for p in originals] == originals
    assert not read_json(config.paths.state_file)['piloto_executado']


def test_failed_preparation_records_failure(pilot_inputs, monkeypatch):
    def fail(*a,**kw): raise OSError('Falha simulada após gravar AOIs')
    monkeypatch.setattr('sbsr_lidar.preparation.support_products',fail)
    with pytest.raises(OSError,match='simulada'):
        prepare_inputs(pilot_inputs,'main')
    state = read_json(pilot_inputs.paths.state_file)
    assert state['ultima_execucao']['status']=='failed'
    manifest = next(pilot_inputs.paths.runs_root.glob('*/manifest.json'))
    assert read_json(manifest)['error']['type']=='OSError'


def test_adversarial_execution_contains_only_one_pair(pilot_inputs):
    result = prepare_inputs(pilot_inputs,'adversarial')
    report = read_json(Path(result['report']))
    assert len(report['clouds']) == 2
    assert report['domain']['context_clipped_to_tile']
    assert any('halo truncado' in x for x in report['limitations'])
    assert {x['quadricula'] for x in report['clouds']} == {'3312-431'}
