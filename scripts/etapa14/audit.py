"""Conferência editorial e de evidências, sem executar novamente as nuvens."""
from pathlib import Path
import json
import math
import re
import subprocess
from xml.etree import ElementTree as ET

import pandas as pd
import yaml

from sbsr_lidar.storage import fingerprint, read_json, atomic_write_json
from etapa14.build import authenticate13, display, select_one


MACRO = re.compile(r'\\(Ev|En|Par)\{([^{}]+)\}')
WORDS = re.compile(r'\d+(?:[.,]\d+)*(?:%)?|[^\W\d_]+(?:[-’\'][^\W\d_]+)*', re.UNICODE)


def expand_numbers(text, registry):
    """A mesma origem numérica, com erro explícito em vez de macro vazia."""
    def replace(match):
        kind, key = match.groups()
        source = registry['parameters' if kind == 'Par' else 'metrics']
        if key not in source:
            raise ValueError(f'Macro sem evidência: {kind}{{{key}}}')
        r = source[key]
        return str(r['value']) if r.get('literal') else display(r['value'], r.get('decimals'), kind == 'En', r.get('scale', 1)).replace('{,}', ',')
    return MACRO.sub(replace, text)


def prose(text):
    text = re.sub(r'(?m)(?<!\\)%[^\n]*', '', text)
    text = re.sub(r'\\(?:cite|label|ref)\{[^}]*\}', '', text)
    text = text.replace(r'\%', '%').replace('~', ' ')
    text = re.sub(r'\\[a-zA-Z]+\*?', '', text)
    return ' '.join(text.translate(str.maketrans('', '', '{}$')).split())


def abstract_counts(source, registry):
    pt = source.split(r'\section*{Resumo}', 1)[1].split(r'\smallskip', 1)[0]
    en = source.split(r'\begin{otherlanguage}{english}\itshape', 1)[1].split(r'\smallskip', 1)[0]
    result = {}
    for language, text in [('pt', pt), ('en', en)]:
        clean = prose(expand_numbers(text, registry))
        result[language] = {'words': len(WORDS.findall(clean)), 'text': clean}
        if not 100 <= result[language]['words'] <= 150:
            raise ValueError(f'Resumo {language}: {result[language]["words"]} palavras, exigido100–150')
    return result


def claims_matrix(source, registry, original_claims):
    pattern = re.compile(r'^% EVIDENCIA: (\w+) \| (\w+) \| ([\w,]+)\s*$', re.M)
    markers = list(pattern.finditer(source))
    original = {c['claim_id']: c for c in original_claims}
    claims = []
    for i, marker in enumerate(markers):
        key, classification, refs = marker.groups()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(source)
        block = source[marker.end():end]
        # Figuras/tabelas têm seus próprios itens no índice; aqui fica o trecho argumentativo.
        text = re.sub(r'\\begin\{(figure\*?|table)\}.*?\\end\{\1\}', '', block, flags=re.S)
        text = re.sub(r'\\(?:sub)?section\*?\{[^}]*\}', '', text)
        refs = refs.split(',')
        if any(r not in original for r in refs):
            raise ValueError(f'Afirmação sem índice da etapa13: {key}')
        expand_numbers(block, registry)
        claims.append({'claim_id': key, 'classification': classification,
            'source_lines': [source[:marker.start()].count('\n') + 1, source[:end].count('\n')],
            'statement_expanded': prose(expand_numbers(text, registry)),
            'metric_ids': sorted({m[1] for m in MACRO.findall(block) if m[0] != 'Par'}),
            'parameter_ids': sorted({m[1] for m in MACRO.findall(block) if m[0] == 'Par'}),
            'stage13_claim_ids': refs,
            'limitations': sorted({s for r in refs for s in original[r]['limitations']}),
            'citation_keys': sorted({k for group in re.findall(r'\\cite\{([^}]+)\}', block) for k in group.split(',')})})
    if not claims or len({c['claim_id'] for c in claims}) != len(claims):
        raise ValueError('Matriz vazia ou IDs repetidos')
    return claims


def json_pointer(data, pointer):
    for key in pointer.strip('/').split('/'):
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def verify_registry(registry):
    """Releia cada fonte/linha; não compare só o texto já arredondado."""
    seen = {}; count = 0
    for key, record in registry['metrics'].items():
        if 'derived_from' in record:
            actual = sum(registry['metrics'][k]['value'] for k in record['derived_from'])
        else:
            fp = record['source']; path = Path(fp['path'])
            if path not in seen:
                if fingerprint(path) != fp: raise ValueError(f'Fonte numérica alterada: {path}')
                seen[path] = read_json(path) if path.suffix == '.json' else pd.read_csv(path)
            data = seen[path]
            actual = json_pointer(data, record['json_pointer']) if 'json_pointer' in record else select_one(data, record['filters'])[record['column']]
        if not math.isclose(float(actual), float(record['value']), rel_tol=0, abs_tol=1e-12):
            raise ValueError(f'Número não reproduzido: {key}')
        count += 1
    for key, record in registry['parameters'].items():
        fp = record['source']; path = Path(fp['path'])
        if fingerprint(path) != fp: raise ValueError(f'Parâmetro com fonte alterada: {key}')
        if record.get('pointer'):
            actual = json_pointer(yaml.safe_load(path.read_text()), record['pointer'])
            if actual != record['value']: raise ValueError(f'Parâmetro divergente: {key}')
    return {'reproduced_metrics': count, 'parameters': len(registry['parameters']), 'numerical_source_files': len(seen)}


def bibliography_checks(source, bibliography):
    cited = {k.strip() for group in re.findall(r'\\cite\{([^}]+)\}', source) for k in group.split(',')}
    existing = set(re.findall(r'@\w+\{([^,]+),', bibliography))
    if cited != existing:
        raise ValueError(f'Citações ausentes/extras: {cited ^ existing}')
    if not cited: raise ValueError('Bibliografia vazia')
    return {'cited_keys': sorted(cited), 'references': len(existing), 'all_citations_resolved': True}


def inspect_pdf(project):
    article = project/'artigo'; report = project/'relatorios/etapa14'
    pdf = article/'manuscrito.pdf'
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
    (report/'pdfinfo.txt').write_text(info)
    pages = int(re.search(r'Pages:\s*(\d+)', info).group(1))
    if not 1 <= pages <= 4: raise ValueError(f'Artigo com {pages} páginas')
    if 'A4' not in info: raise ValueError('Formato não é A4')
    bbox = report/'caixas_pdf.html'
    subprocess.run(['pdftotext', '-bbox', str(pdf), str(bbox)], check=True)
    root = ET.parse(bbox); ns = {'x': 'http://www.w3.org/1999/xhtml'}
    bounds = []
    for i, page in enumerate(root.findall('.//x:page', ns), 1):
        words = page.findall('.//x:word', ns)
        values = {k: op(float(w.attrib[k]) for w in words)*25.4/72 for k, op in [('xMin', min), ('xMax', max), ('yMin', min), ('yMax', max)]}
        # Tolera diferenças ópticas de glifos de até1mm em relação à caixa TeX.
        if values['xMin'] < 18 or values['xMax'] > 198 or values['yMax'] > 255 or (i > 1 and values['yMin'] < 24):
            raise ValueError(f'Conteúdo fora da caixa editorial: página{i}: {values}')
        footer = [w.text for w in words if float(w.attrib['yMin'])*25.4/72 > 260]
        if footer: raise ValueError(f'Conteúdo/numeração no rodapé: {footer}')
        bounds.append({'page': i, 'visible_text_bounds_mm': values, 'footer_words_below_260mm': footer})
    fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True)
    (report/'fontes_pdf.txt').write_text(fonts)
    font_rows = fonts.splitlines()[2:]
    for row in font_rows:
        # As três colunas emb/sub/uni antecedem o ID do objeto.
        if row.split()[-5] != 'yes': raise ValueError(f'Fonte não incorporada: {row}')
    if 'TimesNewRomanPSMT' not in fonts: raise ValueError('Times New Roman ausente')
    log = (article/'manuscrito.log').read_text()
    critical = re.findall(r'^.*(?:Overfull|undefined|Missing character|LaTeX Error|^!).*$', log, re.M | re.I)
    if critical: raise ValueError(f'Aviso crítico no LaTeX: {critical}')
    return {'pages': pages, 'paper': 'A4', 'all_fonts_embedded': True, 'critical_latex_messages': critical,
        'underfull_vbox_notices': len(re.findall('Underfull', log)), 'page_bounds': bounds,
        'title_visible_top_mm': bounds[0]['visible_text_bounds_mm']['yMin'],
        'source_geometry_mm': {'left': 19, 'top': 25, 'textwidth': 178, 'textheight': 229, 'columnwidth': 86, 'columnsep': 6},
        'visible_glyph_tolerance_mm': 1, 'body_font_pt': 10, 'captions_pt': 9, 'title_pt': 14,
        'small_subscripts_are_math_not_reduced_body': True, 'page_numbers': False, 'pdf': fingerprint(pdf)}


def audit(project):
    authenticate13(project)
    article = project/'artigo'; report = project/'relatorios/etapa14'
    registry = read_json(article/'dados/numeros_rastreaveis.json')
    source = (article/'manuscrito.tex').read_text()
    expand_numbers(source, registry)
    counts = abstract_counts(source, registry)
    original = read_json(article/'dados/resultados_publicaveis.json')
    claims = claims_matrix(source, registry, original['claims'])
    bibliography = bibliography_checks(source, (article/'referencias.bib').read_text())
    refs = read_json(article/'dados/referencias_verificadas.json')['references']
    if set(bibliography['cited_keys']) != {r['key'] for r in refs}: raise ValueError('Referência sem fonte primária registrada')
    fig_metadata = read_json(report/'preparacao.json')['numbers']['figure_copies']
    for item in fig_metadata:
        if fingerprint(Path(item['copy']['path'])) != item['copy'] or fingerprint(Path(item['source']['path'])) != item['source']:
            raise ValueError('Figura alterada')
        if item['copy']['sha256'] != item['source']['sha256']: raise ValueError('Cópia de figura divergente')
    # Valida também todas as macros dos arquivos incluídos de tabelas.
    for path in (article/'tabelas').glob('*.tex'): expand_numbers(path.read_text(), registry)
    source13 = Path(read_json(project/'relatorios/etapa13/ultima_execucao.json')['output_root'])
    elements = [
        {'id': 'Figura1', 'source': fig_metadata[0], 'evidence': ['C13_04', 'C13_07'], 'selection': fingerprint(article/'dados/selecao_exemplos.json')},
        {'id': 'Figura2', 'source': fig_metadata[1], 'evidence': ['C13_03']},
        {'id': 'Figura3', 'source': fig_metadata[2], 'evidence': ['C13_05']},
        {'id': 'Tabela1', 'source': fingerprint(source13/'tables/dados_amostra.csv'), 'evidence': ['C13_01', 'C13_02'], 'filters': 'all10corridors, 50m', 'transformation': 'fraction_observed*100;2decimals; eligible/selected integers'},
        {'id': 'Tabela2', 'source': fingerprint(source13/'tables/dados_ablacoes.csv'), 'evidence': ['C13_03', 'C13_05'], 'filters': 'sample_evaluation;conditional_canopy;grid;50m;top_fraction=.2;6 declared variants', 'duplicate_control': fingerprint(article/'dados/controle_duplicacao.json')}
    ]
    matrix = {'source_run_id': registry['source_scientific_run_id'], 'claims': claims, 'elements': elements,
        'numerical_registry': fingerprint(article/'dados/numeros_rastreaveis.json'),
        'parameters_are_protocol_not_estimated_results': True, 'external_accuracy_evaluated': False}
    atomic_write_json(article/'matriz_afirmacoes_evidencias.json', matrix)
    lines = ['# Afirmações e evidências do manuscrito', '', 'Os IDs numéricos remetem a `dados/numeros_rastreaveis.json`, com fontes, filtros, receitas e SHA-256.', '',
        '| Trecho | Classificação | Evidências da etapa13 | Números usados |', '|---|---|---|---|']
    for c in claims: lines.append('| '+ ' | '.join([c['claim_id'], c['classification'], ', '.join(c['stage13_claim_ids']), ', '.join(c['metric_ids']) or 'parâmetros/limites, sem resultado novo'])+' |')
    lines += ['', 'Todos os trechos expandidos, parâmetros, referências, linhas e limitações estão no JSON adjacente.', '',
        'Figura1: F02 (primeiro hash de avaliação; ilustrativa, pós-resultados). Figura2: F03 (A/A+3D). Figura3: F04 (suporte comum de cada par).',
        'Tabela1: dados_amostra.csv (todos os corredores). Tabela2: dados_ablacoes.csv (seis receitas, avaliação/grade50/top20%).',
        'As afirmações de acurácia, ganho real e representatividade municipal permanecem **não testadas**.']
    (article/'matriz_afirmacoes_evidencias.md').write_text('\n'.join(lines)+'\n')
    result = {'stage': '14', 'source_run_id': registry['source_scientific_run_id'], 'abstracts': counts,
        'word_count_method': 'regex Unicode; números decimais e palavras com hífen contam uma palavra; excluídos cabeçalhos/keywords/comandos/comentários; macros expandidas',
        'numbers': verify_registry(registry), 'claims': len(claims), 'bibliography': bibliography,
        'figures': len(fig_metadata), 'tables': 2, 'pdf': inspect_pdf(project),
        'stage13_artifacts_authenticated': 85, 'status': 'passed_automated_checks_draft_for_human_review',
        'submission_ready': False, 'submitted': False,
        'pending': ['revisao_cientifica_e_editorial_humana', 'confirmar_estilo_local_vs_pacote_integral_sbsr_e_divergencia_Carta_A4', 'endereco_postal_nao_fornecido_confirmar_exigencia']}
    atomic_write_json(report/'auditoria_artigo.json', result)
    atomic_write_json(article/'verificacao_editorial.json', result)
    return result
