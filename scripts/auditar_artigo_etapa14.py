from pathlib import Path
import json
from etapa14.audit import audit

if __name__ == '__main__':
    result = audit(Path(__file__).resolve().parents[1])
    print(json.dumps({'status': result['status'], 'pages': result['pdf']['pages'],
        'abstract_words': {k: v['words'] for k, v in result['abstracts'].items()},
        'numbers': result['numbers'], 'references': result['bibliography']['references'], 'claims': result['claims']}, ensure_ascii=False))
