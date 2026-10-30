"""Encadear exportação, auditoria, prova de retomada e figuras após o executor.

Não conclui o estado científico: documentação final exige revisão dos artefatos.
"""
from pathlib import Path
import contextlib
import subprocess
import sys
import time
from sbsr_lidar.config import load_config
from sbsr_lidar.crown_run import sample_pycrown
from sbsr_lidar.storage import read_json,atomic_write_json,fingerprint


def main():
    report=Path('relatorios/etapa12');execution=report/'execucao.json'
    while not execution.is_file():time.sleep(5)
    actual=read_json(execution)
    for name in ['exportar_pycrown_etapa12.py','verificar_etapa12.py']:
        print('start',name,flush=True)
        subprocess.run([sys.executable,'scripts/'+name],check=True)
    print('start cache resume demonstration',flush=True)
    with (report/'retomada_stdout.txt').open('w') as output,contextlib.redirect_stdout(output):
        resumed=sample_pycrown(load_config(Path('configs/terreno_congelado_etapa04.yaml')),Path('configs/amostra_pycrown_exploratoria_v0_3_0.yaml'))
    atomic_write_json(report/'execucao_retomada.json',resumed)
    log=Path(resumed['run_manifest']).parent/'execution.log';events=log.read_text()
    same_roots={cid:resumed['case_results'][cid]['root']==item['root'] for cid,item in actual['case_results'].items()}
    tables=[]
    for q in sorted(Path(resumed['products_root']).glob('*.parquet')):
        p=Path(actual['products_root'])/q.name
        tables.append({'file':p.name,'identical_sha256':fingerprint(p)['sha256']==fingerprint(q)['sha256']})
    proof={'all_cases_cache_hit':len(same_roots)==10 and all(same_roots.values()) and events.count('case_cache ')==10,
        'case_roots_unchanged':same_roots,'no_LAZ_decode':events.count('decode_laz ')==0,
        'no_new_normalized_windows':events.count('normalized_window ')==0,'no_PyCrown_reexecution':events.count('pycrown_start ')==0,
        'scientific_tables':tables,'all_scientific_tables_identical':all(p['identical_sha256'] for p in tables),
        'comparison_scope':'tables_materialized_by_core_executor; later_postprocessing_tables_checked_separately',
        'resume_run_id':resumed['run_id'],'resume_run_manifest':fingerprint(Path(resumed['run_manifest'])),
        'resume_peak_rss_gib':resumed['resources']['peak_rss_gib'],'resume_seconds':resumed['resources']['elapsed_seconds']}
    atomic_write_json(report/'retomada.json',proof)
    if not all(proof[k] for k in ['all_cases_cache_hit','no_LAZ_decode','no_new_normalized_windows','no_PyCrown_reexecution','all_scientific_tables_identical']):
        raise ValueError('Demonstração de retomada não satisfeita')
    print('cache resume verified',proof['resume_seconds'],flush=True)
    subprocess.run([sys.executable,'scripts/visualizar_pycrown_etapa12.py'],check=True)
    print('products ready for review',flush=True)


if __name__=='__main__':main()
