"""Reunir os pares já calculados no suporte comum, mantendo as coortes fixas."""
from pathlib import Path
import geopandas as gpd
import pandas as pd
from sbsr_lidar.config import load_config
from sbsr_lidar.crown_plan import crown_scenarios
from sbsr_lidar.crown_metrics import paired_rank_stability
from sbsr_lidar.crown_data import write_frame
from sbsr_lidar.storage import read_json,atomic_write_json,fingerprint


def main():
    result=read_json(Path('relatorios/etapa12/execucao.json'));root=Path(result['products_root'])
    config=load_config(Path('configs/terreno_congelado_etapa04.yaml'))
    cohort=gpd.read_parquet(root/'coorte_selecionada.parquet');rows=[]
    for scenario in crown_scenarios()[1:]:
        for role in ['development','evaluation']:
            left=[];right=[]
            for cid,record in result['case_results'].items():
                if record['role']!=role:continue
                base=Path(record['root'])/scenario.scenario_id
                left.append(gpd.read_parquet(base/'principal_suporte_comum.parquet'))
                right.append(gpd.read_parquet(base/'cenario_suporte_comum.parquet'))
            fixed=cohort.loc[cohort.role.eq(role),'unit_id'].tolist()
            a=gpd.GeoDataFrame(pd.concat(left,ignore_index=True),geometry='geometry',crs=31983)
            b=gpd.GeoDataFrame(pd.concat(right,ignore_index=True),geometry='geometry',crs=31983)
            if a.unit_id.duplicated().any() or b.unit_id.duplicated().any():raise ValueError('IDs repetidos na consolidação')
            row={'role':role,'scenario_id':scenario.scenario_id,**paired_rank_stability(a,b,config,fixed),
                'common_support_scope':'exact_same_vector_V_intersection_for_each_corridor_before_pooling',
                'normalizer_scope':'identical_surviving_frozen_unit_IDs_pooled_within_role',
                'no_replacement_of_excluded_units':True,'external_accuracy_metric':False,'p_value_computed':False}
            if row['paired_eligible_units']>row['frozen_primary_units']:raise ValueError('Coorte aumentou indevidamente')
            rows.append(row)
    table=pd.DataFrame(rows);dest=root/'sensibilidade_rankings_agrupada.parquet';write_frame(table,dest)
    atomic_write_json(Path('relatorios/etapa12/sensibilidade_agrupada.json'),{'output':fingerprint(dest),'rows':len(table),
        'all_22_predeclared_scenario_role_pairs_present':len(table)==22,'primary_IDs_unchanged':True,
        'all_paired_universes_not_larger_than_frozen_primary':bool((table.paired_eligible_units<=table.frozen_primary_units).all()),
        'external_accuracy_evaluated':False,'p_values_computed':False})
    print(table[['role','scenario_id','paired_eligible_units','spearman_rho','jaccard_exact']].to_string(index=False))


if __name__=='__main__':main()
