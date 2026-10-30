"""Extração de números com receitas executáveis e proveniência por arquivo."""
from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
import geopandas as gpd
import yaml
from sbsr_lidar.storage import fingerprint,read_json,atomic_write_json

MUTABLE={'docs/estado_projeto.json','docs/decisoes_metodologicas.md'}


def native(value):
    if isinstance(value,dict):return {str(k):native(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [native(v) for v in value]
    if isinstance(value,np.generic):return native(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def subset(frame,filters):
    keep=np.ones(len(frame),dtype=bool)
    for key,value in filters.items():
        if isinstance(value,float):keep &= np.isclose(frame[key].to_numpy(dtype=float),value,rtol=0,atol=1e-12)
        else:keep &= frame[key].eq(value).to_numpy()
    return frame.loc[keep].copy()


def evaluate_recipe(frame,recipe):
    data=subset(frame,recipe.get('filters',{}));op=recipe['aggregation'];column=recipe.get('column')
    if op=='count':return int(len(data))
    if op=='nunique':return int(data[column].nunique())
    if op=='scalar':
        if len(data)!=1:raise ValueError(f'Receita escalar exige uma linha, recebeu {len(data)}')
        return native(data.iloc[0][column])
    if op in {'sum','min','max','median'}:return native(getattr(data[column],op)())
    raise ValueError(f'Agregação não declarada: {op}')


def choose_examples(ranks,rule):
    examples=[]
    for status,g in ranks.groupby('disagreement',sort=True):
        row=g.sort_values(['selection_hash','unit_id']).iloc[0]
        examples.append({'status':status,'group_n':len(g),**native(row.to_dict()),
            'selection_rule':rule,'illustrative_post_result_selection':True})
    return examples


def authenticate(project,manifest_path):
    manifest=read_json(manifest_path);checked=[];aliases=[]
    snapshot=project/'relatorios/etapa13/entradas_etapa12';snapshot.mkdir(parents=True,exist_ok=True)
    for entry in manifest['artifacts']:
        source=Path(entry['path']);relative=source.relative_to(project).as_posix() if source.is_relative_to(project) else ''
        actual=source
        if relative in MUTABLE:
            saved=snapshot/source.name
            if not saved.exists():
                if fingerprint(source)!=entry:raise ValueError(f'Estado histórico sem snapshot autêntico: {source}')
                shutil.copyfile(source,saved)
            actual=saved;aliases.append({'original':entry,'snapshot':fingerprint(saved)})
        found=fingerprint(actual)
        if (found['sha256'],found['bytes'])!=(entry['sha256'],entry['bytes']):raise ValueError(f'Entrada da etapa12 alterada: {source}')
        checked.append(entry)
    return manifest,checked,aliases


class Evidence:
    def __init__(self,project,config):
        self.project=project;self.config=config
        self.execution=read_json(project/config['execution_report']);self.root=Path(self.execution['products_root'])
        self.design=yaml.safe_load((project/'configs/amostra_pycrown_exploratoria_v0_3_0.yaml').read_text())
        self.sources={};self.frames={};self.metrics={}
        names=['coorte_selecionada','todas_unidades_50m','indicadores_multiescala','escores_rankings',
            'concordancia_ablacao','membros_top','sensibilidade_rankings_agrupada','sensibilidade_cenarios',
            'pares_cobertura_semelhante','disponibilidade_metodos','qc_fontes','selecao_corredores_congelada']
        geo={'coorte_selecionada','todas_unidades_50m','indicadores_multiescala','selecao_corredores_congelada'}
        for name in names:
            path=self.root/f'{name}.parquet';self.sources[name]=fingerprint(path)
            self.frames[name]=gpd.read_parquet(path) if name in geo else pd.read_parquet(path)
        self.main_filters={'case':'sample_evaluation','family':'grid','scale_m':50.,'scope':config['main_scope'],
            'variant_id':config['main_variant'],'top_fraction':config['top_fraction']}

    def metric(self,key,source,column=None,aggregation='scalar',filters=None,unit='1',interpretation='sustentada'):
        recipe={'source':source,'filters':filters or {},'column':column,'aggregation':aggregation}
        value=evaluate_recipe(self.frames[source],recipe)
        self.metrics[key]={'value':value,'unit':unit,'recipe':recipe,'classification':interpretation,
            'source_fingerprint':self.sources[source],'scientific_protocol':'0.3.0','source_run_id':self.execution['run_id']}
        return value

    def derived(self,key,value,inputs,expression,unit='1',classification='sustentada'):
        self.metrics[key]={'value':native(value),'unit':unit,'derived_from':inputs,'expression':expression,
            'classification':classification,'scientific_protocol':'0.3.0','source_run_id':self.execution['run_id']}

    def prepare(self):
        cohort=self.frames['coorte_selecionada'];all50=self.frames['todas_unidades_50m']
        if cohort.unit_id.duplicated().any() or not cohort.eligible_A_plus_3D.all():raise ValueError('Coorte primária inválida')
        for role in ['evaluation','development']:
            self.metric(f'units_{role}','coorte_selecionada','unit_id','nunique',{'role':role})
            self.metric(f'corridors_{role}','coorte_selecionada','corridor_id','nunique',{'role':role})
        self.metric('all_grid_units_50m','todas_unidades_50m',aggregation='count')
        self.metric('all_grid_units_multiscale','indicadores_multiescala',aggregation='count')
        qc=self.frames['qc_fontes']
        if qc.duplicated(['product','tile']).any():raise ValueError('Nesta amostra as fontes QC precisam de identificação única')
        self.metric('source_files_qc','qc_fontes',aggregation='count')
        self.metric('source_tile_pairs','qc_fontes','tile','nunique')
        self.metric('source_declared_records','qc_fontes','declared_points','sum',unit='records')
        self.metric('source_decoded_records','qc_fontes','decoded_points','sum',unit='records')
        self.metric('source_crc_checked_files','qc_fontes','archive_crc_checked','sum')
        target=int(self.execution['sample']['target_evaluation_units'])
        self.metrics['target_evaluation']={'value':target,'unit':'1','json_pointer':'/sample/target_evaluation_units',
            'source_fingerprint':fingerprint(self.project/self.config['execution_report']),'classification':'sustentada',
            'scientific_protocol':'0.3.0','source_run_id':self.execution['run_id']}
        self.derived('evaluation_shortfall',target-self.metrics['units_evaluation']['value'],['target_evaluation','units_evaluation'],'target_evaluation-units_evaluation')
        for column in ['n','k','spearman_rho','jaccard_exact','jaccard_including_cut_ties','top_intersection_n','top_union_n',
            'mean_absolute_rank_shift','maximum_absolute_rank_shift','base_tie_at_cut_n','variant_tie_at_cut_n']:
            self.metric('primary_'+column,'concordancia_ablacao',column,filters=self.main_filters,interpretation='exploratoria')
        for column in ['paired_eligible_units','spearman_rho','jaccard_exact']:
            for agg in ['min','max']:
                self.metric(f'sensitivity_{column}_{agg}','sensibilidade_rankings_agrupada',column,agg,{'role':'evaluation'},interpretation='parcialmente_sustentada')
        pair_filter={'case':'sample_evaluation','family':'grid','scale_m':50.}
        self.metric('similar_cover_pairs','pares_cobertura_semelhante',aggregation='count',filters=pair_filter,interpretation='exploratoria')
        for col in ['absolute_P95_difference_m','absolute_IQR_difference_m']:
            for agg in ['median','max']:self.metric(f'pairs_{col}_{agg}','pares_cobertura_semelhante',col,agg,pair_filter,'m','exploratoria')
        sample=[]
        for cid,g in all50.groupby('corridor_id',sort=True):
            role=g.role.iloc[0];selected=cohort.loc[cohort.corridor_id.eq(cid)]
            fields={}
            for col in ['area_total_m2','area_observed_m2','area_canopy_m2']:
                fields[col]=self.metric(f'{cid}_{col}','todas_unidades_50m',col,'sum',{'corridor_id':cid},'m2')
            p,o=fields['area_total_m2'],fields['area_observed_m2']
            fraction=o/p;self.derived(f'{cid}_fraction_observed',fraction,[f'{cid}_area_total_m2',f'{cid}_area_observed_m2'],f'{cid}_area_observed_m2/{cid}_area_total_m2')
            sample.append({'corridor_id':cid,'role':role,'block_id':g.block_id.iloc[0],**fields,'fraction_observed':fraction,
                'eligible_50m':int(g.eligible_A_plus_3D.sum()),'selected_50m':len(selected),'target_50m':int(self.design['target_units_per_corridor']),
                'eligibility_shortfall':max(0,int(self.design['target_units_per_corridor'])-len(selected))})
        self.sample=pd.DataFrame(sample)
        self.sources['sample_summary']={'path':'tables/dados_amostra.csv','generated':True}
        self.frames['sample_summary']=self.sample
        for agg in ['min','max']:self.metric(f'observed_fraction_{agg}','sample_summary','fraction_observed',agg,unit='1')
        filters={k:v for k,v in self.main_filters.items() if k!='top_fraction'}
        ranks=self.frames['escores_rankings'];base=subset(ranks,{**filters,'variant_id':'A'})
        aug=subset(ranks,filters)
        if set(base.unit_id)!=set(aug.unit_id) or len(base)!=self.metrics['units_evaluation']['value']:raise ValueError('Rankings usam universos diferentes')
        if base.unit_id.duplicated().any() or aug.unit_id.duplicated().any():raise ValueError('Ranks duplicados')
        self.ranks=base[['unit_id','rank_mean','rank_ordinal','score_for_ranking']].merge(
            aug[['unit_id','rank_mean','rank_ordinal','score_for_ranking']],on='unit_id',suffixes=('_A','_3D'),validate='one_to_one')
        top=subset(self.frames['membros_top'],self.main_filters)
        if len(top)!=len(base) or top.unit_id.duplicated().any():raise ValueError('Membros top não correspondem à coorte')
        self.ranks=self.ranks.merge(top[['unit_id','disagreement','top_baseline_exact','top_variant_exact']],on='unit_id',validate='one_to_one')
        extra=['unit_id','corridor_id','block_id','I1','I4','I5','I6','I7','area_total_m2','area_observed_m2','area_canopy_m2',
            'fraction_observed','n_vegetation_records','selection_hash','classification_uncertainty_present','n_patches_context_censored','n_patches_support_censored']
        self.ranks=self.ranks.merge(cohort[extra],on='unit_id',validate='one_to_one')
        self.examples=choose_examples(self.ranks,self.config['example_selection'])
        for e in self.examples:
            status=e['status']
            expression={'kept':'primary_top_intersection_n','lost':'primary_k-primary_top_intersection_n',
                'gained':'primary_k-primary_top_intersection_n','neither':'primary_n-2*primary_k+primary_top_intersection_n'}[status]
            self.derived('top_group_'+status,e['group_n'],['primary_n','primary_k','primary_top_intersection_n'],expression)
        self.main_example=native(self.ranks.sort_values(['selection_hash','unit_id']).iloc[0].to_dict())
        return self

    def export(self,out):
        tables=out/'tables';tables.mkdir(parents=True,exist_ok=True)
        self.sample.to_csv(tables/'dados_amostra.csv',index=False)
        self.sources['sample_summary']=fingerprint(tables/'dados_amostra.csv')
        for value in self.metrics.values():
            if value.get('recipe',{}).get('source')=='sample_summary':value['source_fingerprint']=self.sources['sample_summary']
        self.ranks.to_csv(tables/'dados_rankings_avaliacao.csv',index=False)
        pd.DataFrame(self.examples).to_csv(tables/'exemplos_acordo_desacordo.csv',index=False)
        selected_sources={'sensibilidade_rankings_agrupada':'dados_sensibilidade','sensibilidade_cenarios':'dados_iou_cenarios',
            'concordancia_ablacao':'dados_ablacoes','pares_cobertura_semelhante':'dados_pares_cobertura'}
        for source,name in selected_sources.items():self.frames[source].to_csv(tables/f'{name}.csv',index=False)
        atomic_write_json(out/'selecao_exemplos.json',{'main':self.main_example,'strata':self.examples,
            'main_rule':self.config['main_example_selection'],'no_selection_by_maximum_disagreement':True,
            'source_run_id':self.execution['run_id'],'post_result_illustrations_not_validation':True})
        claims=[
            ('C13_01',f"A amostra contém {len(self.sample)} corredores e {self.metrics['units_evaluation']['value']} unidades de avaliação, abaixo da meta de {self.metrics['target_evaluation']['value']}.",'sustentada',
                ['units_evaluation','units_development','corridors_evaluation','corridors_development','evaluation_shortfall'],['amostra_intencional','sem_independencia_certificada']),
            ('C13_02','Há áreas sem suporte que limitam a interpretação dos corredores completos.','sustentada',
                ['observed_fraction_min','observed_fraction_max'],['NoData_nao_e_ausencia_de_arvores']),
            ('C13_03','A inclusão de I6/I7 altera a ordenação e o top20% da coorte de avaliação.','exploratoria',
                ['primary_spearman_rho','primary_jaccard_exact','primary_k','primary_top_intersection_n'],['escore_relativo','sem_alvo_independente','sem_causalidade']),
            ('C13_04','Unidades com cobertura semelhante apresentam diferenças de altura dos retornos.','exploratoria',
                ['similar_cover_pairs','pairs_absolute_P95_difference_m_median','pairs_absolute_P95_difference_m_max'],['pares_dependentes','altura_de_retornos_nao_altura_por_arvore']),
            ('C13_05','A estabilidade entre cenários é condicional ao suporte e aos IDs que permanecem elegíveis.','parcialmente_sustentada',
                ['sensitivity_paired_eligible_units_min','sensitivity_paired_eligible_units_max','sensitivity_spearman_rho_min',
                 'sensitivity_spearman_rho_max','sensitivity_jaccard_exact_min','sensitivity_jaccard_exact_max'],['universos_variaveis','sem_garantia_simultanea_para_coorte_integral']),
            ('C13_06','O 3D melhora o diagnóstico ou a prioridade real de intervenção.','nao_testada',[],['nenhum_alvo_independente','nao_confundir_discordancia_com_melhoria']),
            ('C13_07','As copas ou posições de topo têm acurácia conhecida ou contorno exato.','nao_testada',[],['sem_referencia_externa','resolucao_raster','segmentos_nao_equivalem_a_arvores_confirmadas']),
            ('C13_08','Os resultados representam toda São Paulo.','nao_testada',[],['sem_amostra_probabilistica_municipal','apenas_dez_corredores']),
            ('C13_09','B/C e conectividade funcional foram avaliados nesta amostra.','nao_testada',[],['eixos_nao_revalidados','Amais3D_nao_e_C'])]
        self.claims=[{'claim_id':i,'statement':s,'classification':c,'metric_ids':m,'limitations':l,
            'evidence_for_not_tested':None if m else {'source':self.sources['disponibilidade_metodos'] if i=='C13_09' else fingerprint(self.project/'docs/protocolo_pycrown_v0_3_0.md'),
                'reason':'declared_scope_no_independent_target_or_no_longitudinal_axis'}} for i,s,c,m,l in claims]
        atomic_write_json(out/'resultados_publicaveis.json',{'presentation_version':'1.0.0','scientific_protocol':'0.3.0',
            'source_run_id':self.execution['run_id'],'study_mode':'exploratory_without_external_reference',
            'sources':self.sources,'metrics':self.metrics,'claims':self.claims,
            'inference':{'p_values':False,'confidence_intervals':False,'reason':'independence_exchangeability_and_target_reference_not_established'},
            'no_new_LAZ_processing':True})
