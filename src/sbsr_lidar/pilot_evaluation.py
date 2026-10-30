"""Etapa 11: avaliação crítica rastreável e plano condicional; nenhuma nuvem processada."""
from __future__ import annotations

from pathlib import Path
import resource
import shutil
import sys
import time

import geopandas as gpd
import pandas as pd
import psutil

from .annotations import check_annotations
from .environment import environment_snapshot, source_digest
from .pilot_evidence import reconstruct, dependence_diagnostics, cost_projection
from .pilot_planning import load_design, sampling_frame, planned_tiles
from .runtime import Run, exclusive_lock
from .storage import read_json, fingerprint, atomic_write_json


def assessment_criteria(reports, assessment, inventory_ok):
    rows = []
    def add(code, criterion, status, decision, sources, scope):
        rows.append({'criterion_id': code, 'criterion': criterion, 'status': status,
            'decision': decision, 'evidence_reports': sources, 'scope_and_limits': scope})
    def evidence(stage):
        return ';'.join(str(r['run_id'])+':'+stage for (s, _), r in reports.items() if s == stage)
    add('C11_01', 'Rastreabilidade e execução técnica', 'atendido' if inventory_ok else 'falha',
        'Execuções selecionadas e fontes conferidas por hashes, sem repetir processamento de nuvens.', evidence('03'), 'Integridade do piloto; não certifica todo o acervo municipal.')
    add('C11_02', 'Terreno utilizável', 'parcial',
        'TIN5 utilizável no domínio suportado; acurácia absoluta independente não medida.', evidence('04'),
        'Comparar resíduos internos e cobertura conjuntamente; grande perda em blocos MDT reservados e no adverso.')
    add('C11_03', 'Separação árvores/estruturas com qualidade medida', 'dependencia_impeditiva',
        f"{assessment['completed_annotations']} anotações concluídas; precisão/recall/IoU não disponíveis.", evidence('06'),
        'Classes, H, RGB/NIR e geometria são candidatos/diagnósticos, não validação semântica.')
    add('C11_04', 'NoData e observabilidade', 'atendido_tecnicamente',
        'Ausência de MDS, QC excluído, terreno/H sem suporte e classificação incerta permanecem distintos.', evidence('08'),
        'Cobertura T/O é condicional; limites geométricos não incluem erro de classificação.')
    add('C11_05', 'Eixo e indicadores B/C', 'insuficiente_no_formato_atual',
        'Principal ramificado sem eixo único; adverso geométrico com observação longitudinal insuficiente. Adotar A/A+3D em grade.', evidence('07'),
        'Não renomear A+3D como C; I2/I3 e lacunas dependem de eixo/suporte/referência próprios.')
    add('C11_06', 'Efeito de borda/contexto', 'observado',
        'Halo10 ganha suporte em relação a halo0; contexto truncado no adverso e componente censurado são explícitos.', evidence('04')+';'+evidence('10'),
        'Halo não expande P; expansões de P mudam população e ficam separadas.')
    add('C11_07', 'Interpretação e estabilidade dos indicadores', 'condicional',
        'I1/I4 são cobertura/componentes detectados; I6/I7 descrevem retornos. I4 depende de resolução/conectividade; primeiros retornos alteram estimando.', evidence('10'),
        'Sem volume/biomassa, altura por árvore, benefício ecológico universal ou prioridade real.')
    add('C11_08', 'Robustez global do ranking', 'limitada',
        'Interseção elegível global principal 25/50/100m=5/1/0; adverso=0/0/0. Frequências por eixo/receita não substituem suporte global.', evidence('10'),
        'Spearman alto pode coexistir com mudança do top; pesos, sinal de IQR e escala importam.')
    add('C11_09', 'Ganho frente a alvo independente', 'nao_testavel_sem_referencia',
        f"{assessment['independent_priority_references']} alvos independentes. H3 desabilitada.", evidence('09'),
        'Discordância de ranking não é melhoria de diagnóstico ou utilidade de intervenção.')
    add('C11_10', 'Amostra para sustentar o artigo', 'nao_demonstrada',
        'Dois casos heterogêneos, um grupo/caso, desenvolvimento pós-inspeção. Preparar novos blocos e referência.', evidence('09')+';'+evidence('10'),
        'O adverso já foi inspecionado; não é teste municipal intocado. Sem poder/IC/p-valores por pseudorreplicação.')
    add('C11_11', 'Custo e execução ampliada', 'requer_ajuste_limitado',
        'Custos medidos em dois recortes; driver de múltiplos corredores, coorte conjunta e janelas limitadas ainda precisam implementação/teste.', evidence('10'),
        'Envelopes de custo não incluem aquisição/referência/tempo humano e não garantem escalabilidade municipal.')
    return pd.DataFrame(rows)


def failure_inventory():
    rows = [
        ('F11_01', 'referencia', 'impeditiva_H1_H2_validado', 'Zero rótulos completos de máscara.',
         'Concluir/adjudicar as 20 janelas do piloto; preparar 40 janelas novas, oito de desenvolvimento e 32 de avaliação em blocos separados, com fonte datada pertinente a 2020. Incerto permitido; referência derivada do LiDAR não é independente do sensor.',
         'Parecer de qualidade cego aos escores, confusão/precisão/recall/IoU e erros de cobertura com denominadores e incerteza.', '05_reference_if_new_windows;06_mask_if_changed;07_08_09_10_descendants_if_mask_changed'),
        ('F11_02', 'altimetria', 'impeditiva_acuracia_absoluta', 'MDT reservado é referência interna relacionada.',
         'Buscar referência altimétrica independente com datum/data e auditoria de água/ponte; até lá restringir H a suporte e incerteza internos.',
         'Resíduos externos se disponíveis; sem disponibilidade manter acurácia absoluta não demonstrada.', '04_06_07_08_09_10_only_if_terrain_or_datum_changed'),
        ('F11_03', 'eixo_lacunas', 'impeditiva_B_C', 'Eixo principal ambíguo; adverso sem comprimento observável suficiente.',
         'Manter grade no núcleo. Só ativar B/C em protocolo separado com eixo revisado e referência de lacunas, sem cruzar trechos desconhecidos.',
         'Eixo e lacunas validados separadamente; ou B/C explicitamente ausentes.', '07_08_09_10_longitudinal_if_axis_changed;grid_results_remain_historical'),
        ('F11_04', 'alvo_prioridade', 'impeditiva_H3', 'Sem alvo independente de necessidade/utilidade.',
         'Manter H3 desabilitada; se surgir alvo, auditar pertinência temporal e independência dos indicadores e definir novo protocolo antes do teste.',
         'Sem rótulo derivado do próprio escore e sem declarar ganho de acurácia.', '09_predictive_only_after_new_protocol;physical_metrics_not_invalidated'),
        ('F11_05', 'dependencia_espacial', 'impeditiva_inferencia', 'Um corredor/caso não estima variância entre corredores ou alcance confiável.',
         'Novos blocos conservadores de proximidade, sensibilidade de agrupamento, diagnóstico de dependência e reporte de perdas; não chamar contagem de blocos de poder.',
         'Independência/permutabilidade justificadas antes de IC ou p-valores; padrão descritivo.', 'selection_and_inference_if_block_definition_changed;not_raw_H'),
        ('F11_06', 'driver_amostral', 'impeditiva_execucao_amostra', 'CLI atual e leitores congelados operam os casos fixos do piloto.',
         'Na etapa12 criar driver de IDs explícitos, planos de folhas/halos, propriedade de registros/unidades e coorte de avaliação agrupada. TIN por janela limitada; unir IDs de manchas entre janelas antes de I4 e testar fronteiras.',
         'Um novo corredor de desenvolvimento passa por orçamento/QC/retomada antes dos demais; nenhuma execução com gates pendentes.', 'new_sample_namespace_v0.2.0;global_code_digest_causes_cache_miss_but_no_retroactive_data_invalidation'),
        ('F11_07', 'suporte_integridade', 'impeditiva_por_unidade', 'Suporte dos novos corredores e integridade comprimida integral ainda desconhecidos.',
         'Completar somente pares faltantes após plano; decodificar/verificar na primeira passagem, preservar NoData e mínimos de suporte. Excluir com motivo e usar reservas preordenadas, sem escolher por C.',
         'Tabela de todos os candidatos/unidades inclusive perdas; não relaxar 95% ou inventar zeros para atingir meta.', '03_04_06_07_08_09_10_only_affected_inputs_or_parameters'),
        ('F11_08', 'orcamento', 'limitacao_estimativa', 'Dois casos não calibram custo geral; paralelismo não medido.',
         'Um trabalhador, 8GiB/processo, reservar 20GiB livres além do orçamento derivado; recalibrar no primeiro novo caso e checkpoint por janela. Não ativar dois trabalhadores sem ensaio.',
         'Medições novas versus envelope, espaço real e retomada comprovados; downloads/tempo humano sem previsão fictícia.', 'cost_estimate_and_scheduling_only'),
    ]
    return pd.DataFrame(rows, columns=['failure_id','category','severity','observed_failure_or_dependency',
        'concrete_resolution','acceptance_evidence','cache_invalidation'])


def frozen_protocol(config, design, frame_summary, proposal, annotation, inputs):
    selected = proposal.loc[proposal.selected_for_planning.eq(True)].sort_values('candidate_order')
    return {'protocol_version': design.protocol_version, 'status': design.status,
        'post_pilot_choices_not_retroactive_preregistration': True, 'design': design.model_dump(mode='json'),
        'physical_baseline': config.model_dump(mode='json'),
        'population': frame_summary, 'proposed_candidates': selected[['corridor_id','block_id','stratum','proposed_role','target_units']].to_dict('records'),
        'selection_uses_outcomes': False, 'selection_materialized_only_for_planning': True,
        'final_unit_selection_rule': 'after QC before rankings: seeded hash of unit_id, 15 per evaluation corridor without replacement; preserve all physical descriptors/exclusions; insufficient counts use preordered reserve and log replacement before looking at outcomes',
        'primary_comparison': 'A/A_plus_3D, original P, grid50, baseline_h3, TIN5, halo10, connectivity8; same mask/eligible cohort; never fake B/C',
        'normalizer': 'average_rank minus0.5 divided by n on fixed pooled evaluation-unit cohort across the8 new evaluation corridors; distinct from pilot per-case calibration; not transported across populations',
        'comparison_scope': 'target120 evaluation units;30 development units excluded from final estimates/rank normalizers; per-corridor physical summaries retain grouping and small-k guards',
        'hypotheses': {'H1': 'physical vertical variation conditional on I1 with <=0.05 cover tolerance and <=2 observed-area ratio; report reused units/pairs and corridor groups',
            'H2': 'rank changes and robustness with fixed formulas, weights0/.25/.5/.75, both IQR signs, I6-only and dimension controls; negative outcomes admissible',
            'H3': 'disabled without independently audited dated priority target; never use own height/score as truth'},
        'validation': {'mask': 'real labels, dated independent imagery/field where pertinent; uncertain allowed; class errors and propagation to I1/ranks assessed; no fabricated accuracy threshold claimed justified',
            'development': '2 entirely new spatial blocks for limited adjustment; existing pilot is development context',
            'evaluation': '8 different new provisional blocks; held-out annotation/quality review without scores; test not used to tune parameters',
            'proposed_windows': design.target_corridors*design.reference_windows_per_corridor,
            'double_annotation': design.double_annotation_fraction, 'human_labels_available_now': annotation['completed_annotations'],
            'terrain': 'internal QC plus external datum-consistent validation if available; no absolute accuracy claim without it',
            'priority': 'no independent target now; H3/utility claims disabled'},
        'inference': 'descriptive by default;1000m graph groups are conservative planning, not estimated independence;6-group threshold necessary operational guard but insufficient for power/CI/permutability; no automatic p-values or pixel bootstrap',
        'sensitivity': 'retain stage10 parameter definitions and gradual scenarios;0.5/1/2m,2/3/5m,25/50/100m,halo0/10/20,record thinning,weights and IQR signs; exact common-support transfer; no selecting winner scenario',
        'gate_status': {'reference_quality_review': False, 'new_sample_support_QC': False,
            'generic_driver_verified': False, 'new_case_resource_calibration': False,
            'geometric_frame_sufficient': frame_summary['adequate_geometric_frame']},
        'step12_handoff': {'mode': 'amostra_cientifica', 'current_allowed_operation': 'preflight_reference_and_materialize_plan_only',
            'cloud_processing_enabled': False, 'municipal_processing_enabled': False,
            'unlock_condition': 'all reference/support/driver/resource gates independently evidenced; new version for changed scientific rules; explicit user activation of step12'},
        'change_control': 'retain v0.1 pilot and frozen v0.2 proposal; necessary method changes get new version and descendant cache invalidation; no overwritten history or selecting weights by advantage of3D',
        'source_vector_fingerprints': [p for p in inputs if Path(p['path']).suffix in {'.shp','.dbf','.shx','.prj','.cst'}]}


def evaluate_pilot(config, design_path):
    design = load_design(design_path)
    state = read_json(config.paths.state_file)
    if state['etapas']['10']['status'] != 'concluida': raise ValueError('Concluir etapa10 antes da avaliação')
    with exclusive_lock(config.paths.runs_root/'.pilot_evaluation.lock'):
        aggregates, reports, executions, checks, inputs, output_inventory = reconstruct(config, state)
        historical_config = read_json(Path(aggregates['10']['runs']['execucao_main']['manifest']))['config']
        for section in ['grid','vegetation','terrain','support','segmentation','comparison','sensitivity']:
            if historical_config[section] != getattr(config, section).model_dump(mode='json'):
                raise ValueError(f'Configuração atual difere do piloto avaliado: {section}')
        reference = check_annotations(Path(state['referencia_anotacao']['package']))
        if not reference['ok']: raise ValueError('Esquema/referência inconsistentes; revisar antes da avaliação')
        inputs.append(fingerprint(Path(design_path)))
        code = source_digest(); environment = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
        snapshot = config.model_dump(mode='json'); snapshot['study_design'] = design.model_dump(mode='json')
        run = Run(config.paths.runs_root, config.paths.state_file, 'evaluate-pilot', snapshot, inputs, environment, code, stage='11')
        started = time.monotonic()
        try:
            directory = config.paths.project_root/'relatorios/etapa11'/run.run_id
            directory.mkdir(parents=True, exist_ok=False)
            run.event('reconstruct_complete', selected_runs=len(executions), source_checks=len(checks))
            reservation = pd.read_csv(state['referencia_anotacao']['group_reservation'])
            frame, proposal, blocks, block_sensitivity, frame_summary = sampling_frame(config, design, reservation)
            links, files = planned_tiles(config, proposal)
            # Cabeçalhos planejados são metadados, não evidência de integridade/QC de pontos.
            for p in files.loc[files.exists, 'path']:
                inputs.append(fingerprint(Path(p)))
            variance, dependence = dependence_diagnostics(config, state)
            calibrations, projections = cost_projection(executions, reports, design, proposal, links, files)
            protocol = frozen_protocol(config, design, frame_summary, proposal, reference, inputs)
            criteria = assessment_criteria(reports, reference, bool(checks.ok.all()))
            failures = failure_inventory()
            criteria_decision = 'depende_de_referencia_complementar' if not reference['completed_annotations'] else 'requer_revisao_da_qualidade_da_referencia'
            tables = {'execucoes_reconstruidas': executions, 'verificacao_fontes': checks,
                'manifestos_reconstruidos': pd.DataFrame([{'stage': stage, 'historical_status': m['status'],
                    'manifest': str(config.paths.project_root/f'docs/manifesto_etapa{stage}.json'),
                    'scope': 'historical_snapshot; shared_code_docs_state_may_evolve; selected_science_files_separately_hashed',
                    'recorded_criteria': str(m.get('criteria', m.get('checks', {})))} for stage,m in aggregates.items()]),
                'criterios_evidencias': criteria, 'inventario_falhas': failures,
                'quadro_amostral': frame, 'ordem_candidatos': proposal,
                'blocos_espaciais': blocks, 'sensibilidade_blocos': block_sensitivity,
                'folhas_por_candidato': links, 'arquivos_planejados': files,
                'variabilidade_piloto': variance, 'dependencia_espacial_descritiva': dependence,
                'calibracao_custo': calibrations, 'estimativa_custo': projections,
                'inventario_produtos_selecionados': pd.DataFrame(output_inventory)}
            for name, table in tables.items():
                table.to_parquet(directory/f'{name}.parquet', index=False, compression='zstd')
                plain = pd.DataFrame(table.drop(columns='geometry')) if isinstance(table, gpd.GeoDataFrame) else table
                plain.to_csv(directory/f'{name}.csv', index=False)
            atomic_write_json(directory/'protocolo_congelado_v0_2_0.json', protocol)
            atomic_write_json(directory/'referencia_atual.json', reference)
            # Snapshot físico de disco: arquivos de desenvolvimento/cache também
            # ocupam espaço, mas não são somados como novas observações científicas.
            disk_inventory = []
            for path in config.paths.output_root.rglob('*'):
                if path.is_file(): disk_inventory.append({'path': str(path), 'logical_bytes': path.stat().st_size})
            pd.DataFrame(disk_inventory).to_parquet(directory/'inventario_disco_derivado.parquet', index=False)
            derived_bytes = sum(p['logical_bytes'] for p in disk_inventory)
            disk = {'external_free_bytes': shutil.disk_usage(config.paths.output_root).free,
                'project_free_bytes': shutil.disk_usage(config.paths.project_root).free,
                'all_current_derived_logical_bytes': derived_bytes,
                'all_current_derived_files': len(disk_inventory), 'available_ram_bytes': psutil.virtual_memory().available,
                'measurement_note': 'current stat snapshot incl development/cache/duplicates; logical file bytes, not unique science observations; no predicted RAM scaling by municipality'}
            main10, adv10 = reports[('10','main')], reports[('10','adversarial')]
            result = {'ok': True, 'stage': '11', 'run_id': run.run_id, 'products_root': str(directory),
                'continuation_classification': criteria_decision, 'secondary_adjustment': 'generic_sample_driver_and_resource_recalibration_required',
                'technical_pilot': 'executed_reproducible_bounded_scope',
                'scientific_interpretability': 'conditional_descriptive; mask_unvalidated_and_no_independent_priority_target',
                'article_supporting_sample': 'not_established; new_sample_and_reference_pending',
                'ready_for_scientific_sample_execution': False, 'empirical_validation_complete': False,
                'full_pilot_approved': False, 'mask_validated': False, 'accuracy_gain_claimed': False,
                'p_values_computed': False, 'statistical_power_computed': False,
                'new_cloud_records_decoded': 0, 'human_labels_created': 0, 'sample_executed': False,
                'selected_historical_runs': len(executions), 'verified_source_records': len(checks),
                'frame': frame_summary, 'resources': disk,
                'global_50m_eligible_units': {'main': next(x['n_common_eligible_all_scenarios'] for x in main10['strict_cohorts'] if x['ensemble']=='physical_global_common_support' and x['scale_m']==50),
                    'adversarial': next(x['n_common_eligible_all_scenarios'] for x in adv10['strict_cohorts'] if x['ensemble']=='physical_global_common_support' and x['scale_m']==50)},
                'frozen_protocol': str(directory/'protocolo_congelado_v0_2_0.json'),
                'next_stage': '12', 'step12_operation_now': protocol['step12_handoff'],
                'table_rows': {name: len(t) for name,t in tables.items()},
                'elapsed_seconds': time.monotonic()-started, 'peak_process_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
            # Entradas adicionadas pelos cabeçalhos são incorporadas antes de concluir o manifesto.
            inputs = list({p['path']:p for p in inputs}.values())
            if any(fingerprint(Path(p['path'])) != p for p in inputs): raise ValueError('Fonte mudou durante a avaliação')
            run.manifest['inputs'] = inputs
            report = run.path/'avaliacao_piloto.json'; atomic_write_json(report, result)
            products = [report]+sorted(p for p in directory.iterdir() if p.is_file())
            run.finish(products)
            return {'ok': True, 'stage': '11', 'run_id': run.run_id, 'manifest': str(run.path/'manifest.json'),
                'report': str(report), 'products_root': str(directory), 'continuation_classification': criteria_decision}
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt)); raise
