from pathlib import Path
import json
import math
import os
import re
import shutil
import subprocess
import yaml
import numpy as np
import pandas as pd
from sbsr_lidar.storage import fingerprint,read_json,atomic_write_json


def escape_tex(value):
    chars={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_',
        '{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(chars.get(c,c) for c in str(value))


def display(value,decimals=None,english=False,scale=1):
    if value is None:raise ValueError('Número ausente não pode virar zero no artigo')
    value=float(value)*scale
    if not math.isfinite(value):raise ValueError('Número não finito não pode entrar no artigo')
    text=str(int(round(value))) if decimals is None else f'{value:.{decimals}f}'
    return text if english else text.replace('.',r'{,}')


def select_one(frame,filters):
    mask=np.ones(len(frame),bool)
    for key,value in filters.items():
        mask &= np.isclose(frame[key].to_numpy(dtype=float),value,rtol=0,atol=1e-12) if isinstance(value,float) else frame[key].eq(value).to_numpy()
    result=frame.loc[mask]
    if len(result)!=1:raise ValueError(f'Esperada uma linha para {filters}, obtidas{len(result)}')
    return result.iloc[0]


def authenticate13(project):
    m=read_json(project/'docs/manifesto_etapa13.json');snapshot=project/'relatorios/etapa14/entradas_etapa13';snapshot.mkdir(parents=True,exist_ok=True)
    for record in m['artifacts']:
        path=Path(record['path']);actual=path
        if path in [project/'docs/estado_projeto.json',project/'docs/decisoes_metodologicas.md']:
            actual=snapshot/path.name
            if not actual.exists():
                if fingerprint(path)!=record:raise ValueError(f'Snapshot da etapa13 não está disponível: {path}')
                shutil.copyfile(path,actual)
        found=fingerprint(actual)
        if (found['sha256'],found['bytes'])!=(record['sha256'],record['bytes']):raise ValueError(f'Artefato13 alterado: {path}')
    return m


def prepare_numbers(project):
    authenticate13(project)
    article=project/'artigo';pointer=read_json(project/'relatorios/etapa13/ultima_execucao.json');source=Path(pointer['output_root'])
    ev=read_json(source/'resultados_publicaveis.json');registry={}
    def add(key,value,decimals=None,scale=1,**provenance):
        registry[key]={'value':value,'decimals':decimals,'scale':scale,**provenance}
    for key,record in ev['metrics'].items():
        if isinstance(record['value'],(int,float)):
            decimals=None if isinstance(record['value'],int) else 4
            if 'difference_m' in key:decimals=3
            if 'rank_shift' in key:decimals=1
            add(key,record['value'],decimals,source=fingerprint(source/'resultados_publicaveis.json'),json_pointer='/metrics/'+key+'/value')
    add('corridors_total',registry['corridors_evaluation']['value']+registry['corridors_development']['value'],derived_from=['corridors_evaluation','corridors_development'],expression='corridors_evaluation+corridors_development')
    for key in ['observed_fraction_min','observed_fraction_max']:
        add(key+'_percent',ev['metrics'][key]['value'],2,100,source=fingerprint(source/'resultados_publicaveis.json'),json_pointer='/metrics/'+key+'/value')
    sample=pd.read_csv(source/'tables/dados_amostra.csv')
    for r in sample.itertuples():
        for column in ['eligible_50m','selected_50m']:
            add(r.corridor_id+'_'+column,int(getattr(r,column)),source=fingerprint(source/'tables/dados_amostra.csv'),filters={'corridor_id':r.corridor_id},column=column,aggregation='scalar')
        add(r.corridor_id+'_observed_percent',float(r.fraction_observed),2,100,source=fingerprint(source/'tables/dados_amostra.csv'),filters={'corridor_id':r.corridor_id},column='fraction_observed',aggregation='scalar')
    controls=pd.read_csv(source/'tables/dados_ablacoes.csv')
    base={'case':'sample_evaluation','scope':'conditional_canopy','family':'grid','scale_m':50.,'top_fraction':.2}
    variants=[('weight0','I6/I7',0.,'A_plus_3D__I6_I7__Vplus__w0'),('weight025','I6/I7',.25,'A_plus_3D__I6_I7__Vplus__w0.25'),
        ('primary','I6/I7',.5,'A_plus_3D__I6_I7__Vplus__w0.5'),('weight075','I6/I7',.75,'A_plus_3D__I6_I7__Vplus__w0.75'),
        ('reverse','IQR oposto',.5,'A_plus_3D__I6_I7__Vminus__w0.5'),('height_only','I6 isolado',.5,'A_plus_3D__I6_only__height_only__w0.5')]
    rows=[]
    for label,name,weight,variant in variants:
        filters={**base,'variant_id':variant};row=select_one(controls,filters)
        for column,short in [('spearman_rho','rho'),('jaccard_exact','jaccard')]:
            add('control_'+label+'_'+short,float(row[column]),4,source=fingerprint(source/'tables/dados_ablacoes.csv'),filters=filters,column=column,aggregation='scalar')
        rows.append([name,display(weight,2),r'\Ev{control_'+label+'_rho}',r'\Ev{control_'+label+'_jaccard}'])
    scores=pd.read_parquet(Path(ev['sources']['escores_rankings']['path']))
    common={'case':'sample_evaluation','scope':'conditional_canopy','family':'grid','scale_m':50.}
    ids={}
    for variant in ['A_plus_3D__I6_only__height_only__w0.5','A_plus_3D__I6_duplicate__duplicate_control__w0.5']:
        data=scores
        for key,val in {**common,'variant_id':variant}.items():data=data.loc[data[key].eq(val)]
        ids[variant]=data.set_index('unit_id').score.sort_index()
    a,b=ids.values()
    if not a.index.equals(b.index) or not np.array_equal(a.to_numpy(),b.to_numpy()):raise ValueError('Controle de duplicação não coincide')
    atomic_write_json(article/'dados/controle_duplicacao.json',{'identical_scores':True,'n':len(a),'source':ev['sources']['escores_rankings'],
        'filters_common':common,'variants':list(ids),'comparison':'equal source scores on identical sorted unit_IDs'})
    physical=yaml.safe_load((project/'configs/terreno_congelado_etapa04.yaml').read_text());design=yaml.safe_load((project/'configs/amostra_pycrown_exploratoria_v0_3_0.yaml').read_text())
    p={}
    def param(key,value,source_path,pointer,decimals=None,scale=1):
        p[key]={'value':value,'source':fingerprint(project/source_path),'pointer':pointer,'decimals':decimals,'scale':scale}
    dpath='configs/amostra_pycrown_exploratoria_v0_3_0.yaml';ppath='configs/terreno_congelado_etapa04.yaml'
    for key,field in [('halo','halo_m'),('window','window_size_m'),('resolution','primary_resolution_m'),('height','primary_height_m'),
        ('detection_radius','primary_detection_radius_m'),('crown_radius','primary_crown_radius_m'),('target_per_corridor','target_units_per_corridor'),('seed','seed')]:param(key,design[field],dpath,'/'+field)
    param('tin_radius',physical['terrain']['maximum_distance_m'],ppath,'/terrain/maximum_distance_m')
    param('epsg',physical['grid']['epsg'],ppath,'/grid/epsg')
    for key,field in [('area_min','minimum_unit_area_m2'),('canopy_min','minimum_canopy_area_m2'),('returns_min','minimum_vegetation_returns')]:param(key,physical['support'][field],ppath,'/support/'+field)
    param('observed_min',physical['support']['minimum_observed_fraction'],ppath,'/support/minimum_observed_fraction',scale=100)
    param('primary_weight',physical['comparison']['primary_vertical_weight'],ppath,'/comparison/primary_vertical_weight',decimals=1)
    param('top_fraction',physical['comparison']['primary_top_fraction'],ppath,'/comparison/primary_top_fraction',decimals=1)
    param('top_percent',physical['comparison']['primary_top_fraction'],ppath,'/comparison/primary_top_fraction',scale=100)
    param('cover_tolerance',physical['comparison']['similar_cover_tolerance'],ppath,'/comparison/similar_cover_tolerance',decimals=2)
    param('area_ratio',physical['comparison']['maximum_observed_area_ratio'],ppath,'/comparison/maximum_observed_area_ratio')
    # Anos e matriz são fatos do protocolo, não resultados estimados.
    for key,value in [('lidar_year',2020),('geometry_year',2026),('main_scale',50),('scenario_count',12)]:
        p[key]={'value':value,'source':fingerprint(project/'docs/protocolo_pycrown_v0_3_0.md'),'basis':'declared temporal scope / scenario matrix / primary grid','decimals':None,'scale':1}
    p['scales']={'value':'25/50/100','source':fingerprint(project/'docs/protocolo_pycrown_v0_3_0.md'),'basis':'predefined grid scales','literal':True}
    commands=[r'% Gerado por scripts/preparar_artigo_etapa14.py; não editar números.',r'\newcommand{\Ev}[1]{\csname ev@#1\endcsname}',
        r'\newcommand{\En}[1]{\csname en@#1\endcsname}',r'\newcommand{\Par}[1]{\csname par@#1\endcsname}']
    for key,record in registry.items():
        for prefix,english in [('ev',False),('en',True)]:
            commands.append(r'\expandafter\def\csname '+prefix+'@'+key+r'\endcsname{'+display(record['value'],record['decimals'],english,record['scale'])+'}')
    for key,record in p.items():
        value=record['value'] if record.get('literal') else display(record['value'],record.get('decimals'),scale=record.get('scale',1))
        commands.append(r'\expandafter\def\csname par@'+key+r'\endcsname{'+value+'}')
    (article/'numeros.tex').write_text('\n'.join(commands)+'\n')
    atomic_write_json(article/'dados/numeros_rastreaveis.json',{'source_stage13_run_id':pointer['run_id'],'source_scientific_run_id':ev['source_run_id'],
        'metrics':registry,'parameters':p,'external_accuracy_evaluated':False})
    lines=[r'\begin{tabular}{lrrr}',r'\hline',r'Corredor & $O/P$(\%) & $n_e$ & $n_s$ \\',r'\hline']
    for r in sample.sort_values('corridor_id').itertuples():
        lines.append(escape_tex(r.corridor_id)+('*' if r.role=='development' else '')+r' & \Ev{'+r.corridor_id+r'_observed_percent} & \Ev{'+r.corridor_id+r'_eligible_50m} & \Ev{'+r.corridor_id+r'_selected_50m} \\')
    (article/'tabelas/amostra.tex').write_text('\n'.join(lines+[r'\hline',r'\end{tabular}'])+'\n')
    (article/'tabelas/controles.tex').write_text('\n'.join([r'\begin{tabular}{lrrr}',r'\hline',r'Receita & $w$ & $\rho$ & $J$ \\',r'\hline',
        *[' & '.join(row)+r' \\' for row in rows],r'\hline',r'\end{tabular}'])+'\n')
    sample.to_csv(article/'dados/amostra_completa.csv',index=False)
    copies=[]
    for name in ['F02_exemplo_2D_H','F03_rankings','F04_sensibilidade']:
        a=source/'figures'/f'{name}.pdf';b=article/'figuras'/a.name;shutil.copyfile(a,b);copies.append({'source':fingerprint(a),'copy':fingerprint(b)})
    for name in ['resultados_publicaveis.json','selecao_exemplos.json']:
        shutil.copyfile(source/name,article/'dados'/name)
    return {'source_stage13':pointer,'figure_copies':copies,'numerical_registry':fingerprint(article/'dados/numeros_rastreaveis.json')}


def prepare_authors(project):
    data=yaml.safe_load((project/'artigo/autoria.yaml').read_text());authors=data.get('authors',[])
    if not authors:raise ValueError('Autoria não informada')
    names='; '.join(escape_tex(a['name']) for a in authors);affiliations=r'\\'.join(dict.fromkeys(escape_tex(a['affiliation']) for a in authors))
    contact=escape_tex(authors[data.get('corresponding_author',0)]['email'])
    (project/'artigo/autores.tex').write_text(r'% Metadados fornecidos pelo usuário.'+'\n'+r'\newcommand{\AutoriaNomes}{'+names+'}\n'+r'\newcommand{\AutoriaAfiliacoes}{'+affiliations+'}\n'+r'\newcommand{\AutoriaContato}{'+contact+'}\n')
    return {'authors':authors,'source':data['source'],'postal_address_provided':all(bool(a.get('address')) for a in authors),'human_review_completed':bool(data['human_review_completed'])}


def prepare_bibliography(project):
    records=read_json(project/'relatorios/etapa14/referencias_crossref.json')['entries'];bydoi={r['doi'].lower():r for r in records}
    mapping=[('alonzo2014','10.1016/j.rse.2014.03.018'),('dalponte2016','10.1111/2041-210x.12575'),
        ('zorner2018','10.3390/f9110702'),('hurlbert1984','10.2307/1942661')]
    entries=[];provenance=[]
    for key,doi in mapping:
        row=bydoi[doi];authors=' and '.join(a['family']+', '+a.get('given','') for a in row['author'])
        title=escape_tex(row['title'][0].replace('‐','-'))
        fields={'author':authors,'title':'{'+title+'}','journal':row['container_title'][0],
            'year':str(row['year']['date-parts'][0][0]),'volume':row['volume'],'pages':row['page'].replace('-','--'),
            'doi':doi,'note':r'\url{https://doi.org/'+doi+'}'}
        if row.get('issue'):fields['number']=row['issue']
        entries.append('@article{'+key+',\n'+',\n'.join('  '+k+' = {'+v+'}' for k,v in fields.items())+'\n}\n')
        provenance.append({'key':key,'doi':doi,'title':row['title'][0],'publisher_metadata':row['raw'],'verified_on':'2026-10-26','primary_url':'https://doi.org/'+doi})
    datacite=read_json(project/'relatorios/etapa14/pycrown_datacite.json')['data']['attributes']
    authors=' and '.join(c['familyName']+', '+c['givenName'] for c in datacite['creators'])
    entries.append('@misc{pycrown,\n  author = {'+authors+'},\n  title = {{PyCrown}: Fast raster-based individual tree segmentation for {LiDAR} data},\n  year = {'+str(datacite['publicationYear'])+'},\n  howpublished = {'+datacite['publisher']+'},\n  note = {Software. \\url{https://doi.org/10.7931/M0SR-DN55}}\n}\n')
    provenance.append({'key':'pycrown','doi':'10.7931/M0SR-DN55','primary_url':datacite['url'],'registry':'DataCite','record':fingerprint(project/'relatorios/etapa14/pycrown_datacite.json'),'verified_on':'2026-10-26'})
    entries.append('@misc{geosampa,\n  author = {{Prefeitura do Município de São Paulo}},\n  title = {{GeoSampa: Mapa Digital da Cidade de São Paulo}},\n  howpublished = {\\url{https://novogeosampa.prefeitura.sp.gov.br/}},\n  note = {Acesso em 26 out. 2026}\n}\n')
    provenance.append({'key':'geosampa','primary_url':'https://novogeosampa.prefeitura.sp.gov.br/','type':'official_data_portal','verified_on':'2026-10-26','publication_year_not_inferred':True})
    (project/'artigo/referencias.bib').write_text('\n'.join(entries))
    atomic_write_json(project/'artigo/dados/referencias_verificadas.json',{'references':provenance,'no_demonstration_references_used':True})


def compile_article(project,only_cached=False):
    article=project/'artigo';env=os.environ.copy();env['TECTONIC_CACHE_DIR']=str(project/'.tools/tectonic/cache')
    executable=project/'.tools/tectonic/tectonic'
    command=[str(executable),'--keep-logs','--keep-intermediates','--untrusted']
    if only_cached:command+=['--only-cached']
    command+=['manuscrito.tex']
    with (project/'relatorios/etapa14/compilacao_stdout.txt').open('w') as log:
        process=subprocess.run(command,cwd=article,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    if process.returncode:raise RuntimeError('Compilação falhou; consultar relatorios/etapa14/compilacao_stdout.txt')
    subprocess.run(['pdftotext','-layout',str(article/'manuscrito.pdf'),str(article/'manuscrito_texto_extraido.txt')],check=True)
    return {'command':command,'cache_dir':env['TECTONIC_CACHE_DIR'],'compiler':fingerprint(executable),'pdf':fingerprint(article/'manuscrito.pdf')}
