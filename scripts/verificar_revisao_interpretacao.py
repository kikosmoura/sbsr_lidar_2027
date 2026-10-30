"""Autenticação histórica e auditoria do manuscrito revisto, sem reprocessar LAZ."""
from pathlib import Path
import json
import math
import re
import subprocess
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json
from verificar_complemento_etapa17 import history
from etapa14.audit import abstract_counts, verify_registry, bibliography_checks, expand_numbers


def verify_history(project, out):
    result = history(project); aliases = []
    mutable = {project/'docs'/x for x in ['estado_projeto.json', 'decisoes_metodologicas.md', 'RETOMADA_PROJETO.md']}
    mutable.add(project/'artigo/versao_atual.json')
    records = read_json(project/'docs/manifesto_etapa17.json')['artifacts']
    for record in records:
        original = Path(record['path']); actual = out/'entradas_etapa17'/original.name if original in mutable else original
        fp = fingerprint(actual)
        if (fp['sha256'], fp['bytes']) != (record['sha256'], record['bytes']): raise ValueError(f'Histórico17 mudou: {original}')
        if original != actual: aliases.append({'original': record, 'snapshot': fp})
    result['authenticated_by_stage']['17'] = len(records); result['aliases'].extend(aliases)
    return result


def verify(project, out):
    historical = verify_history(project, out)
    inputs = read_json(out/'fontes_utilizadas.json')
    for record in inputs['inputs']+[inputs['module'], inputs['configuration']]:
        if fingerprint(Path(record['path'])) != record: raise ValueError(f'Fonte da revisão mudou: {record["path"]}')
    result = read_json(out/'resultados.json'); pairs = pd.read_csv(out/'pares16_preservados.csv')
    # Reconstituir quantis por posições na ordem, sem chamar o agregador novo.
    for name in ['P95', 'IQR']:
        x = sorted(pairs[f'absolute_{name}_difference_m'])
        for key, q in [('minimum_m',0), ('q25_m',.25), ('median_m',.5), ('q75_m',.75), ('maximum_m',1)]:
            h = (len(x)-1)*q; lo, hi = math.floor(h), math.ceil(h)
            value = x[lo]+(h-lo)*(x[hi]-x[lo])
            if abs(result['disjoint_pairs'][name][key]-value)>1e-12: raise ValueError('Distribuição dos pares divergente')
    qc = pd.read_csv(out/'qc_tin5_por_janela.csv')
    for split, group in qc.groupby('split'):
        expected = result['internal_TIN5_QC'][split]
        valid = group.rmse_m.notna() & group.n_valid.gt(0)
        if expected['n_windows'] != len(group) or expected['n_windows_with_valid_residuals'] != valid.sum(): raise ValueError('Contagens QC divergentes')
        if abs(expected['valid_record_fraction']-group.n_valid.sum()/group.n_evaluated.sum())>1e-12: raise ValueError('Denominador QC divergente')
    if result['external_accuracy_estimated'] or result['difference_above_total_measurement_error_established'] or result['metrology']['numerical_external_vertical_rmse_m'] is not None:
        raise ValueError('Acurácia externa não pode ser fabricada')
    article = project/'artigo/revisao_interpretacao_v0_3_2'; prior = project/'artigo/complemento_etapa17'
    registry = read_json(article/'dados/numeros_rastreaveis.json'); source = (article/'manuscrito.tex').read_text()
    old = read_json(prior/'dados/numeros_rastreaveis.json')
    for key, record in old['metrics'].items():
        if registry['metrics'][key] != record: raise ValueError('Resultado anterior alterado')
    numerical = verify_registry(registry); abstracts = abstract_counts(source, registry)
    bibliography = bibliography_checks(source, (article/'referencias.bib').read_text())
    if {x['key'] for x in read_json(article/'dados/referencias_verificadas.json')['references']} != set(bibliography['cited_keys']): raise ValueError('Referência sem índice primário')
    for name in ['F02_exemplo_2D_H', 'F05_pares_horizontais', 'F06_estabilidade_coorte_fixa']:
        if fingerprint(article/f'figuras/{name}.pdf')['sha256'] != fingerprint(prior/f'figuras/{name}.pdf')['sha256']: raise ValueError('Figura alterada')
    for path in (article/'tabelas').glob('*.tex'): expand_numbers(path.read_text(), registry)
    if r'V_{\mathrm{exp}}' not in source or 'sem interpretação de menor altura/dispersão como degradação' not in source: raise ValueError('Interpretação experimental ausente')
    pdf = article/'manuscrito.pdf'; info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
    (out/'pdfinfo.txt').write_text(info); pages = int(re.search(r'Pages:\s*(\d+)', info).group(1))
    if pages != 4 or 'A4' not in info: raise ValueError(f'PDF fora de quatro páginas A4: {pages}')
    fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True); (out/'fontes_pdf.txt').write_text(fonts)
    if 'TimesNewRoman' not in fonts or any(row.split()[-5]!='yes' for row in fonts.splitlines()[2:]): raise ValueError('Fontes incorretas')
    log = (article/'manuscrito.log').read_text()
    critical = re.findall(r'^.*(?:Overfull|undefined|Missing character|LaTeX Error|^!).*$', log, re.M|re.I)
    if critical: raise ValueError(f'Compilação com aviso crítico: {critical}')
    text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)
    if {int(x) for x in re.findall(r'Figura\s+(\d+)\s*:', text)} != {1,2,3}: raise ValueError('Figura ausente')
    if {int(x) for x in re.findall(r'Tabela\s+(\d+)\s*:', text)} != {1,2,3}: raise ValueError('Tabela ausente')
    if 'carlos-henrique.silva@serpro.gov.br' not in text: raise ValueError('Autoria ausente')
    bbox = out/'caixas_pdf.html'; subprocess.run(['pdftotext', '-bbox', str(pdf), str(bbox)], check=True)
    ns = {'x':'http://www.w3.org/1999/xhtml'}; bounds = []
    for page in ET.parse(bbox).findall('.//x:page', ns):
        words = page.findall('.//x:word', ns)
        b = {k: op(float(w.attrib[k]) for w in words)*25.4/72 for k, op in [('xMin',min),('xMax',max),('yMin',min),('yMax',max)]}
        if b['xMin']<18 or b['xMax']>198 or b['yMax']>255: raise ValueError(f'Caixa óptica excedida: {b}')
        bounds.append(b)
    audit = {'history': historical, 'distribution_quantiles_reconstructed': 10,
        'previous_143_article_values_unchanged': True, 'numerical_registry': numerical, 'abstracts': abstracts,
        'bibliography': bibliography, 'pdf': fingerprint(pdf), 'source': fingerprint(article/'manuscrito.tex'),
        'pages': pages, 'figures': 3, 'tables': 3, 'all_fonts_embedded': True, 'critical_latex_messages': critical,
        'bounds_mm': bounds, 'author_approved': False, 'submission_ready': False,
        'external_altimetric_accuracy_estimated': False}
    atomic_write_json(out/'verificacao.json', audit)
    return {k:v for k,v in audit.items() if k not in ['history','abstracts','bounds_mm']}


if __name__ == '__main__':
    project = Path(__file__).resolve().parents[1]
    out = Path(read_json(project/'relatorios/revisao_interpretacao/ultima_execucao.json')['output_root'])
    print(json.dumps(verify(project,out),ensure_ascii=False,indent=2))
