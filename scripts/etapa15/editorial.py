"""Cópia revisada separada do original da etapa14, compilação e provas."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
from xml.etree import ElementTree as ET

from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json
from etapa14.audit import expand_numbers, abstract_counts, bibliography_checks, claims_matrix, MACRO


def compile_at(project, article, log, only_cached=True):
    env = os.environ.copy(); env['TECTONIC_CACHE_DIR'] = str(project/'.tools/tectonic/cache')
    cmd = [str(project/'.tools/tectonic/tectonic'), '--untrusted', '--keep-logs', '--keep-intermediates']
    if only_cached: cmd.append('--only-cached')
    cmd.append('manuscrito.tex')
    with log.open('w') as f: r = subprocess.run(cmd, cwd=article, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=300)
    if r.returncode: raise RuntimeError(f'Falha de compilação: {log}')
    subprocess.run(['pdftotext', '-layout', str(article/'manuscrito.pdf'), str(article/'manuscrito_texto_extraido.txt')], check=True)
    return {'command': cmd, 'cwd': str(article), 'pdf': fingerprint(article/'manuscrito.pdf')}


def clone_and_rebuild(project, out):
    manifest = read_json(project/'docs/manifesto_etapa14.json')
    destination = project/'artigo/revisao_etapa15'
    if destination.exists(): raise ValueError('Revisão já preparada; compilar com --compile-only para preservar edições')
    destination.mkdir()
    for record in manifest['artifacts']:
        path = Path(record['path'])
        if path.is_relative_to(project/'artigo'):
            if fingerprint(path) != record: raise ValueError(f'Original14 alterado: {path}')
            copied = destination/path.relative_to(project/'artigo'); copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, copied)
    # Compilar o pacote original em diretório portátil; comparar conteúdo, não data do PDF.
    with tempfile.TemporaryDirectory(prefix='sbsr_etapa15_latex_') as temporary:
        work = Path(temporary)/'artigo'; shutil.copytree(destination, work)
        compile_at(project, work, out/'compilacao_original_em_tmp.txt')
        expected = (project/'artigo/manuscrito_texto_extraido.txt').read_text()
        if (work/'manuscrito_texto_extraido.txt').read_text() != expected: raise ValueError('Texto não reproduzido pela compilação isolada')
        rebuilt = {'original': fingerprint(project/'artigo/manuscrito.pdf'), 'isolated_pdf': fingerprint(work/'manuscrito.pdf'),
            'extracted_text_exact': True, 'temporary_path': str(work), 'new_machine_tested': False,
            'scope': 'different_temporary_directory_same_machine_no_external_HD_needed_for_LaTeX', 'cache_only': True}
    rebuilt['temporary_directory_removed'] = not Path(temporary).exists()
    atomic_write_json(out/'reproducao_documento.json', rebuilt)
    source = destination/'manuscrito.tex'; before = source.read_text(); after = before
    after = after.replace(r'e \Par{returns_min} retornos vegetais', r'e $\geq\Par{returns_min}$ retornos vegetais')
    after = after.replace('A comparação usou Spearman com posições médias', 'Os escores foram arredondados a 12 casas decimais para os empates. A comparação usou Spearman com posições médias')
    after = after.replace('Os indicadores longitudinais B/C ficaram indisponíveis porque os eixos da nova amostra não foram revalidados; A+3D não foi renomeado C.', 'Análises longitudinais foram excluídas porque os eixos da nova amostra não foram revalidados.')
    after = after.replace('São variações uma a uma; o MDT não foi rarefeito.', 'São variações uma a uma, com uma semente de rarefação; o MDT não foi rarefeito.')
    if MACRO.findall(before) != MACRO.findall(after): raise ValueError('Correção editorial alterou referências numéricas')
    source.write_text(after)
    style = destination/'formato_sbsr_local.sty'; t = style.read_text()
    t = t.replace('Rascunho para revisão dos autores — não submetido', 'Rascunho revisado para apreciação do autor — não submetido')
    style.write_text(t)
    changes = [
        {'id': 'C15_01', 'location': 'manuscrito.tex, Dados/domínio/seleção', 'change': 'Explicitar >=50 retornos, em lugar da redação ambígua 50 retornos', 'scientific_result_changed': False},
        {'id': 'C15_02', 'location': 'manuscrito.tex, Ablação/sensibilidades', 'change': 'Documentar arredondamento a12 casas que o código já usava para empates', 'scientific_result_changed': False},
        {'id': 'C15_03', 'location': 'manuscrito.tex, Ablação/sensibilidades', 'change': 'Substituir símbolos B/C não definidos no artigo por exclusão explícita de análises longitudinais', 'scientific_result_changed': False},
        {'id': 'C15_04', 'location': 'manuscrito.tex, Ablação/sensibilidades', 'change': 'Esclarecer que a rarefação usou somente uma semente, sem repetições estocásticas', 'scientific_result_changed': False},
        {'id': 'C15_05', 'location': 'formato_sbsr_local.sty', 'change': 'Identificar a cópia como rascunho revisado para apreciação do autor', 'scientific_result_changed': False}]
    atomic_write_json(out/'correcoes_editoriais.json', {'source': fingerprint(project/'artigo/manuscrito.tex'), 'reviewed': fingerprint(source), 'changes': changes, 'same_numerical_macros_in_same_order': True})
    return destination


def check_pdf_elements(paper_text):
    """Confira legendas no texto; recortes invisíveis ainda exigem inspeção visual."""
    figures = set(int(x) for x in re.findall(r'Figura\s+(\d+)\s*:', paper_text))
    tables = set(int(x) for x in re.findall(r'Tabela\s+(\d+)\s*:', paper_text))
    if figures != {1, 2, 3} or tables != {1, 2}:
        raise ValueError(f'Elementos ausentes do PDF: figuras={sorted(figures)}, tabelas={sorted(tables)}')
    return {'figures': sorted(figures), 'tables': sorted(tables)}


def inspect(project, article, out):
    registry = read_json(article/'dados/numeros_rastreaveis.json'); source = (article/'manuscrito.tex').read_text()
    expand_numbers(source, registry); counts = abstract_counts(source, registry)
    refs = bibliography_checks(source, (article/'referencias.bib').read_text())
    claims = claims_matrix(source, registry, read_json(article/'dados/resultados_publicaveis.json')['claims'])
    matrix = read_json(article/'matriz_afirmacoes_evidencias.json'); matrix['claims'] = claims; matrix['review_stage'] = '15'
    atomic_write_json(article/'matriz_afirmacoes_evidencias.json', matrix)
    info = subprocess.check_output(['pdfinfo', str(article/'manuscrito.pdf')], text=True); (out/'pdfinfo.txt').write_text(info)
    pages = int(re.search(r'Pages:\s*(\d+)', info).group(1))
    if pages != 4 or 'A4' not in info: raise ValueError('Revisão fora de quatro páginas A4')
    fonts = subprocess.check_output(['pdffonts', str(article/'manuscrito.pdf')], text=True); (out/'fontes_pdf.txt').write_text(fonts)
    if 'TimesNewRoman' not in fonts or any(line.split()[-5] != 'yes' for line in fonts.splitlines()[2:]): raise ValueError('Fonte ausente/não incorporada')
    log = (article/'manuscrito.log').read_text()
    critical = re.findall(r'^.*(?:Overfull|undefined|Missing character|LaTeX Error|^!).*$', log, re.M | re.I)
    if critical: raise ValueError(f'Compilação com mensagens críticas: {critical}')
    bbox = out/'caixas_pdf.html'; subprocess.run(['pdftotext', '-bbox', str(article/'manuscrito.pdf'), str(bbox)], check=True)
    ns = {'x': 'http://www.w3.org/1999/xhtml'}; bounds = []
    for i, page in enumerate(ET.parse(bbox).findall('.//x:page', ns), 1):
        words = page.findall('.//x:word', ns)
        b = {a: op(float(w.attrib[a]) for w in words)*25.4/72 for a, op in [('xMin', min), ('xMax', max), ('yMin', min), ('yMax', max)]}
        if b['xMin'] < 18 or b['xMax'] > 198 or b['yMax'] > 255 or any(float(w.attrib['yMin'])*25.4/72 > 260 for w in words): raise ValueError('Texto fora da caixa ou rodapé numerado')
        bounds.append({'page': i, 'visible_text_bounds_mm': b})
    paper_text = (article/'manuscrito_texto_extraido.txt').read_text()
    rendered_elements = check_pdf_elements(paper_text)
    if 'Carlos Henrique de Moura Silva' not in info or 'carlos-henrique.silva@serpro.gov.br' not in paper_text: raise ValueError('Autoria incorreta')
    figures = [x for x in re.findall(r'\\includegraphics\[[^]]*\]\{([^}]+)\}', source)]
    for name in figures:
        a = fingerprint(article/name); b = fingerprint(project/'artigo'/name)
        if a['sha256'] != b['sha256']: raise ValueError('Figura alterada sem regeneração')
    proof = out/'provas'; proof.mkdir(exist_ok=True)
    subprocess.run(['pdftoppm', '-r', '120', '-png', str(article/'manuscrito.pdf'), str(proof/'pagina')], check=True)
    result = {'stage': '15', 'pdf': fingerprint(article/'manuscrito.pdf'), 'pages': pages, 'abstracts': counts,
        'bibliography': refs, 'figures': len(figures), 'tables': len(re.findall(r'\\begin\{table\}', source)),
        'all_fonts_embedded': True, 'Times_New_Roman_present': True, 'critical_latex_messages': critical,
        'elements_actually_captioned_in_pdf': rendered_elements,
        'underfull_notices': log.count('Underfull'), 'page_numbers': False, 'page_bounds': bounds,
        'title_visible_top_mm': bounds[0]['visible_text_bounds_mm']['yMin'],
        'source_format': 'A4;10pt body;14pt title;9pt bold captions;86mm columns;6mm gap;178x229mm text',
        'optical_glyph_tolerance_mm': 1, 'same_result_macros_and_figures': True,
        'human_author_approval': False, 'full_official_style_obtained': False, 'submission_ready': False}
    atomic_write_json(out/'auditoria_editorial.json', result)
    atomic_write_json(article/'verificacao_editorial.json', result)
    return result
