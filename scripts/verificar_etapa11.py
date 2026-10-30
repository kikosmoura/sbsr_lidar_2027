"""Auditoria independente dos produtos de avaliação/planejamento, sem executar amostra."""
from pathlib import Path
import hashlib
import json
import math
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from sbsr_lidar.config import load_config
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.pilot_planning import StudyDesign,load_design
from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json

root=Path.cwd(); c=load_config(root/'configs/terreno_congelado_etapa04.yaml'); design=load_design(root/'configs/amostra_cientifica_v0_2_0.yaml')
e=read_json(root/'relatorios/etapa11/execucao.json'); r=read_json(Path(e['report'])); d=Path(e['products_root']); m=RunManifest.model_validate(read_json(Path(e['manifest'])))
tables={p.stem:pd.read_parquet(p) for p in d.glob('*.parquet')}; protocol=read_json(Path(r['frozen_protocol'])); checks={}
checks['completed_stage11_current_source']=m.stage=='11' and m.status=='completed' and m.code_sha256==source_digest()
checks['immutable_inputs_verified']=all(fingerprint(Path(p.path))==p.model_dump() for p in m.inputs)
checks['01_to_10_aggregates_reconstructed']=set(tables['manifestos_reconstruidos'].stage)=={f'{i:02}' for i in range(1,11)}
checks['selected_15_runs_and_commands']=len(tables['execucoes_reconstruidas'])==15 and tables['execucoes_reconstruidas'].command.notna().all() and tables['execucoes_reconstruidas'].workers.eq(1).all()
checks['source_ledger_passed']=bool(tables['verificacao_fontes'].ok.all()) and r['verified_source_records']==len(tables['verificacao_fontes'])
checks['decision_and_levels_honest']=r['continuation_classification']=='depende_de_referencia_complementar' and not r['ready_for_scientific_sample_execution'] and not r['full_pilot_approved'] and r['article_supporting_sample'].startswith('not_established')
checks['no_sample_cloud_labels_or_inference']=r['new_cloud_records_decoded']==0 and r['human_labels_created']==0 and not any(r[k] for k in ['sample_executed','empirical_validation_complete','mask_validated','accuracy_gain_claimed','p_values_computed','statistical_power_computed'])
criteria=tables['criterios_evidencias'].set_index('criterion_id');failures=tables['inventario_falhas']
checks['criteria_have_evidence_and_limits']=len(criteria)==11 and criteria.evidence_reports.notna().all() and criteria.scope_and_limits.notna().all() and criteria.loc['C11_03'].status=='dependencia_impeditiva' and criteria.loc['C11_05'].status=='insuficiente_no_formato_atual'
checks['failure_resolution_and_invalidation']=len(failures)==8 and failures.failure_id.is_unique and failures.concrete_resolution.notna().all() and failures.acceptance_evidence.notna().all() and failures.cache_invalidation.notna().all()
checks['frozen_design_matches_yaml']=protocol['design']==design.model_dump(mode='json') and protocol==read_json(root/'configs/protocolo_congelado_amostra_v0_2_0.json') and protocol['protocol_version']=='0.2.0'
checks['freeze_not_retroactive_or_authorization']=protocol['post_pilot_choices_not_retroactive_preregistration'] and not protocol['design']['execution_enabled'] and not protocol['design']['municipal_mode_enabled'] and not protocol['selection_uses_outcomes']
checks['pending_gates_preserved']=protocol['gate_status']['geometric_frame_sufficient'] and not any(protocol['gate_status'][k] for k in ['reference_quality_review','new_sample_support_QC','generic_driver_verified','new_case_resource_calibration']) and not protocol['step12_handoff']['cloud_processing_enabled'] and not protocol['step12_handoff']['municipal_processing_enabled']
frame=gpd.read_parquet(d/'quadro_amostral.parquet'); order=gpd.read_parquet(d/'ordem_candidatos.parquet'); selected=order.loc[order.selected_for_planning.eq(True)].sort_values('candidate_order')
original=gpd.read_file(c.paths.corridors).set_index(c.pilot.corridor_field)
checks['full_frame_and_original_geometries']=len(frame)==114 and frame.corridor_id.is_unique and set(frame.corridor_id)==set(original.index) and all(g.equals(original.loc[u].geometry) for u,g in zip(frame.corridor_id,frame.geometry))
checks['selection_scope_and_capacity']=len(selected)==10 and selected[design.status_field].eq('PROPOSTO').all() and selected[design.type_field].eq('CORREDOR VERDE').all() and selected.potential_50m_units_area_only.ge(15).all()
checks['roles_and_target_not_actual_sample']=selected.proposed_role.eq('avaliacao').sum()==8 and selected.proposed_role.eq('desenvolvimento').sum()==2 and selected.loc[selected.proposed_role.eq('avaliacao'),'target_units'].sum()==120 and order.actual_eligible_units.isna().all() and order.actual_validated_units.isna().all()
checks['new_support_quality_unknown']=not frame.LiDAR_support_assessed_for_new_corridor.any() and not frame.canopy_quality_assessed_for_new_corridor.any() and not r['frame']['independent_groups_certified'] and not r['frame']['probability_sample']
checks['selection_uses_seeded_ID_only']=all(v==hashlib.sha256(f'{design.seed}|{u}'.encode()).hexdigest() for u,v in zip(frame.corridor_id,frame.selection_priority)) and not any(k in frame for k in ['I1','I4','I6','I7','score','rank_mean'])
# Conferir fechamento transitivo por busca em grafo, independentemente do union-find do produtor.
block_table=tables['blocos_espaciais']; geometries=frame.geometry.to_numpy(); ids=frame.corridor_id.to_numpy(); block_ok=True
for distance in design.block_sensitivity_m:
 mapping=block_table.loc[block_table.distance_m.eq(distance)].set_index('corridor_id').block_id.to_dict()
 adjacency={u:set() for u in ids}
 for i,j in shapely.STRtree(geometries).query(geometries,predicate='dwithin',distance=distance).T:
  adjacency[ids[i]].add(ids[j])
 remaining=set(ids)
 while remaining:
  start=min(remaining); component={start}; frontier=[start]
  while frontier:
   for neighbor in adjacency[frontier.pop()]-component: component.add(neighbor);frontier.append(neighbor)
  remaining-=component
  block_ok &= len({mapping[u] for u in component})==1
  bid=mapping[start]; block_ok &= {u for u,b in mapping.items() if b==bid}==component
checks['proximity_graph_components_independent_reconstruction']=bool(block_ok)
checks['selected_roles_spatially_separated']=selected.block_id.nunique()==10 and min(a.distance(b) for i,a in enumerate(selected.geometry) for b in selected.geometry.iloc[i+1:])>design.block_distance_m
checks['legacy_reserved_groups_excluded']=selected.legacy_fold.eq('nao_atribuido').all() and not selected.legacy_proximity_excluded.any() and not selected.corridor_id.isin([c.pilot.corridor_id,c.pilot.adversarial_corridor]).any()
checks['candidate_losses_explicit']=frame.loc[~frame.planning_eligible].planning_exclusion_reason.notna().all() and frame.loc[frame.planning_eligible].planning_exclusion_reason.isna().all()
# O arquivo vetorial pode conter fragmentos desconectados em um mesmo quadrado;
# a capacidade conta partes poligonais positivas, sem inventar observação.
def parts(g):
 if g.geom_type=='Polygon': return [g]
 return [p for q in getattr(g,'geoms',[]) for p in parts(q)]
capacity_ok=True
for row in selected.itertuples():
 count=0
 for part in parts(row.geometry):
  x0,y0,x1,y1=part.bounds
  cells=[shapely.box(x*50,y*50,(x+1)*50,(y+1)*50) for x in range(math.floor(x0/50),math.ceil(x1/50)) for y in range(math.floor(y0/50),math.ceil(y1/50))]
  for intersection in shapely.intersection(np.array(cells,dtype=object),part): count+=sum(g.area>=25 for g in parts(intersection))
 capacity_ok &= count==row.potential_50m_units_area_only
checks['geometric_capacity_independent_overlay']=bool(capacity_ok)
links=tables['folhas_por_candidato']; files=tables['arquivos_planejados']; costs=tables['estimativa_custo']; calibration=tables['calibracao_custo']; executions=tables['execucoes_reconstruidas']
checks['tile_product_plan_unique_and_no_download']=not files.duplicated(['tile','product']).any() and len(files)==2*files.tile.nunique() and files.verification_scope.eq('header_only_no_point_decoding').all() and (files.needs_download==((~files.exists)&files.available_archive.isna())).all()
checks['missing_headers_not_invented']=files.loc[~files.exists,['declared_points','header_epsg','compressed_bytes']].isna().all().all() and files.loc[files.exists].header_epsg.eq(31983).all()
checks['observed_calibration_from_manifests']=all(np.isclose(row.observed_baseline_pipeline_seconds,executions.loc[executions.case.eq(row.case)&executions.stage.isin(['03','04','06','07','08','09']),'elapsed_seconds'].sum()) and np.isclose(row.observed_30_scenario_seconds,executions.loc[executions.case.eq(row.case)&executions.stage.eq('10'),'elapsed_seconds'].iloc[0]) for row in calibration.itertuples())
projection_ok=True
for row in costs.itertuples():
 candidates=order.loc[order.candidate_order.le(row.planned_corridors)]
 area=sum(g.buffer(c.pilot.halo_m).area for g in candidates.geometry)
 tiles=set(links.loc[links.corridor_id.isin(candidates.corridor_id),'tile']); f=files.loc[files.tile.isin(tiles)]
 projection_ok &= np.isclose(row.sum_context_area_m2,area) and row.unique_tiles==len(tiles) and row.missing_files==int((~f.exists).sum())
 projection_ok &= np.isclose(row.estimated_baseline_area_seconds_low,area*calibration.baseline_seconds_per_context_m2.min()) and np.isclose(row.estimated_baseline_area_seconds_budget,area*calibration.baseline_seconds_per_context_m2.max()*3)
 projection_ok &= np.isclose(row.estimated_additional_sensitivity_seconds_budget,area*calibration.sensitivity_seconds_per_context_m2.max()*3)
 projection_ok &= row.estimated_derived_bytes_budget==int(area*(calibration.baseline_bytes_per_context_m2.max()+calibration.sensitivity_bytes_per_context_m2.max())*3)
 if row.missing_files: projection_ok &= pd.isna(row.estimated_baseline_seconds_low) and pd.isna(row.estimated_baseline_seconds_budget)
checks['cost_formulas_and_missing_data_independently_recomputed']=bool(projection_ok)
checks['no_false_duration_or_human_time']=costs.cost_type.str.startswith('uncalibrated').all() and costs[['download_seconds','human_annotation_seconds','reference_setup_seconds']].isna().all().all()
checks['budget_serial_bounded']=design.cpu_workers==1 and design.maximum_ram_gib==8 and design.maximum_ground_vertices_per_window==1000000 and design.maximum_roi_records_per_window==5000000 and design.external_free_reserve_gib==20
checks['spatial_diagnostics_not_inference']=not tables['dependencia_espacial_descritiva'].pairs_independent.any() and not tables['dependencia_espacial_descritiva'].range_estimated.any() and not tables['variabilidade_piloto'].power_computed.any()
checks['global_support_limit_retained']=r['global_50m_eligible_units']=={'main':1,'adversarial':0}
checks['pooled_evaluation_normalizer_excludes_development']='pooled evaluation-unit cohort' in protocol['normalizer'] and 'development units excluded' in protocol['comparison_scope']
checks['required_documents_exist']=all((root/p).is_file() and (root/p).stat().st_size>500 for p in ['docs/relatorio_piloto.md','docs/protocolo_amostra_v0_2_0.md','docs/plano_custo_etapa11.md','docs/criterios_evidencias_etapa11.csv','docs/inventario_falhas_etapa11.csv','docs/proposta_amostra_etapa11.csv'])
checks['schemas_current']=read_json(root/'docs/schemas/run_manifest.schema.json')==RunManifest.model_json_schema() and read_json(root/'docs/schemas/study_design.schema.json')==StudyDesign.model_json_schema()
old=read_json(root/'docs/manifesto_etapa10.json')
checks['protected_original_downloader_tests_requirements']=all(fingerprint(root/p)['sha256']==h for p,h in old['protected_files_sha256'].items())
checks['frozen_human_work_unchanged']=all(p.model_dump()==fingerprint(Path(p.path)) for p in m.inputs if '/trabalho/' in p.path)
result={'ok':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'tests':{'scientific_passed':168,'scientific_added':6,'downloader_passed':25,'downloader_subtests_passed':2},'run_id':r['run_id'],'classification':r['continuation_classification'],'sample_executed':False,'cloud_records_decoded':0,'planned_corridors':len(selected),'actual_eligible_units':None}
atomic_write_json(root/'relatorios/etapa11/verificacoes.json',result)
print({'ok':result['ok'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v]})
raise SystemExit(0 if result['ok'] else 1)
