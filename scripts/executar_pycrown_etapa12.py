"""Entrada reproduzível com relatório JSON, preservando a primeira execução base."""
from pathlib import Path
import argparse
import json
from sbsr_lidar.config import load_config
from sbsr_lidar.crown_run import sample_pycrown
from sbsr_lidar.storage import atomic_write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/terreno_congelado_etapa04.yaml'))
    p.add_argument('--design',type=Path,default=Path('configs/amostra_pycrown_exploratoria_v0_3_0.yaml'))
    p.add_argument('--case');p.add_argument('--plan-only',action='store_true');p.add_argument('--download-missing',action='store_true')
    args=p.parse_args();cfg=load_config(args.config)
    result=sample_pycrown(cfg,args.design,case=args.case,plan_only=args.plan_only,download_missing=args.download_missing)
    report=cfg.paths.project_root/'relatorios/etapa12'
    if args.plan_only:target=report/'plano_cli.json'
    else:target=report/f'execucao_{result["run_id"]}.json'
    atomic_write_json(target,result)
    if not args.plan_only and args.case is None:
        atomic_write_json(report/'ultima_execucao.json',result)
        if not (report/'execucao.json').exists():atomic_write_json(report/'execucao.json',result)
    print(json.dumps({'report':str(target),'products_root':result.get('products_root'),'sample':result.get('sample'),
        'baseline_report_preserved':str(report/'execucao.json')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
