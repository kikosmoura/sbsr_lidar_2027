"""Diagnóstico dirigido: registra leituras e testes locais, sem reprocessar LiDAR."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import uuid

import psutil
import geopandas as gpd
from pyproj import CRS

from sbsr_lidar.config import load_config
from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json
from etapa15.science import authenticate


def horizontal_crs(path):
    """Conferir coordenadas nativas e o driver real, sem executar transformação."""
    declared = CRS.from_wkt(path.with_suffix('.prj').read_text())
    native = declared.source_crs if declared.is_bound else declared
    driver = gpd.read_file(path, rows=1).crs
    expected = CRS.from_epsg(31983)
    if driver is None or not native.equals(expected, ignore_axis_order=True) or not driver.equals(expected, ignore_axis_order=True):
        raise ValueError(f'CRS horizontal difere de EPSG31983: {path}')
    return {'epsg': 31983, 'raw_wkt_is_bound': declared.is_bound,
        'raw_wkt_authority': declared.to_authority(), 'native_horizontal_authority': native.to_authority(),
        'driver_authority': driver.to_authority(), 'coordinate_transform_applied': False}


def history(project):
    report = authenticate(project)
    manifest = read_json(project/'docs/manifesto_etapa15.json'); aliases = []
    for record in manifest['artifacts']:
        original = Path(record['path']); actual = original
        if original in [project/'docs/estado_projeto.json', project/'docs/decisoes_metodologicas.md']:
            saved = project/'relatorios/etapa16/entradas_etapa15'/original.name
            if saved.exists(): actual = saved
        found = fingerprint(actual)
        if (found['sha256'], found['bytes']) != (record['sha256'], record['bytes']):
            raise ValueError(f'Artefato da etapa15 alterado: {original}')
        if actual != original: aliases.append({'original': record, 'snapshot': found})
    report['authenticated_by_stage']['15'] = len(manifest['artifacts'])
    report['historical_aliases'].extend(aliases)
    return report


def command(args, env=None):
    process = subprocess.run(args, capture_output=True, text=True, timeout=120, env=env)
    return {'args': args, 'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}


def diagnose(project, out, run_tests=False):
    out.mkdir(parents=True, exist_ok=False)
    record = {'stage': '16', 'type': 'retomada_diagnostico_utilitario',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'client_timezone': 'America/Sao_Paulo',
        'reported_new_failure': None, 'new_LAZ_processing': False, 'new_downloads': False,
        'raw_or_scientific_outputs_modified': False, 'external_HD_write_test_performed': False, 'commands': []}
    try:
        record['history'] = history(project)
        state = read_json(project/'docs/estado_projeto.json')
        config = load_config(project/'configs/terreno_congelado_etapa04.yaml')
        config_fp = fingerprint(project/'configs/terreno_congelado_etapa04.yaml')
        paths = {}
        for key in ['project_root', 'data_root', 'mount_root', 'output_root', 'runs_root', 'state_file', 'corridors', 'grid']:
            path = getattr(config.paths, key)
            paths[key] = {'path': str(path), 'exists': path.exists()}
        paths['mount_root']['is_mount'] = config.paths.mount_root.is_mount()
        if not all(p['exists'] for p in paths.values()) or not paths['mount_root']['is_mount']:
            raise ValueError('Caminho obrigatório ausente ou HD não montado')
        for key in ['corridors', 'grid']:
            path = getattr(config.paths, key)
            sidecars = [path.with_suffix(s) for s in ['.shp', '.shx', '.dbf', '.prj']]
            if not all(p.is_file() for p in sidecars): raise ValueError(f'Shapefile incompleto: {path}')
            paths[key].update(**horizontal_crs(path), components=[fingerprint(p) for p in sidecars])
        record['paths'] = paths
        disks = {}
        for key, path in [('project', project), ('external_HD', config.paths.mount_root)]:
            usage = shutil.disk_usage(path)
            disks[key] = {'path': str(path), 'free_gib': usage.free/2**30, 'total_gib': usage.total/2**30}
        available_ram = psutil.virtual_memory().available/2**30
        record['resources'] = {'disks': disks, 'available_ram_gib': available_ram, 'frozen_limits': config.resources.model_dump(),
            'meets_frozen_local_free': disks['project']['free_gib'] >= config.resources.min_local_free_gib,
            'meets_frozen_external_free': disks['external_HD']['free_gib'] >= config.resources.min_output_free_gib,
            'meets_cloud_RAM_budget_at_check_time': available_ram >= config.resources.max_ram_gib,
            'cloud_execution_not_requested': True}
        baseline = read_json(project/'relatorios/etapa15/registro_reproducao.json')
        current = {name: importlib.metadata.version(name) for name in baseline['environment']}
        if current != baseline['environment']: raise ValueError('Ambiente científico mudou; registrar migração antes de comparar')
        env = os.environ.copy(); env['PIP_NO_CACHE_DIR'] = '1'
        pip = command([sys.executable, '-m', 'pip', 'check'], env); record['commands'].append(pip)
        if pip['returncode']: raise ValueError('Dependências Python inconsistentes')
        worker = project/'.venv-pycrown/bin/python'
        lock = command([str(worker), '-m', 'pip', 'freeze'], env); record['commands'].append(lock)
        frozen = (project/'relatorios/etapa12/requirements_pycrown.lock.txt').read_text().strip().splitlines()
        if lock['returncode'] or sorted(lock['stdout'].strip().splitlines()) != sorted(frozen): raise ValueError('Ambiente PyCrown mudou')
        tectonic = command([str(project/'.tools/tectonic/tectonic'), '--version']); record['commands'].append(tectonic)
        if tectonic['returncode']: raise ValueError('Compilador local indisponível')
        record['environment'] = {'packages': current, 'unchanged_since_stage15': True, 'PyCrown_matches_frozen_lock': True,
            'scientific_configuration': config_fp, 'compiler': tectonic['stdout'].strip()}
        runs = []
        for path in sorted(config.paths.runs_root.glob('*/manifest.json')):
            run = read_json(path)
            runs.append({k: run.get(k) for k in ['run_id', 'command', 'stage', 'status', 'started_at', 'finished_at']})
        source_run = state['revisao_final']['source_run_id']
        if not any(r['run_id'] == source_run and r['status'] == 'completed' for r in runs): raise ValueError('Execução fonte não está concluída')
        processes = []
        for process in psutil.process_iter(['pid', 'name', 'cmdline', 'uids']):
            try:
                info = process.info
                if process.pid == os.getpid() or not info['uids'] or info['uids'].real != os.getuid() or 'python' not in (info['name'] or '').lower(): continue
                args = info['cmdline'] or []
                targets = [x for x in args if any(w in x for w in ['sample-pycrown', 'sbsr_lidar', 'pycrown_worker.py', 'baixar_lidar_geosampa.py'])]
                if targets: processes.append({'pid': process.pid, 'executable_name': info['name'], 'matched_targets': [Path(x).name for x in targets]})
            except (psutil.NoSuchProcess, psutil.AccessDenied): continue
        record['executions'] = {'status_counts': dict(Counter(r['status'] for r in runs)), 'records': runs,
            'source_run_id': source_run, 'source_completed': True,
            'unfinished_manifests': [r for r in runs if r['status'] in ['running', 'started']],
            'visible_production_processes_for_current_user': processes,
            'historical_interruptions_preserved': [r['run_id'] for r in runs if r['status'] == 'interrupted'],
            'automatic_restart_performed': False}
        root = Path(read_json(project/'artigo/dados/resultados_publicaveis.json')['sources']['coorte_selecionada']['path']).parent
        case_results = read_json(root/'result.json')['case_results']; scan = {root}
        for case in case_results.values():
            analysis = Path(case['root']); normalized = Path(case['normalized_source']).parent
            scan.update([analysis, analysis/'primary', normalized]); scan.update(p for p in normalized.glob('W*') if p.is_dir())
        partials = sorted(str(p) for d in scan for p in d.glob('*.part*') if p.is_file())
        record['partials'] = {'active_namespace_directories_checked': len(scan), 'found': partials,
            'scope': 'source_execution_root; case_analysis_root/primary; normalized_root/windows; no_recursive_municipal_scan',
            'deleted_or_ignored_as_complete': False}
        for fp in read_json(project/'artigo/dados/resultados_publicaveis.json')['sources'].values():
            if fingerprint(Path(fp['path'])) != fp: raise ValueError('Fonte de tabela alterada desde as evidências')
        article_pointer = read_json(project/'artigo/versao_atual.json')
        if fingerprint(Path(article_pointer['pdf']['path'])) != article_pointer['pdf']: raise ValueError('PDF corrente alterado')
        info = command(['pdfinfo', article_pointer['pdf']['path']]); record['commands'].append(info)
        if info['returncode'] or 'Pages:           4' not in info['stdout']: raise ValueError('PDF corrente não tem quatro páginas')
        record['article'] = {'pointer': fingerprint(project/'artigo/versao_atual.json'), 'pdf': article_pointer['pdf'],
            'classification': state['revisao_final']['classification'], 'pending': state['revisao_final']['pending'],
            'human_approval': False, 'submission_ready': False, 'submitted': False}
        if run_tests:
            args = [sys.executable, '-m', 'pytest', 'tests/cientifico/test_config.py', 'tests/cientifico/test_storage_runtime.py', 'tests/cientifico/test_final_review.py', 'tests/cientifico/test_retomada.py', '-q']
            tested = command(args); record['commands'].append(tested)
            (out/'testes_regressao.txt').write_text(tested['stdout']+tested['stderr'])
            if tested['returncode']: raise ValueError('Regressão dirigida falhou')
        record['tests_executed_this_run'] = run_tests
        record.update(status='diagnostico_concluido_sem_nova_falha_reproduzivel',
            correction_needed=False, products_invalidated=[], source_tables_authenticated=13,
            pending_editorial_and_human_items_preserved=True,
            next_action='conferir_modelo_integral_completar_endereco_institucional_e_revisao_do_autor')
    except Exception as error:
        record.update(status='dependencia_ou_divergencia_detectada', error={'type': type(error).__name__, 'message': str(error)},
            automatic_repair_or_deletion=False)
    atomic_write_json(out/'diagnostico.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--tests', action='store_true')
    args = parser.parse_args(); project = Path(__file__).resolve().parents[1]
    output = args.output or project/'relatorios/etapa16'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
    output = output.resolve()
    if not (output.is_relative_to(project/'relatorios/etapa16') or output.is_relative_to(Path('/tmp'))): parser.error('Saída deve ficar em relatorios/etapa16 ou /tmp')
    result = diagnose(project, output, args.tests)
    print(json.dumps({'status': result['status'], 'output': str(output), 'history': result.get('history', {}).get('authenticated_by_stage'), 'error': result.get('error')}, ensure_ascii=False))
    if result['status'] == 'dependencia_ou_divergencia_detectada': sys.exit(1)
