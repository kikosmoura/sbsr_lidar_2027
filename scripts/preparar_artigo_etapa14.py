from pathlib import Path
import argparse,json
from etapa14.build import prepare_numbers,prepare_authors,prepare_bibliography,compile_article
from etapa14.audit import expand_numbers,abstract_counts
from sbsr_lidar.storage import read_json
from sbsr_lidar.storage import atomic_write_json

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Preparar e compilar o rascunho rastreável da etapa14')
    p.add_argument('--only-cached',action='store_true');p.add_argument('--no-compile',action='store_true');a=p.parse_args()
    project=Path(__file__).resolve().parents[1]
    record={'stage':'14','status':'draft','numbers':prepare_numbers(project),'authorship':prepare_authors(project)}
    prepare_bibliography(project)
    source=(project/'artigo/manuscrito.tex').read_text();registry=read_json(project/'artigo/dados/numeros_rastreaveis.json')
    expand_numbers(source,registry);abstract_counts(source,registry)
    if not a.no_compile:record['compilation']=compile_article(project,a.only_cached)
    atomic_write_json(project/'relatorios/etapa14/preparacao.json',record)
    print(json.dumps({'status':'rascunho_compilado' if not a.no_compile else 'fonte_preparada','authors':len(record['authorship']['authors']),
        'pdf':record.get('compilation',{}).get('pdf',{}).get('path')},ensure_ascii=False))
