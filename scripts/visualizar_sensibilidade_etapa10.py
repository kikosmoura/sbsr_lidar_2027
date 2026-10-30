"""Figuras locais do piloto: suporte e frequências descritivas, sem acurácia implícita."""
import argparse
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr-matplotlib')
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from sbsr_lidar.storage import read_json

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('report',type=Path)
p.add_argument('--output-dir',type=Path,default=Path('relatorios/etapa10'))
a=p.parse_args(); r=read_json(a.report); root=Path(r['products_root']); a.output_dir.mkdir(parents=True,exist_ok=True)
areas=pd.read_parquet(root/'dominios_areas.parquet'); pairs=pd.read_parquet(root/'comparacoes_suporte_comum.parquet')
physical=gpd.read_parquet(root/'estabilidade_fisica.parquet'); recipes=gpd.read_parquet(root/'estabilidade_receitas.parquet')
native=gpd.read_parquet(root/'indicadores_nativos.parquet'); outlines=native.loc[(native.scenario_id=='primary')&(native.scale_m==50)]
fig,axes=plt.subplots(2,2,figsize=(14,12),layout='constrained')
f=areas.loc[~areas.population_changed].copy(); f['fraction']=f.observed_area_m2/f.measurement_area_m2
axes[0,0].barh(f.scenario_id,f.fraction,color='#34758c'); axes[0,0].set(xlim=(0,1.03),xlabel='Área observada / P',title='Suporte nativo: cenário e aquisição'); axes[0,0].invert_yaxis(); axes[0,0].tick_params(axis='y',labelsize=7)
f=pairs.loc[pairs.scale_m==50].copy(); axes[0,1].barh(f.scenario_id,pd.to_numeric(f.spearman_rho),color='#8b5a3c')
axes[0,1].set(xlim=(-1,1.03),xlabel='Spearman descritivo A+3D: principal × cenário',title='Mesma interseção observada e mesma coorte por par'); axes[0,1].invert_yaxis(); axes[0,1].tick_params(axis='y',labelsize=7)
if not f.spearman_rho.notna().any():
 axes[0,1].clear(); axes[0,1].set_axis_off(); axes[0,1].text(.5,.5,'Spearman indisponível\nn < 3 ou variável constante\nNenhum valor foi imputado',transform=axes[0,1].transAxes,ha='center',va='center',fontsize=14)
for ax,table,title in [(axes[1,0],recipes,'Receitas de escore: suporte congelado'),(axes[1,1],physical,'Densidade: alturas com máscara fixa')]:
 outlines.boundary.plot(ax=ax,color='#777777',linewidth=.35)
 if 'ensemble' in table:
  subset=table.loc[table.scale_m.eq(50)]
  if table is physical: subset=subset.loc[subset.ensemble.eq('physical_axis_density_height_only')]
 else: subset=table.iloc[:0]
 if len(subset):
  subset.plot(column='priority_frequency',ax=ax,cmap='viridis',vmin=0,vmax=1,legend=True,legend_kwds={'label':'Frequência top 20% (IDs para desempate)'})
  n=int(subset.cohort_n.iloc[0]); count=int(subset.n_scenarios.iloc[0])
  ax.set_title(title+f'\nn={n}, {count} cenários'+('\nLista pequena; desempates podem dominar' if n<5 else ''))
 else:
  ax.text(.5,.5,'Sem coorte comum elegível',transform=ax.transAxes,ha='center'); ax.set_title(title)
 ax.set_aspect('equal'); ax.set_xlabel('E (EPSG:31983)'); ax.set_ylabel('N (m)'); ax.ticklabel_format(style='plain',useOffset=False); ax.tick_params(labelsize=7)
fig.suptitle(f"{r['corridor_id']} — etapa 10 exploratória\nFrequência não é probabilidade de intervenção; máscara não validada; sem intervalos de confiança",fontsize=13)
output=a.output_dir/f"sensibilidade_{r['case']}.png"; fig.savefig(output,dpi=180); plt.close(fig); print(output)
