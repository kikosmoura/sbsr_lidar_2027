from pathlib import Path
import argparse
import json
from sbsr_lidar.storage import read_json,atomic_write_json
from etapa13.verification import verify

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Conferir números, universos, figuras e NoData da etapa13')
    parser.add_argument('--root',type=Path);args=parser.parse_args()
    root=args.root or Path(read_json(Path('relatorios/etapa13/ultima_execucao.json'))['output_root'])
    result=verify(root)
    atomic_write_json(Path('relatorios/etapa13/verificacao_independente.json'),result)
    print(json.dumps({'ok':result['ok'],'checks':len(result['checks']),'run_id':result['stage13_run_id']},ensure_ascii=False))
