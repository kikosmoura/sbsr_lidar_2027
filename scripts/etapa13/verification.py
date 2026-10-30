"""Auditoria independente do pacote de apresentação e das receitas numéricas."""
from pathlib import Path
import ast
import json
import re
import subprocess
import numpy as np
import pandas as pd
from PIL import Image
from scipy.stats import rankdata
from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json
from .evidence import evaluate_recipe,choose_examples


def arithmetic(expression,values):
    def run(node):
        if isinstance(node,ast.Expression):return run(node.body)
        if isinstance(node,ast.Name):return values[node.id]
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):return node.value
        if isinstance(node,ast.BinOp):
            a,b=run(node.left),run(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
        raise ValueError('Expressão não aritmética')
    return run(ast.parse(expression,mode='eval'))


def verify(root):
    manifest=read_json(root/'manifest.json');evidence=read_json(root/'resultados_publicaveis.json');checks=[]
    def check(name,condition,**details):
        checks.append({'check':name,'ok':bool(condition),**details})
        if not condition:raise ValueError(f'Etapa13 {name}: {details}')
    check('completed_generation',manifest['status']=='completed')
    check('output_hashes',all(fingerprint(Path(p['path']))==p for p in manifest['outputs']),count=len(manifest['outputs']))
    frames={}
    for name,source in evidence['sources'].items():
        path=Path(source['path']);check('source_hash:'+name,fingerprint(path)==source)
        frames[name]=pd.read_csv(path) if path.suffix=='.csv' else pd.read_parquet(path)
    values={key:metric['value'] for key,metric in evidence['metrics'].items()}
    for key,metric in evidence['metrics'].items():
        if 'recipe' in metric:value=evaluate_recipe(frames[metric['recipe']['source']],metric['recipe'])
        elif 'derived_from' in metric:value=arithmetic(metric['expression'],values)
        else:
            source=read_json(Path(metric['source_fingerprint']['path']));value=source
            for token in metric['json_pointer'].strip('/').split('/'):value=value[token]
        expected=metric['value'];ok=value==expected if not isinstance(value,(int,float)) or value is None else np.isclose(value,expected,rtol=1e-11,atol=1e-9)
        check('metric_recipe:'+key,ok,value=value)
    ranks=pd.read_csv(root/'tables/dados_rankings_avaliacao.csv');n=len(ranks);k=int(values['primary_k'])
    check('same_primary_cohort',set(ranks.unit_id)==set(frames['coorte_selecionada'].loc[frames['coorte_selecionada'].role.eq('evaluation'),'unit_id']))
    a=set(ranks.nsmallest(k,'rank_ordinal_A').unit_id);b=set(ranks.nsmallest(k,'rank_ordinal_3D').unit_id)
    intersection=len(a&b);union=len(a|b)
    check('top_intersection_recomputed',intersection==values['primary_top_intersection_n'])
    check('jaccard_recomputed',np.isclose(intersection/union,values['primary_jaccard_exact']))
    rho=float(np.corrcoef(rankdata(ranks.rank_mean_A),rankdata(ranks.rank_mean_3D))[0,1])
    check('spearman_recomputed_with_ties',np.isclose(rho,values['primary_spearman_rho']))
    for row in ranks.itertuples():
        actual='kept' if row.unit_id in a&b else 'lost' if row.unit_id in a else 'gained' if row.unit_id in b else 'neither'
        if actual!=row.disagreement:raise ValueError('Categoria top inconsistente')
    check('top_categories_no_omission',ranks.groupby('disagreement').size().sum()==n)
    examples=read_json(root/'selecao_exemplos.json');chosen=choose_examples(ranks,manifest['config']['example_selection'])
    check('balanced_hash_selection',[(e['status'],e['unit_id'],e['group_n']) for e in chosen]==[(e['status'],e['unit_id'],e['group_n']) for e in examples['strata']])
    check('main_example_hash_selection',examples['main']['unit_id']==ranks.sort_values(['selection_hash','unit_id']).iloc[0].unit_id)
    figures=read_json(root/'indice_figuras_tabelas.json')['items'];scale=[]
    for record in figures:
        check(record['figure_id']+':physical_width',any(np.isclose(record['width_mm'],w) for w in [86,178]))
        check(record['figure_id']+':text_legible',record['minimum_font_pt']>=7 and not record['text_outside_canvas'])
        check(record['figure_id']+':no_overlap_or_missing_glyphs',not record['text_overlaps'] and not record['missing_glyphs'])
        files={Path(p['path']).suffix:Path(p['path']) for p in record['files']}
        with Image.open(files['.png']) as image:
            expected_px=record['width_mm']/25.4*600
            check(record['figure_id']+':PNG_resolution',abs(image.width-expected_px)<=1 and image.info['dpi'][0]>=599)
        info=subprocess.run(['pdfinfo',str(files['.pdf'])],check=True,capture_output=True,text=True).stdout
        width_pt=float(re.search(r'Page size:\s+([0-9.]+)',info).group(1))
        check(record['figure_id']+':PDF_width',abs(width_pt*25.4/72-record['width_mm'])<.02)
        fonts=subprocess.run(['pdffonts',str(files['.pdf'])],check=True,capture_output=True,text=True).stdout
        check(record['figure_id']+':PDF_embedded_fonts','TrueType' in fonts and 'yes' in fonts)
        if 'window_data' in record:
            with np.load(record['window_data']['path']) as data:
                obs,labels,cat=data['observation'],data['labels'],data['categories']
                check(record['figure_id']+':NoData_distinct',np.array_equal(cat==0,obs==255) and np.array_equal(cat==2,(obs!=1)&(obs!=255)))
                check(record['figure_id']+':canopy_only_on_support',np.array_equal(cat==3,(obs==1)&(labels>0)))
            check(record['figure_id']+':native_height_not_clipped',record['height_cells_clipped_above_maximum']==0)
            check(record['figure_id']+':CRS',record['epsg']==31983)
            scale.append(record['height_scale_m'])
    check('common_height_scale_across_examples',all(s==scale[0] for s in scale))
    check('no_invented_inference',not evidence['inference']['p_values'] and not evidence['inference']['confidence_intervals'])
    check('all_claims_classified',all(c['classification'] in {'sustentada','parcialmente_sustentada','exploratoria','nao_testada'} for c in evidence['claims']))
    check('all_claim_metrics_resolve',all(all(i in values for i in c['metric_ids']) for c in evidence['claims']))
    return {'ok':all(c['ok'] for c in checks),'checks':checks,'source_run_id':manifest['source_run_id'],
        'stage13_run_id':manifest['run_id'],'asserted_external_accuracy':False,'LAZ_reprocessed':False}
