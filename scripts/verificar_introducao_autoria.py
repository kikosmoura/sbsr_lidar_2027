"""Conferir a revisão editorial 0.3.4 sem reprocessar os dados científicos."""
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
import json
import re
import subprocess

import yaml

from sbsr_lidar.storage import fingerprint, read_json, atomic_write_json
from etapa14.audit import MACRO, abstract_counts, bibliography_checks, verify_registry
from verificar_revisao_final_quantitativa import history as history32
from revisar_introducao_autoria import ARTICLE, AUTHORS, REPOSITORY, REVISION


def history(project, out):
    prior_out = Path(read_json(project/'relatorios/revisao_final_quantitativa/ultima_execucao.json')['output_root'])
    hist = history32(project, prior_out)
    mutable = {project/'docs'/n for n in ['estado_projeto.json', 'decisoes_metodologicas.md', 'RETOMADA_PROJETO.md']}
    mutable.add(project/'artigo/versao_atual.json')
    records = read_json(project/'docs/manifesto_revisao_final_quantitativa.json')['artifacts']
    for fp in records:
        path = Path(fp['path'])
        actual = out/'entradas_v0_3_3'/path.name if path in mutable else path
        got = fingerprint(actual)
        if (got['bytes'], got['sha256']) != (fp['bytes'], fp['sha256']):
            raise ValueError(f'Histórico 0.3.3 alterado: {path}')
    hist['authenticated_by_stage']['0.3.3'] = len(records)
    return hist


def verify(project, out):
    hist = history(project, out)
    article, prior = project/ARTICLE, project/'artigo/revisao_final_v0_3_3'
    source, old = [(p/'manuscrito.tex').read_text() for p in [article, prior]]
    registry = read_json(article/'dados/numeros_rastreaveis.json')
    if registry != read_json(prior/'dados/numeros_rastreaveis.json'):
        raise ValueError('Registro científico alterado em revisão editorial')
    if Counter(MACRO.findall(source)) != Counter(MACRO.findall(old)):
        raise ValueError('Referência numérica retirada/acrescentada')
    numbers = verify_registry(registry)
    for name in ['numeros.tex'] + [str(p.relative_to(prior)) for folder in ['figuras', 'tabelas'] for p in (prior/folder).rglob('*') if p.is_file()]:
        if (article/name).read_bytes() != (prior/name).read_bytes():
            raise ValueError(f'Figura, tabela ou valor científico alterado: {name}')
    conclusion = source.split(r'\section{Conclusões}', 1)[1].split(r'\smallskip\noindent\textbf{Código.}', 1)[0].strip()
    old_conclusion = old.split(r'\section{Conclusões}', 1)[1].split(r'\renewcommand', 1)[0].strip()
    if conclusion != old_conclusion:
        raise ValueError('Conclusão quantitativa anterior alterada')
    abstracts = abstract_counts(source, registry)
    if abstracts != abstract_counts(old, registry):
        raise ValueError('Resumo ou abstract alterado')
    intro = source.split(r'\section{Introdução}', 1)[1].split(r'\section{Material e métodos}', 1)[0]
    if not all(x in intro for x in ['A lacuna', 'As duas contribuições', '(H1)', '(H2)', 'lefsky1999', 'fagin2003']):
        raise ValueError('Lacuna, contribuições ou referências ausentes')
    refs = bibliography_checks(source, (article/'referencias.bib').read_text())
    if refs['references'] != 9 or set(refs['cited_keys']) != {x['key'] for x in read_json(article/'dados/referencias_verificadas.json')['references']}:
        raise ValueError('Referência sem origem primária documentada')
    authors = yaml.safe_load((article/'autoria.yaml').read_text())
    if authors['authors'] != AUTHORS or authors['human_review_completed']:
        raise ValueError('Autoria difere da informação fornecida')
    author_tex = (article/'autores.tex').read_text()
    for a in AUTHORS:
        if not all(x in author_tex for x in [a['name'], a['affiliation'], a['address'], a['email']]):
            raise ValueError('Autoria incompleta no bloco LaTeX')
        if r'\textit{'+a['name']+r'}\textsuperscript{'+str(a['affiliation_marker'])+'}' not in author_tex:
            raise ValueError('Itálico ou marcador de filiação ausente')
    if (article/'formato_sbsr_local.sty').read_text() != (prior/'formato_sbsr_local.sty').read_text().replace('apreciação do autor', 'apreciação dos autores'):
        raise ValueError('Dimensões, fonte ou estilo editorial alterados')
    pdf = article/'manuscrito.pdf'
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
    (out/'pdfinfo.txt').write_text(info)
    if int(re.search(r'Pages:\s*(\d+)', info).group(1)) != 4 or 'A4' not in info:
        raise ValueError('Artigo fora de quatro páginas A4')
    fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True)
    (out/'fontes_pdf.txt').write_text(fonts)
    if 'TimesNewRoman' not in fonts or any(row.split()[-5] != 'yes' for row in fonts.splitlines()[2:]):
        raise ValueError('Fontes não incorporadas')
    log = (article/'manuscrito.log').read_text()
    critical = re.findall(r'^.*(?:Overfull|undefined|Missing character|LaTeX Error|^!).*$', log, re.M|re.I)
    if critical:
        raise ValueError(f'Compilação com avisos críticos: {critical}')
    text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)
    for a in AUTHORS:
        for x in [a['name'], a['email'], 'Rua Olívia Guedes Penteado, 941']:
            if x not in text:
                raise ValueError(f'Autoria ausente do PDF: {x}')
        if a['name'] not in info:
            raise ValueError('Metadados de autoria incompletos')
    for element in ['Figura', 'Tabela']:
        if set(map(int, re.findall(element+r'\s+(\d+)\s*:', text))) != {1, 2, 3}:
            raise ValueError(f'{element} ausente')
    if REPOSITORY not in re.sub(r'\s+', '', text) or 'serão disponibilizados' not in text:
        raise ValueError('Indicação do repositório incompleta ou disponibilidade antecipada')
    xml = out/'ligacoes_pdf.xml'
    subprocess.run(['pdftohtml', '-xml', '-i', '-hidden', str(pdf), str(xml)], check=True, stdout=subprocess.DEVNULL)
    links = {a.get('href') for a in ET.parse(xml).iter('a')}
    if REPOSITORY not in links:
        raise ValueError('Repositório sem hiperlink no PDF')
    atestado = next(x for x in read_json(article/'dados/referencias_verificadas.json')['references'] if x['key'] == 'atestado2020')['primary_url']
    if atestado not in links:
        raise ValueError('Link integral do atestado não preservado')
    bbox = out/'caixas_pdf.html'
    subprocess.run(['pdftotext', '-bbox', str(pdf), str(bbox)], check=True)
    ns = {'x': 'http://www.w3.org/1999/xhtml'}
    bounds = []
    for page in ET.parse(bbox).findall('.//x:page', ns):
        words = page.findall('.//x:word', ns)
        b = {k: op(float(w.attrib[k]) for w in words)*25.4/72 for k, op in [('xMin', min), ('xMax', max), ('yMin', min), ('yMax', max)]}
        if b['xMin'] < 18 or b['xMax'] > 198 or b['yMax'] > 255:
            raise ValueError(f'Caixa editorial excedida: {b}')
        bounds.append(b)
    result = {'revision': REVISION, 'historical_counts': hist['authenticated_by_stage'],
        'pdf': fingerprint(pdf), 'source': fingerprint(article/'manuscrito.tex'),
        'pages': 4, 'figures': 3, 'tables': 3, 'numerical_registry': numbers,
        'same_numerical_macros': True, 'same_registry_figures_tables_and_conclusion': True,
        'abstracts': abstracts, 'bibliography': refs, 'authors': AUTHORS,
        'author_format_checked': 'italic_names_superscript_markers_centered_affiliations',
        'same_page_dimensions_fonts_and_sizes': True, 'all_fonts_embedded': True,
        'critical_latex_messages': critical, 'bounds_mm': bounds,
        'repository': REPOSITORY, 'repository_hyperlink_present': True,
        'source_document_hyperlink_preserved': True, 'codes_uploaded_or_availability_verified': False,
        'human_author_approval': False, 'submitted': False}
    atomic_write_json(out/'verificacao.json', result)
    return result


if __name__ == '__main__':
    project = Path(__file__).resolve().parents[1]
    out = Path(read_json(project/'relatorios/revisao_introducao_autoria/ultima_execucao.json')['output_root'])
    result = verify(project, out)
    print(json.dumps({k: v for k, v in result.items() if k not in ['abstracts', 'authors', 'bounds_mm']}, ensure_ascii=False, indent=2))
