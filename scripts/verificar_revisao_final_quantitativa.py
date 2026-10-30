"""Auditoria do par máximo, das seleções e do PDF0.3.3; sem alterar históricos."""
from pathlib import Path
import json
import re
import subprocess
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json
from verificar_revisao_interpretacao import verify_history
from etapa14.audit import verify_registry,abstract_counts,bibliography_checks,expand_numbers


def history(project,out):
    old=Path(read_json(project/'relatorios/revisao_interpretacao/ultima_execucao.json')['output_root'])
    hist=verify_history(project,old)
    mutable={project/'docs'/name for name in ['estado_projeto.json','decisoes_metodologicas.md','RETOMADA_PROJETO.md']}
    mutable.add(project/'artigo/versao_atual.json')
    records=read_json(project/'docs/manifesto_revisao_interpretacao.json')['artifacts']
    for record in records:
        source=Path(record['path']);actual=out/'entradas_v0_3_2'/source.name if source in mutable else source
        found=fingerprint(actual)
        if (found['bytes'],found['sha256'])!=(record['bytes'],record['sha256']):raise ValueError(f'Histórico0.3.2 mudou: {source}')
    hist['authenticated_by_stage']['0.3.2']=len(records)
    return hist


def verify(project,out):
    hist=history(project,out);provenance=read_json(out/'fontes_utilizadas.json')
    for fp in provenance['inputs']+provenance['code']:
        if fingerprint(Path(fp['path']))!=fp:raise ValueError(f'Fonte da conferência mudou: {fp["path"]}')
    r=read_json(out/'resultados.json');records=[]
    for i,u in enumerate([r['unit_i'],r['unit_j']]):
        frame=pd.read_parquet(out/f'retornos_unidade_{i+1}.parquet');selected=frame.loc[frame.retained_original]
        if frame.duplicated(['source_tile','source_point_index']).any():raise ValueError('Registros repetidos no diagnóstico')
        if not selected.observed.all() or not selected.inside_estimated_canopy.all():raise ValueError('Retorno fora de suporte/máscara')
        h=selected.h.to_numpy();q=pd.Series(h).quantile([.25,.75,.95],interpolation='linear')
        expected=r['units'][u]
        if len(selected)!=expected['n'] or abs(q.loc[.95]-expected['P95_m'])>1e-9 or abs(q.loc[.75]-q.loc[.25]-expected['IQR_m'])>1e-9:
            raise ValueError('Quantis do par não reproduzidos')
        if not np.allclose(h,selected.z_absolute-selected.terrain_z,rtol=0,atol=1e-9):raise ValueError('Fórmula H divergente')
        records.append(len(selected))
    if r['external_semantic_or_altimetric_validation_performed'] or not r['max_pair_retained_in_primary_results']:raise ValueError('Interpretação indevida da conferência')
    selection=pd.read_csv(out/'permanencia_selecoes.csv')
    if len(selection)!=11 or not selection.n.eq(68).all() or not selection.k.eq(14).all():raise ValueError('Universo das seleções mudou')
    if not np.allclose(selection.replacement_fraction,selection.lost_n/selection.k,rtol=0,atol=1e-12):raise ValueError('Jaccard confundido com substituição')
    if not np.allclose(selection.jaccard,selection.shared_n/(2*selection.k-selection.shared_n),rtol=0,atol=1e-12):raise ValueError('Interseção/união divergente')
    article=project/'artigo/revisao_final_v0_3_3';prior=project/'artigo/revisao_interpretacao_v0_3_2'
    registry=read_json(article/'dados/numeros_rastreaveis.json');old=read_json(prior/'dados/numeros_rastreaveis.json')
    for key,value in old['metrics'].items():
        if registry['metrics'][key]!=value:raise ValueError('Resultado numérico anterior alterado')
    numerical=verify_registry(registry);source=(article/'manuscrito.tex').read_text()
    abstracts=abstract_counts(source,registry);refs=bibliography_checks(source,(article/'referencias.bib').read_text())
    for p in (article/'tabelas').glob('*.tex'):
        expand_numbers(p.read_text(),registry)
        if p.read_bytes()!=(prior/'tabelas'/p.name).read_bytes():raise ValueError('Tabela primária alterada')
    for name in ['F02_exemplo_2D_H','F05_pares_horizontais','F06_estabilidade_coorte_fixa']:
        if (article/f'figuras/{name}.pdf').read_bytes()!=(prior/f'figuras/{name}.pdf').read_bytes():raise ValueError('Figura primária alterada')
    conclusion=source.split(r'\section{Conclusões}',1)[1].split(r'\renewcommand',1)[0]
    for key in ['comp_pairs','comp_units','comp_p95','comp_disjoint','comp_disjoint_p95','comp_fixed','comp_rhomin','comp_rhomax','comp_jmin','comp_jmax','fin_min_replaced','fin_max_replaced','comp_k']:
        if r'\Ev{'+key+'}' not in conclusion:raise ValueError(f'Achado quantitativo ausente da conclusão: {key}')
    pdf=article/'manuscrito.pdf';info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);(out/'pdfinfo.txt').write_text(info)
    pages=int(re.search(r'Pages:\s*(\d+)',info).group(1))
    if pages!=4 or 'A4' not in info:raise ValueError('PDF fora de quatro páginas A4')
    fonts=subprocess.check_output(['pdffonts',str(pdf)],text=True);(out/'fontes_pdf.txt').write_text(fonts)
    if 'TimesNewRoman' not in fonts or any(row.split()[-5]!='yes' for row in fonts.splitlines()[2:]):raise ValueError('Fontes não incorporadas')
    log=(article/'manuscrito.log').read_text();critical=re.findall(r'^.*(?:Overfull|undefined|Missing character|LaTeX Error|^!).*$',log,re.M|re.I)
    if critical:raise ValueError(f'Mensagem crítica na compilação: {critical}')
    text=subprocess.check_output(['pdftotext','-layout',str(pdf),'-'],text=True)
    for element in ['Figura','Tabela']:
        if set(map(int,re.findall(element+r'\s+(\d+)\s*:',text)))!={1,2,3}:raise ValueError(f'{element} ausente do PDF')
    bbox=out/'caixas_pdf.html';subprocess.run(['pdftotext','-bbox',str(pdf),str(bbox)],check=True)
    bounds=[];ns={'x':'http://www.w3.org/1999/xhtml'}
    for page in ET.parse(bbox).findall('.//x:page',ns):
        words=page.findall('.//x:word',ns)
        b={k:op(float(w.attrib[k]) for w in words)*25.4/72 for k,op in [('xMin',min),('xMax',max),('yMin',min),('yMax',max)]}
        if b['xMin']<18 or b['xMax']>198 or b['yMax']>255:raise ValueError(f'Conteúdo fora da caixa: {b}')
        bounds.append(b)
    audit={'historical_counts':hist['authenticated_by_stage'],'reconstructed_return_counts':records,
        'top_lists_reconstructed':11,'previous_158_article_values_unchanged':True,
        'numerical_registry':numerical,'abstracts':abstracts,'bibliography':refs,
        'pdf':fingerprint(pdf),'source':fingerprint(article/'manuscrito.tex'),'pages':pages,'figures':3,'tables':3,
        'critical_latex_messages':critical,'all_fonts_embedded':True,'bounds_mm':bounds,
        'external_validation_performed':False,'author_approved':False,'submission_ready':False}
    atomic_write_json(out/'verificacao.json',audit)
    return audit


if __name__=='__main__':
    project=Path(__file__).resolve().parents[1];out=Path(read_json(project/'relatorios/revisao_final_quantitativa/ultima_execucao.json')['output_root'])
    r=verify(project,out);print(json.dumps({k:v for k,v in r.items() if k not in ['abstracts','bounds_mm']},ensure_ascii=False,indent=2))
