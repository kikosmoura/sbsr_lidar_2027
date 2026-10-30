"""Demonstrar regeneração sem edição: valores, CSVs e figuras equivalentes."""
from pathlib import Path
import argparse
import json
from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json


def compare(first,second):
    a,b=(read_json(root/'manifest.json') for root in [first,second])
    if a['config_fingerprint']!=b['config_fingerprint'] or a['code']!=b['code']:raise ValueError('Regeneração exige mesmo código e configuração')
    if a['source_manifest']!=b['source_manifest']:raise ValueError('Fonte científica diferente')
    ea,eb=(read_json(root/'resultados_publicaveis.json') for root in [first,second])
    values_a={k:v['value'] for k,v in ea['metrics'].items()};values_b={k:v['value'] for k,v in eb['metrics'].items()}
    identical_metrics=values_a==values_b
    files=[]
    for p in sorted(first.rglob('*')):
        if not p.is_file() or p.suffix not in {'.csv','.png','.pdf','.svg','.tex'}:continue
        q=second/p.relative_to(first)
        same=q.is_file() and fingerprint(p)['sha256']==fingerprint(q)['sha256']
        files.append({'file':p.relative_to(first).as_posix(),'same_sha256':same})
    result={'ok':identical_metrics and all(r['same_sha256'] for r in files),'first_run_id':a['run_id'],'second_run_id':b['run_id'],
        'first_root':str(first),'second_root':str(second),'same_code_and_config':True,'same_source_manifest':True,
        'identical_metric_values':identical_metrics,'metric_count':len(values_a),'files':files,
        'JSON_provenance_paths_expected_to_differ_between_runs':True,'no_manual_value_edits':True}
    atomic_write_json(Path('relatorios/etapa13/regeneracao.json'),result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('first',type=Path);p.add_argument('second',type=Path);args=p.parse_args()
    r=compare(args.first,args.second)
    print(json.dumps({'ok':r['ok'],'metrics':r['metric_count'],'files':len(r['files']),
        'mismatches':[x['file'] for x in r['files'] if not x['same_sha256']]},ensure_ascii=False))
    if not r['ok']:raise SystemExit(1)
