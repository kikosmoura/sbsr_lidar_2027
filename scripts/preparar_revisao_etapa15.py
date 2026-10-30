from pathlib import Path
import argparse
import json
from etapa15.editorial import clone_and_rebuild, compile_at, inspect
from sbsr_lidar.storage import atomic_write_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preparar/compilar a cópia editorial revisada, preservando o original14')
    parser.add_argument('--compile-only', action='store_true')
    args = parser.parse_args(); project = Path(__file__).resolve().parents[1]; out = project/'relatorios/etapa15'
    article = project/'artigo/revisao_etapa15' if args.compile_only else clone_and_rebuild(project, out)
    compilation = compile_at(project, article, out/'compilacao_revisao.txt')
    result = inspect(project, article, out)
    atomic_write_json(out/'compilacao.json', compilation)
    print(json.dumps({'pages': result['pages'], 'abstract_words': {k: v['words'] for k, v in result['abstracts'].items()}, 'references': result['bibliography']['references'], 'critical_latex_messages': result['critical_latex_messages']}, ensure_ascii=False))
