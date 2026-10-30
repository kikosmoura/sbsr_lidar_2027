"""Reprodução dirigida sobre entradas reais preservadas, com saídas temporárias."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.metadata
import json
import subprocess
import tempfile
import time

import numpy as np
import pandas as pd
import shapely

from sbsr_lidar.config import load_config
from sbsr_lidar.crown_plan import load_crown_design, selected_domains, CrownScenario
from sbsr_lidar.crown_run import prepare, cache_identity
from sbsr_lidar.crown_data import deduplicate_ground, query, completed
from sbsr_lidar.crown_raster import run_worker
from sbsr_lidar.terrain_surface import Surface
from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json


def array_digest(array):
    a = np.ascontiguousarray(array)
    return hashlib.sha256(str((a.dtype.str, a.shape)).encode()+a.tobytes()).hexdigest()


def replay_window(config, design, domain, case, temporary):
    """TIN de uma janela a partir dos blocos LAZ já decodificados; nenhuma aquisição."""
    normalized = Path(case['normalized_source']).parent
    raw = normalized.parent/'raw'; index = read_json(raw/'index.json')
    windows = read_json(normalized/'normalization.json')['windows']
    window = sorted((w for w in windows if w['mds_records'] > 0), key=lambda w: (w['wx'], w['wy']))[0]
    wx, wy = window['wx'], window['wy']; size = design.window_size_m
    region = shapely.box(wx*size, wy*size, (wx+1)*size, (wy+1)*size).buffer(design.terrain_context_m, join_style='mitre').intersection(domain.context)
    ground = []; mds = []; inputs = []
    for bucket in index['buckets']:
        terrain = bucket['product'] == 'MDT' and abs(bucket['wx']-wx) <= 1 and abs(bucket['wy']-wy) <= 1
        points = bucket['product'] == 'MDS' and (bucket['wx'], bucket['wy']) == (wx, wy)
        if not (terrain or points): continue
        path = Path(bucket['path']); seal = read_json(path.parent/'complete.json')
        expected = next(p for p in seal['outputs'] if p['path'] == str(path))
        if fingerprint(path) != expected: raise ValueError('Bloco de entrada alterado')
        inputs.append(expected); f = pd.read_parquet(path)
        if points: mds.append((path, f))
        if terrain:
            keep = ((f.qc_flags.to_numpy() & 2) == 0) & shapely.intersects_xy(region, f.x.to_numpy(), f.y.to_numpy())
            if keep.any(): ground.append(f.loc[keep, ['x', 'y', 'z_absolute']].to_numpy())
    xyz = deduplicate_ground(np.concatenate(ground), config)
    if len(xyz) != window['unique_ground_vertices']: raise ValueError('Vértices MDT diferentes')
    model = Surface(xyz, config.terrain); maximum = 0.; rows = 0; checks = []
    seal = read_json(normalized/f'W{wx}_{wy}/complete.json'); hashes = {p['path']: p for p in seal['outputs']}
    for i, (source, f) in enumerate(sorted(mds, key=lambda p: str(p[0]))):
        expected_path = Path(window['height_parts'][i])
        if fingerprint(expected_path) != hashes[str(expected_path)]: raise ValueError('Alturas originais alteradas')
        inputs.append(hashes[str(expected_path)]); old = pd.read_parquet(expected_path)
        if list(zip(f.source_tile, f.source_point_index)) != list(zip(old.source_tile, old.source_point_index)): raise ValueError('Ordem/ID de registros alterada')
        z, status = query(model, f[['x', 'y']].to_numpy(), config)
        excluded = (f.qc_flags.to_numpy() & 2) != 0; z[excluded] = np.nan; status[excluded] = 6
        h = f.z_absolute.to_numpy()-z; flags = f.qc_flags.to_numpy().astype('uint16')
        flags[(status != 0) & ~excluded] |= 1
        flags[np.isfinite(h) & (h < 0)] |= 4
        flags[np.isfinite(h) & (h < config.terrain.negative_warning_m)] |= 8
        flags[np.isfinite(h) & (h > config.terrain.extreme_height_m)] |= 16
        for key, values in [('h', h), ('terrain_z', z)]:
            if not np.array_equal(np.isnan(values), np.isnan(old[key].to_numpy())): raise ValueError('Padrão NoData diferente')
            valid = np.isfinite(values); error = float(np.max(np.abs(values[valid]-old[key].to_numpy()[valid]))) if valid.any() else 0.
            maximum = max(maximum, error)
            if error > 1e-9: raise ValueError('Reprodução altimétrica fora da tolerância')
        if not np.array_equal(status, old.terrain_status) or not np.array_equal(flags, old.qc_flags): raise ValueError('Status/flags diferentes')
        replay = pd.DataFrame({'source_tile': f.source_tile, 'source_point_index': f.source_point_index, 'terrain_z': z, 'h': h, 'terrain_status': status, 'qc_flags': flags})
        replay.to_parquet(temporary/f'replay_H_{i:04d}.parquet', index=False)
        rows += len(f); checks.append({'source_block': fingerprint(source), 'expected_normalized_part': fingerprint(expected_path), 'rows': len(f)})
    for fp in inputs:
        if fingerprint(Path(fp['path'])) != fp: raise ValueError('Entrada modificada durante a reprodução')
    return {'case': domain.corridor_id, 'window': [wx, wy], 'records': rows, 'unique_ground_vertices': len(xyz),
        'height_absolute_tolerance_m': 1e-9, 'maximum_absolute_error_m': maximum, 'NoData_status_QC_exact': True,
        'parts': checks, 'input_blocks_authenticated': len(inputs), 'all_inputs_unchanged': True,
        'starting_level': 'preserved_decoded_MDT_MDS_blocks; full_LAZ_decode_not_repeated', 'formula': 'H=Z_absolute-TIN5(X,Y)'}


def replay_pycrown(config, design, domain, case, temporary):
    source = Path(case['root'])/'primary'
    seal = read_json(Path(case['root'])/'complete.json'); hashes = {p['path']: p for p in seal['outputs']}
    for name in ['input.npz', 'labels.npz', 'job.json']:
        path = source/name
        if fingerprint(path) != hashes[str(path)]: raise ValueError('Entrada/resultado PyCrown alterado')
    upstream = config.paths.project_root/design.upstream_root
    for fp in read_json(upstream/'UPSTREAM.json')['files']:
        if fingerprint(upstream/fp['path'])['sha256'] != fp['sha256']: raise ValueError('PyCrown original alterado')
    with np.load(source/'input.npz') as x: chm = x['chm']; valid = x['valid']
    with np.load(source/'labels.npz') as x: expected = {k: x[k] for k in x.files}
    arrays = {'chm': chm, 'observation': np.where(valid, 1, 2).astype('uint8')}
    layout = SimpleNamespace(width=chm.shape[1], height=chm.shape[0]); events = []
    def event(name, **data): events.append({'event': name, **data})
    root = temporary/'pycrown'
    labels, worker = run_worker(config, design, layout, arrays, CrownScenario(), root, event)
    def equal_arrays():
        with np.load(labels) as x:
            for k, original in expected.items():
                if not np.array_equal(x[k], original, equal_nan=True): raise ValueError(f'Reprodução PyCrown diferente: {k}')
    equal_arrays(); first = fingerprint(labels); event_at = len(events)
    run_worker(config, design, layout, arrays, CrownScenario(), root, event)
    if fingerprint(labels) != first or [e['event'] for e in events[event_at:]] != ['pycrown_cache']: raise ValueError('Cache intacto não retomado')
    # Somente a saída TEMPORÁRIA é removida; uma parcial órfã não vale como resultado.
    labels.unlink(); (root/'labels.part.npz').write_bytes(b'incomplete-checkpoint')
    if completed(root/'worker_complete.json') is not None: raise ValueError('Checkpoint incompleto aceito')
    run_worker(config, design, layout, arrays, CrownScenario(), root, event); equal_arrays()
    if (root/'labels.part.npz').exists(): raise ValueError('Parcial não foi substituída atomicamente')
    key = cache_identity(config, design, domain, read_json(Path(case['root'])/'qc.json')['inputs'])
    changed = config.model_copy(update={'terrain': config.terrain.model_copy(update={'maximum_distance_m': 4.})})
    changed_key = cache_identity(changed, design, domain, read_json(Path(case['root'])/'qc.json')['inputs'])
    if key == changed_key: raise ValueError('Parâmetro físico não invalida identidade de cache')
    for name in ['input.npz', 'labels.npz', 'job.json']:
        if fingerprint(source/name) != hashes[str(source/name)]: raise ValueError('Fonte preservada foi alterada')
    return {'case': domain.corridor_id, 'whole_corridor_input_shape': list(chm.shape), 'estimated_seeds': worker['seeds'],
        'exact_arrays': {k: {'dtype': str(v.dtype), 'shape': list(v.shape), 'semantic_sha256': array_digest(v)} for k, v in expected.items()},
        'input': hashes[str(source/'input.npz')], 'expected_labels': hashes[str(source/'labels.npz')],
        'intact_cache_hit': True, 'missing_output_and_orphan_partial_recovered': True,
        'parameter_change_invalidates_cache_identity': True, 'modified_parameter_not_executed': True,
        'all_preserved_inputs_unchanged': True, 'events': events,
        'comparison': 'exact decoded arrays; NPZ timestamps/container bytes not the numerical criterion'}


def reproduce(project, out):
    started = time.monotonic(); design = load_crown_design(project/'configs/amostra_pycrown_exploratoria_v0_3_0.yaml')
    config = prepare(load_config(project/'configs/terreno_congelado_etapa04.yaml'), design)
    _, domains, _, _, _ = selected_domains(config, design)
    evidence = read_json(project/'artigo/dados/resultados_publicaveis.json')
    root = Path(evidence['sources']['coorte_selecionada']['path']).parent
    cases = read_json(root/'result.json')['case_results']
    cid = sorted(c for c, r in cases.items() if r['role'] == 'development')[0]
    domain = domains[cid]; case = cases[cid]
    worker_lock = subprocess.check_output([str(project/design.worker_python), '-m', 'pip', 'freeze'], text=True).strip().splitlines()
    frozen = (project/'relatorios/etapa12/requirements_pycrown.lock.txt').read_text().strip().splitlines()
    if sorted(worker_lock) != sorted(frozen): raise ValueError('Ambiente PyCrown difere do congelado')
    with tempfile.TemporaryDirectory(prefix='sbsr_etapa15_repro_') as tmp:
        temporary = Path(tmp)
        result = {'sample_selection': 'lexicographically_first_development_corridor; first_nonempty_XY_window; no_selection_by_result',
            'normalization': replay_window(config, design, domain, case, temporary),
            'pycrown': replay_pycrown(config, design, domain, case, temporary),
            'temporary_directory': str(temporary), 'all_outputs_temporary': True,
            'environment': {name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'pandas', 'shapely', 'pyarrow', 'rasterio', 'laspy', 'lazrs']},
            'worker_lock_matches_frozen': True, 'worker_packages': worker_lock,
            'seed': design.seed, 'scientific_config': fingerprint(project/'configs/terreno_congelado_etapa04.yaml'),
            'design': fingerprint(project/'configs/amostra_pycrown_exploratoria_v0_3_0.yaml'),
            'worker': fingerprint(project/design.worker_script), 'raw_LAZ_files_modified': False,
            'p_values_or_external_validation': False}
    result.update(temporary_directory_removed=not temporary.exists(), elapsed_seconds=time.monotonic()-started)
    atomic_write_json(out/'registro_reproducao.json', result)
    return result
