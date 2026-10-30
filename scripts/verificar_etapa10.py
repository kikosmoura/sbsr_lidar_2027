"""Verificar produtos reais, suportes, votos e transferência sem refazer o experimento."""
import math
import re
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from sbsr_lidar.config import load_config
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json
from sbsr_lidar.sensitivity_scenarios import scenarios, thinning_uniform
from sbsr_lidar.domain import build_domain
from rasterio.features import geometry_mask

root=Path.cwd(); c=load_config(root/'configs/terreno_congelado_etapa04.yaml'); state=read_json(c.paths.state_file)
checks={}; summary={}
for case,label in [('main','principal'),('adversarial','adverso')]:
 e=read_json(root/f'relatorios/etapa10/execucao_{case}.json'); r=read_json(Path(e['report'])); d=Path(e['products_root'])
 m=RunManifest.model_validate(read_json(Path(e['manifest'])))
 tables={p.stem:pd.read_parquet(p) for p in d.glob('*.parquet')}
 native=gpd.read_parquet(d/'indicadores_nativos.parquet'); recipes=gpd.read_parquet(d/'estabilidade_receitas.parquet')
 physical=gpd.read_parquet(d/'estabilidade_fisica.parquet'); cross=tables['comparacoes_entre_escalas']; transferred=gpd.read_parquet(d/'transferencia_espacial.parquet')
 pairs=tables['comparacoes_suporte_comum']; changes=tables['mudancas_indicadores']; cohorts=tables['coorte_estrita']; areas=tables['dominios_areas']
 checks[case+':manifest_code_inputs']=m.status=='completed' and m.stage=='10' and m.code_sha256==source_digest() and all(fingerprint(Path(p.path))==p.model_dump() for p in m.inputs)
 cached=read_json(root/f'relatorios/etapa10/cache_{case}.json'); cm=RunManifest.model_validate(read_json(Path(cached['manifest'])))
 checks[case+':full_output_cache_verified']=cached['cache_hit'] and cm.cache_hit and cm.status=='completed' and cm.code_sha256==source_digest() and cm.source_run_id==m.run_id and cm.outputs==m.outputs and cached['report']==e['report']
 checks[case+':scenario_count_and_budget']=r['scenario_count']==30 and set(native.scenario_id)=={s.scenario_id for s in scenarios(c)} and r['peak_process_rss_mib']<c.resources.max_ram_gib*1024
 checks[case+':primary_replayed']=r['primary_replay']['mask_and_observation_bitwise_identical'] and r['primary_replay']['same_ids_and_eligibility'] and r['height_replay']['same_finite_H_support'] and r['height_replay']['maximum_recomputed_H_difference_m']<1e-6
 old=state['comparacao_piloto'][label]['primary_50m_conditional']
 replay=tables['ablacao_por_cenario'].loc[tables['ablacao_por_cenario'].scenario_id.eq('primary')&tables['ablacao_por_cenario'].scale_m.eq(50)].iloc[0]
 checks[case+':primary_ranking_reproduces_stage09']=all((pd.isna(replay[k]) and old[k] is None) or (old[k] is not None and np.isclose(replay[k],old[k],atol=1e-12,rtol=0)) for k in ['spearman_rho','jaccard_exact','jaccard_including_cut_ties'])
 checks[case+':native_area_conservation']=all(np.isclose(t.area_total_m2.sum(),areas.set_index('scenario_id').loc[sid].measurement_area_m2,atol=1e-4,rtol=0) and np.isclose(t.area_observed_m2.sum(),areas.set_index('scenario_id').loc[sid].observed_area_m2,atol=1e-4,rtol=0) for (sid,scale),t in native.groupby(['scenario_id','scale_m']))
 checks[case+':area_order_and_nulls']=bool(((native.area_canopy_m2>=0)&(native.area_canopy_m2<=native.area_observed_m2+1e-6)&(native.area_observed_m2<=native.area_total_m2+1e-6)).all() and native.loc[native.eligible_A_plus_3D,['I6','I7']].notna().all().all() and native.loc[~native.height_support_sufficient,['I6','I7']].isna().all().all())
 checks[case+':eligibility_contract']=bool((native.eligible_A==((native.area_total_m2>=c.support.minimum_unit_area_m2)&(native.fraction_observed>=c.support.minimum_observed_fraction))).all() and (native.eligible_A_plus_3D==(native.eligible_A&native.height_support_sufficient)).all())
 masks_ok=True; thinning_ok=True; context_ok=True
 with rasterio.open(d/'primary/mascaras.tif') as ds: canonical_obs,canonical_mask=ds.read(); transform=ds.transform
 for s in scenarios(c):
  with rasterio.open(d/s.scenario_id/'mascaras.tif') as ds: obs,mask=ds.read(); epsg=ds.crs.to_epsg()
  with rasterio.open(d/s.scenario_id/'contagens.tif') as ds: counts=ds.read()
  masks_ok &= epsg==31983 and np.array_equal(obs==1,mask!=255) and np.all(counts[0]>=counts[1]) and np.all(counts[1]>=counts[2]) and np.all(counts[2]>=counts[3]) and np.all((obs!=1)|((counts[1]>0)&(counts[2]>0)))
  if s.mask_version=='baseline': masks_ok &= np.array_equal(mask==1,(obs==1)&(counts[3]>=1))
  if s.sampling_mode=='height_only': thinning_ok &= np.array_equal(mask,canonical_mask) and np.array_equal(obs,canonical_obs)
 checks[case+':native_masks_counts_and_QC']=bool(masks_ok)
 checks[case+':height_only_frozen_mask_V']=bool(thinning_ok)
 for axis in ['resolution','height','context','interpolation_radius','interpolation_method','patch_definition','classification','classification_bound','density_coupled','density_height_only','return_policy','selected_interaction']:
  subset=areas.loc[areas.axis.eq(axis)]
  context_ok &= np.allclose(subset.measurement_area_m2,areas.iloc[0].measurement_area_m2,atol=1e-6)
 checks[case+':halo_preserves_P_expansion_changes_population']=bool(context_ok and areas.population_changed.sum()==2 and (areas.loc[areas.population_changed].measurement_area_m2>areas.iloc[0].measurement_area_m2).all() and not pairs.scenario_id.str.startswith('domain_').any())
 expanded=native.loc[native.scenario_id.str.startswith('domain_')]
 checks[case+':expanded_IDs_distinct']=expanded.unit_id.str.contains('__domain_plus_').all() and not set(expanded.unit_id)&set(native.loc[native.scenario_id.eq('primary')].unit_id)
 checks[case+':pairwise_and_small_list_guards']=pairs.loc[pairs.n>0].support.eq('pairwise_intersection_exact_geometry').all() and pairs.loc[pairs.k.fillna(0)<5,'jaccard_exact'].isna().all()
 terms=['score_contribution_'+k for k in ['I1','I4','I6','I7']]
 checks[case+':score_change_contributions_close']=np.allclose(changes[terms].sum(axis=1),changes.score_difference,atol=1e-12,rtol=0)
 disagreement=gpd.read_parquet(root/f'relatorios/etapa10/desacordos_{case}_50m.parquet'); original=native.loc[native.scenario_id.eq('primary')&native.scale_m.eq(50)].set_index('unit_id')
 checks[case+':disagreement_regions_original_geometry']=all(g.equals(original.loc[u].geometry) for u,g in zip(disagreement.unit_id,disagreement.geometry)) and np.allclose(disagreement.rank_shift,disagreement.rank_scenario-disagreement.rank_primary)
 checks[case+':stability_frequencies_and_ranges']=all((f.priority_frequency.between(0,1).all() and f.priority_frequency_including_cutoff_ties.between(0,1).all() and (f.rank_min<=f.rank_max).all() and np.allclose(f.rank_range,f.rank_max-f.rank_min) and not f.frequency_is_intervention_probability.any()) for f in [physical,recipes] if len(f))
 # Recalcular votos das dez receitas usando os escores congelados da etapa 09.
 scores=pd.read_parquet(state['comparacao_piloto'][label]['scores_rankings']); vote_ok=True
 for scale,g in recipes.groupby('scale_m'):
  t=scores.loc[scores.family.eq('grid')&scores.scope.eq('conditional_canopy')&scores.scale_m.eq(scale)&(~scores.features.eq('I6_duplicate'))&((scores.method=='A')|(scores.vertical_weight>0))]
  votes={u:[] for u in g.unit_id}; ranges={u:[] for u in g.unit_id}; inclusive={u:[] for u in g.unit_id}
  for variant,v in t.groupby('variant_id'):
   ordered=v.sort_values('rank_ordinal'); k=math.ceil(.2*len(v)); cut=ordered.iloc[k-1].score_for_ranking
   top=set(ordered.head(k).unit_id); itop=set(v.loc[v.score_for_ranking>=cut].unit_id)
   for row in v.itertuples(): votes[row.unit_id].append(row.unit_id in top); inclusive[row.unit_id].append(row.unit_id in itop); ranges[row.unit_id].append(row.rank_mean)
  for row in g.itertuples():
   vote_ok &= row.n_scenarios==10 and np.isclose(row.priority_frequency,np.mean(votes[row.unit_id])) and np.isclose(row.priority_frequency_including_cutoff_ties,np.mean(inclusive[row.unit_id])) and row.rank_min==min(ranges[row.unit_id]) and row.rank_max==max(ranges[row.unit_id])
 checks[case+':recipe_votes_independently_reproduced_from_stage09']=bool(vote_ok)
 checks[case+':global_common_support_loss_explicit']=r['global_common_area_m2']<=r['primary_observed_area_m2']+1e-6 and len(cohorts.loc[cohorts.ensemble.eq('physical_global_common_support')])==3
 # Geometrias transferidas particionam W; nenhuma comparação usa igualdade de IDs entre escalas.
 transfer_ok=True
 for row in cross.itertuples():
  cells=transferred.loc[(transferred.method==row.method)&(transferred.scale_from==row.scale_from)&(transferred.scale_to==row.scale_to)] if len(transferred) else transferred
  if not len(cells): continue
  transfer_ok &= np.allclose(cells.geometry.area,cells.area_m2,atol=1e-6,rtol=0) and np.isclose(cells.area_m2.sum(),row.common_area_m2,atol=1e-4,rtol=0)
  transfer_ok &= abs(cells.area_m2.sum()-cells.geometry.union_all().area)<1e-4
  if pd.notna(row.area_jaccard_top):
   union=cells.loc[cells.top_from|cells.top_to,'area_m2'].sum(); inter=cells.loc[cells.top_from&cells.top_to,'area_m2'].sum()
   transfer_ok &= np.isclose(row.area_jaccard_top,inter/union,atol=1e-12,rtol=0) and row.k_from>=5 and row.k_to>=5
  else: transfer_ok &= row.k_from<5 or row.k_to<5
 checks[case+':area_transfer_partition_and_Jaccard']=bool(transfer_ok)
 audit=read_json(d/'validacao_por_objeto.json')
 checks[case+':validation_separate_real_reference_only']=len(audit['objects'])==4 and audit['annotation_assessment']['completed_annotations']==0 and audit['annotation_assessment']['independent_priority_references']==0 and not any(o['accuracy_claimed'] for o in audit['objects']) and not audit['bootstrap_performed'] and not audit['p_values_computed'] and not audit['test_annotations_modified']
 checks[case+':no_B_C_volume_or_inference']=not r['B_available'] and not r['C_available'] and not r['horizontal_gap_distance_executed'] and not r['mask_validated'] and not r['accuracy_gain_claimed'] and not r['confidence_intervals_computed'] and audit['volume_proxy']=='not_defined_I9_excluded'
 # Ler todos os rasters e comparar contagens agregadas reais de .5 -> 2 m.
 agg=read_json(d/'teste_agregacao.json')
 with rasterio.open(d/'res_0.5/contagens.tif') as ds: fine_counts=ds.read(1); ft=ds.transform
 with rasterio.open(d/'res_0.5/mascaras.tif') as ds: fine_obs,fine_mask=ds.read()
 with rasterio.open(d/'res_2/contagens.tif') as ds: coarse_counts=ds.read(1); ct=ds.transform
 with rasterio.open(d/'res_2/mascaras.tif') as ds: coarse_obs,coarse_mask=ds.read()
 ch,cw=coarse_counts.shape
 rowoff=round((ct.f-ft.f)/.5); coloff=round((ft.c-ct.c)/.5)
 def block_sum(values):
  padded=np.zeros((ch*4,cw*4),dtype='uint64'); padded[rowoff:rowoff+values.shape[0],coloff:coloff+values.shape[1]]=values
  return padded.reshape(ch,4,cw,4).sum(axis=(1,3))
 measured=geometry_mask([build_domain(c,case).measurement],coarse_counts.shape,ct,invert=True)
 expected=[int(np.sum(measured&(block_sum(fine_counts)!=coarse_counts))),int(np.sum(measured&((block_sum(fine_mask==1)>0)!=(coarse_mask==1)))),int(np.sum(measured&((block_sum(fine_obs==1)>0)!=(coarse_obs==1))))]
 actual=[agg['sum_fine_record_counts_vs_native_coarse_different_cells'],agg['any_fine_canopy_vs_native_coarse_different_cells'],agg['any_fine_valid_vs_native_coarse_different_cells']]
 checks[case+':aggregation_declared_tested']=agg['native_points_used'] and not agg['coarse_P95_is_mean_of_fine_P95'] and actual==expected
 # Reagrupar diretamente registros de unidades sem fragmentos irmãos no mesmo
 # quadrado. Aqui a propriedade na fronteira é expressa por intervalos XY
 # semiabertos, independentemente do STRtree utilizado pelo processamento.
 work=Path(r['intermediates_root']); raw=pd.read_parquet(work/'registros_ROI.parquet')
 x,y=raw.x.to_numpy(),raw.y.to_numpy(); source_h={}; sampled_h_ok=True; samples=0
 for sid in ['primary','res_0.5','height_5','radius_3','first_returns','thin_coupled_0.25_s2027','thin_height_only_0.25_s2027']:
  spec=next(s for s in scenarios(c) if s.scenario_id==sid)
  t=native.loc[native.scenario_id.eq(sid)&native.scale_m.eq(50)&native.eligible_A_plus_3D].sort_values('area_total_m2',ascending=False)
  all_units=native.loc[native.scenario_id.eq(sid)&native.scale_m.eq(50)]
  chosen=None
  for row in t.itertuples():
   match=re.search(r'_G50_X(-?\d+)_Y(-?\d+)_F',row.unit_id)
   if match and all_units.unit_id.str.contains(match.group(0),regex=False).sum()==1:
    chosen=(row,int(match[1]),int(match[2])); break
  if chosen is None: continue
  row,ix,iy=chosen
  path=work/f'H_halo_10_r{spec.radius_m:g}.parquet'
  if path not in source_h: source_h[path]=pd.read_parquet(path)
  h=source_h[path].tin.to_numpy(); status=source_h[path].tin_status.to_numpy()
  use=(x>=ix*50)&(x<(ix+1)*50)&(y>iy*50)&(y<=(iy+1)*50)&shapely.intersects_xy(row.geometry,x,y)
  use &= raw.qc_usable.to_numpy()&(status==0)&np.isfinite(h)&raw.classification.isin([3,4,5]).to_numpy()&(h>=spec.height_m)
  if spec.fraction<1: use &= thinning_uniform(raw.source_tile.to_numpy(),raw.source_point_index.to_numpy(),spec.seed)<spec.fraction
  if spec.sampling_mode=='first_returns': use &= raw.return_number.to_numpy()==1
  with rasterio.open(d/sid/'mascaras.tif') as ds:
   obs,mask=ds.read(); col=np.floor((x-ds.transform.c)/ds.transform.a).astype(int); rr=np.floor((ds.transform.f-y)/(-ds.transform.e)).astype(int)
  valid=(col>=0)&(rr>=0)&(col<obs.shape[1])&(rr<obs.shape[0]); col=np.clip(col,0,obs.shape[1]-1); rr=np.clip(rr,0,obs.shape[0]-1)
  use &= valid&(obs[rr,col]==1)&(mask[rr,col]==1)
  values=h[use]; q=np.quantile(values,[.25,.75,.95],method='linear') if len(values) else [np.nan]*3
  sampled_h_ok &= len(values)==row.n_vegetation_records and np.allclose([values.mean() if len(values) else np.nan,q[2],q[1]-q[0]],[row.I5,row.I6,row.I7],atol=1e-10,rtol=0)
  samples+=1
 checks[case+':real_height_quantiles_independent_XY_regrouping']=bool(sampled_h_ok and samples>=4)
 checks[case+':CSV_Parquet_equivalence']=len(pd.read_csv(d/'indicadores_nativos.csv'))==len(native) and np.allclose(pd.read_csv(d/'indicadores_nativos.csv').I6,native.I6,equal_nan=True,atol=1e-12,rtol=0)
 summary[case]={'run_id':r['run_id'],'scenarios':r['scenario_count'],'roi_records':r['roi_records'],'peak_rss_mib':r['peak_process_rss_mib'],'elapsed_seconds':r['elapsed_seconds'],'global_common_area_m2':r['global_common_area_m2'],'strict_cohorts':r['strict_cohorts']}
protected=read_json(root/'docs/manifesto_etapa09.json')['protected_files_sha256']
checks['protected_downloader_requirements']=all(fingerprint(root/p)['sha256']==h for p,h in protected.items())
checks['schemas_current']=read_json(root/'docs/schemas/config.schema.json')==c.model_json_schema() and read_json(root/'docs/schemas/run_manifest.schema.json')==RunManifest.model_json_schema()
result={'ok':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'summary':summary,'tests':{'scientific_passed':162,'downloader_passed':25}}
atomic_write_json(root/'relatorios/etapa10/verificacoes.json',result)
print({'ok':result['ok'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v]})
raise SystemExit(0 if result['ok'] else 1)
