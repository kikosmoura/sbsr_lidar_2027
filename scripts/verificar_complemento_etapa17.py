"""Conferência independente de fontes, rankings e PDF do complemento17."""
from pathlib import Path
import json
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etapa14.audit import abstract_counts, verify_registry, bibliography_checks, expand_numbers
from etapa15.editorial import check_pdf_elements


def history(project):
    counts, aliases = {}, []
    for stage, next_stage in [('12', '13'), ('13', '14'), ('14', '15'), ('15', '16'), ('16', '17')]:
        manifest = read_json(project/f'docs/manifesto_etapa{stage}.json')
        for record in manifest['artifacts']:
            original = Path(record['path']); actual = original
            if original in [project/'docs/estado_projeto.json', project/'docs/decisoes_metodologicas.md']:
                actual = project/f'relatorios/etapa{next_stage}/entradas_etapa{stage}'/original.name
            if stage == '12' and original == project/'src/sbsr_lidar/crown_data.py':
                actual = project/'relatorios/etapa15/entradas_etapa12/crown_data.py'
            if stage == '15' and original == project/'artigo/versao_atual.json':
                actual = project/'relatorios/etapa17/entradas_etapa15/versao_atual.json'
            if stage == '16' and original == project/'docs/RETOMADA_PROJETO.md':
                actual = project/'relatorios/etapa17/entradas_etapa16/RETOMADA_PROJETO.md'
            found = fingerprint(actual)
            if (found['bytes'], found['sha256']) != (record['bytes'], record['sha256']):
                raise ValueError(f'Histórico alterado: etapa{stage}: {original}')
            if actual != original: aliases.append({'stage': stage, 'original': record, 'snapshot': found})
        counts[stage] = len(manifest['artifacts'])
    return {'authenticated_by_stage': counts, 'aliases': aliases}


def independent_rank(frame, method, decimals=12):
    frame = frame.set_index('unit_id').sort_index()
    r = (frame[['I1', 'I4', 'I6', 'I7']].rank(method='average')-.5)/len(frame)
    a = (1-r.I1+r.I4)/2
    score = a if method == 'A' else .5*a+.25*(2-r.I6-r.I7)
    score = score.round(decimals)
    result = pd.DataFrame({'unit_id': frame.index, 'score_for_ranking': score.to_numpy(),
                          'rank_mean': score.rank(method='average', ascending=False).to_numpy()})
    order = result.sort_values(['score_for_ranking', 'unit_id'], ascending=[False, True]).unit_id
    ordinal = pd.Series(np.arange(1, len(frame)+1), index=order)
    result['rank_ordinal'] = result.unit_id.map(ordinal)
    return result.set_index('unit_id').sort_index()


def verify(project, out):
    hist = history(project); provenance = read_json(out/'proveniencia.json')
    for record in provenance['authenticated_inputs']+provenance['code']:
        if fingerprint(Path(record['path'])) != record: raise ValueError(f'Fonte mudou: {record["path"]}')
    if (out/'regras_antes_calculo.yaml').read_bytes() != (project/'configs/complemento_analitico_etapa17.yaml').read_bytes():
        raise ValueError('Regras posteriores ao cálculo')
    summary = read_json(out/'resultados.json'); fixed = summary['strict_fixed_ids']
    observed = pd.read_csv(out/'estabilidade_rankings.csv')
    run = read_json(project/'relatorios/etapa12/execucao.json')
    native = pd.read_parquet(Path(run['products_root'])/'coorte_selecionada.parquet')
    native = native.loc[native.unit_id.isin(fixed)].drop(columns='geometry')
    groups = 0
    for scenario in observed.scenario_id.unique():
        tables = {'native_primary': native}
        for key, name in [('primary_on_pair_support', 'principal_suporte_comum'), ('scenario_on_pair_support', 'cenario_suporte_comum')]:
            frames = [pd.read_parquet(Path(case['root'])/scenario/f'{name}.parquet') for case in run['case_results'].values() if case['role'] == 'evaluation']
            table = pd.concat(frames, ignore_index=True); tables[key] = table.loc[table.unit_id.isin(fixed)].drop(columns='geometry')
        for measurement, frame in tables.items():
            if len(frame) != len(fixed) or set(frame.unit_id) != set(fixed): raise ValueError('Coorte fixa mudou')
            for method in ['A', 'A_plus_3D']:
                expected = independent_rank(frame, method)
                actual = observed.loc[observed.scenario_id.eq(scenario) & observed.measurement.eq(measurement) & observed.analysis_method.eq(method)].set_index('unit_id').sort_index()
                for col in ['score_for_ranking', 'rank_mean', 'rank_ordinal']:
                    if not np.allclose(actual.loc[expected.index, col], expected[col], rtol=0, atol=1e-12):
                        raise ValueError(f'Ranking não reproduzido: {scenario}/{measurement}/{method}/{col}')
                groups += 1
    article = project/'artigo/complemento_etapa17'; pdf = article/'manuscrito.pdf'
    registry = read_json(article/'dados/numeros_rastreaveis.json'); source = (article/'manuscrito.tex').read_text()
    nums = verify_registry(registry); abstracts = abstract_counts(source, registry)
    refs = bibliography_checks(source, (article/'referencias.bib').read_text())
    for path in (article/'tabelas').glob('*.tex'): expand_numbers(path.read_text(), registry)
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True); (out/'pdfinfo.txt').write_text(info)
    pages = int(re.search(r'Pages:\s*(\d+)', info).group(1))
    if pages != 4 or 'A4' not in info: raise ValueError('PDF fora de quatro páginas A4')
    fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True); (out/'fontes_pdf.txt').write_text(fonts)
    if 'TimesNewRoman' not in fonts or any(row.split()[-5] != 'yes' for row in fonts.splitlines()[2:]):
        raise ValueError('Fonte ausente ou não incorporada')
    log = (article/'manuscrito.log').read_text()
    critical = re.findall(r'^.*(?:Overfull|undefined|Missing character|LaTeX Error|^!).*$', log, re.M | re.I)
    if critical: raise ValueError(f'Aviso crítico no PDF: {critical}')
    text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)
    elements = check_pdf_elements(text)
    if 'carlos-henrique.silva@serpro.gov.br' not in text: raise ValueError('Autoria ausente')
    bbox = out/'caixas_pdf.html'; subprocess.run(['pdftotext', '-bbox', str(pdf), str(bbox)], check=True)
    ns = {'x': 'http://www.w3.org/1999/xhtml'}; bounds = []
    for i, page in enumerate(ET.parse(bbox).findall('.//x:page', ns), 1):
        words = page.findall('.//x:word', ns)
        b = {key: op(float(w.attrib[key]) for w in words)*25.4/72 for key, op in [('xMin', min), ('xMax', max), ('yMin', min), ('yMax', max)]}
        if b['xMin'] < 18 or b['xMax'] > 198 or b['yMax'] > 255 or (i > 1 and b['yMin'] < 24): raise ValueError('Texto fora da caixa editorial')
        bounds.append({'page': i, 'bounds_mm': b})
    result = {'historical_integrity': hist, 'authenticated_analysis_files': len(provenance['authenticated_inputs']),
        'independently_reconstructed_ranking_groups': groups, 'rank_tolerance': 1e-12, 'numerical_registry': nums,
        'old_538_pairs_and_11_comparisons_reproduced': summary['old_538_pairs_reproduced'] and summary['old_11_sensitivities_reproduced'],
        'pdf': fingerprint(pdf), 'source': fingerprint(article/'manuscrito.tex'), 'pages': pages, 'paper': 'A4',
        'abstracts': abstracts, 'bibliography': refs, 'all_fonts_embedded': True, 'critical_latex_messages': critical,
        'elements_captioned': elements, 'bounds': bounds, 'visual_inspection_separately_required': True,
        'submission_ready': False, 'author_approved': False, 'full_official_style_equivalence_certified': False}
    atomic_write_json(out/'verificacao_independente.json', result)
    return result


if __name__ == '__main__':
    project = Path(__file__).resolve().parents[1]
    out = Path(read_json(project/'relatorios/etapa17/ultima_analise.json')['output_root'])
    r = verify(project, out)
    print(json.dumps({k: v for k, v in r.items() if k not in ['historical_integrity', 'abstracts', 'bounds']}, ensure_ascii=False, indent=2))
