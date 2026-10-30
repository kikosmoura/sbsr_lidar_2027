"""Extrair evidências do piloto e regiões de mudança para documentação local."""
from pathlib import Path
import json
import geopandas as gpd
import numpy as np
import pandas as pd
from sbsr_lidar.storage import atomic_write_json, read_json

root=Path.cwd(); output=root/'relatorios/etapa10'; summaries={}
def records(frame): return json.loads(pd.DataFrame(frame).to_json(orient='records',double_precision=15))
for case in ['main','adversarial']:
 entry=read_json(output/f'execucao_{case}.json'); report=read_json(Path(entry['report'])); directory=Path(entry['products_root'])
 tables={name:pd.read_parquet(directory/f'{name}.parquet') for name in ['dominios_areas','comparacoes_suporte_comum','coorte_estrita','sensibilidade_densidade','ablacao_por_cenario','comparacoes_entre_escalas','mudancas_indicadores']}
 native=gpd.read_parquet(directory/'indicadores_nativos.parquet'); units=native.loc[native.scenario_id.eq('primary')&native.scale_m.eq(50),['unit_id','geometry']]
 changes=tables['mudancas_indicadores'].loc[tables['mudancas_indicadores'].scale_m.eq(50)].copy()
 spatial=units.merge(changes,on='unit_id'); spatial=gpd.GeoDataFrame(spatial,geometry='geometry',crs=units.crs)
 spatial['rank_changed']=spatial.rank_shift.ne(0)
 spatial.to_parquet(output/f'desacordos_{case}_50m.parquet',index=False)
 evidence={'run_id':report['run_id'],'products_root':str(directory),'elapsed_seconds':report['elapsed_seconds'],'peak_rss_mib':report['peak_process_rss_mib'],'roi_records':report['roi_records'],'maximum_ground_vertices':report['maximum_ground_vertices'],
 'common_global_area_m2':report['global_common_area_m2'],'primary_observed_area_m2':report['primary_observed_area_m2'],
 'native_domains_areas':records(tables['dominios_areas']),
 'eligible_native_50':records(native.loc[native.scale_m==50].groupby('scenario_id',sort=False).agg(eligible_A=('eligible_A','sum'),eligible_A_plus_3D=('eligible_A_plus_3D','sum')).reset_index()),
 'paired_comparison_50':records(tables['comparacoes_suporte_comum'].loc[tables['comparacoes_suporte_comum'].scale_m==50]),
 'cohorts':records(tables['coorte_estrita']),
 'A_vs_A3D_native_50':records(tables['ablacao_por_cenario'].loc[tables['ablacao_por_cenario'].scale_m==50]),
 'cross_scale':records(tables['comparacoes_entre_escalas']),
 'density_50':records(tables['sensibilidade_densidade'].loc[tables['sensibilidade_densidade'].scale_m==50]),
 'aggregation_check':report['aggregation_check']}
 freq=gpd.read_parquet(directory/'estabilidade_receitas.parquet'); freq=freq.loc[freq.scale_m==50]
 evidence['score_recipe_frequency_50']={'units':len(freq),'recipes':int(freq.n_scenarios.iloc[0]) if len(freq) else 0,
 'units_never_in_operational_top':int(freq.priority_frequency.eq(0).sum()),'units_always_in_operational_top':int(freq.priority_frequency.eq(1).sum()),
 'units_sometimes_in_operational_top':int(freq.priority_frequency.between(0,1,inclusive='neither').sum()),
 'largest_mean_rank_range':float(freq.rank_range.max()) if len(freq) else None}
 terms=['score_contribution_'+k for k in ['I1','I4','I6','I7']]
 evidence['mean_absolute_score_change_contribution_50_by_axis']=records(changes.groupby('axis')[terms].agg(lambda x:float(x.abs().mean())).reset_index())
 summaries[case]=evidence
atomic_write_json(output/'resumo_para_relatorio.json',summaries)
print(output/'resumo_para_relatorio.json')
