"""Auditar e reproduzir de forma dirigida; não faz submissão nem lote municipal."""
import argparse
from pathlib import Path
import json
from etapa15.science import audit_science
from etapa15.reproduce import reproduce

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--science-only', action='store_true')
    parser.add_argument('--reproduction-only', action='store_true')
    args = parser.parse_args()
    if args.science_only and args.reproduction_only: parser.error('Escolha somente um recorte ou execute ambos')
    project = Path(__file__).resolve().parents[1]; out = project/'relatorios/etapa15'; out.mkdir(parents=True, exist_ok=True)
    result = {}
    if not args.reproduction_only:
        r = audit_science(project, out)
        result['science'] = {'historical': r['history']['authenticated_by_stage'], 'scores': len(r['score_variants_reproduced']), 'sensitivities': len(r['sensitivities_reproduced']), 'maximum_score_error': r['maximum_score_absolute_error']}
    if not args.science_only:
        r = reproduce(project, out)
        result['reproduction'] = {'case': r['normalization']['case'], 'records': r['normalization']['records'], 'height_error_m': r['normalization']['maximum_absolute_error_m'], 'estimated_seeds': r['pycrown']['estimated_seeds'], 'cache_recovered': r['pycrown']['missing_output_and_orphan_partial_recovered'], 'seconds': r['elapsed_seconds']}
    print(json.dumps(result, ensure_ascii=False))
