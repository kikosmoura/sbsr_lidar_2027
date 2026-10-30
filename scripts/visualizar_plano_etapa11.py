"""Mapa da proposta espacial e envelope heurístico de custo, sem amostra executada."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr-matplotlib')
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from sbsr_lidar.storage import read_json

root=Path.cwd(); e=read_json(root/'relatorios/etapa11/execucao.json'); d=Path(e['products_root'])
f=gpd.read_parquet(d/'ordem_candidatos.parquet'); selected=f.loc[f.selected_for_planning.eq(True)]
cost=pd.read_parquet(d/'estimativa_custo.parquet')
fig,(ax,bx)=plt.subplots(1,2,figsize=(15,10),gridspec_kw={'width_ratios':[1.2,1]})
fig.subplots_adjust(left=.07,right=.97,top=.87,bottom=.24,wspace=.35)
f.boundary.plot(ax=ax,color='#999999',linewidth=.4)
f.loc[f.planning_eligible].plot(ax=ax,color='#b9d5e4',edgecolor='#7795a5',linewidth=.3)
colors={'avaliacao':'#227e62','desenvolvimento':'#dd7722'}
for role,color in colors.items():
 s=selected.loc[selected.proposed_role.eq(role)]
 s.plot(ax=ax,color=color,edgecolor='#222222',linewidth=.8)
 points=s.geometry.representative_point(); ax.scatter(points.x,points.y,s=22,c=color,zorder=5)
 for row in s.itertuples():
  pt=row.geometry.representative_point(); ax.annotate(row.corridor_id,(pt.x,pt.y),xytext=(5,4),textcoords='offset points',fontsize=8,color=color)
ax.legend(handles=[Patch(facecolor='#b9d5e4',label='Candidato geométrico'),Patch(facecolor=colors['avaliacao'],label='8 propostos para avaliação'),Patch(facecolor=colors['desenvolvimento'],label='2 propostos para desenvolvimento')],loc='upper left',bbox_to_anchor=(0,-.1),fontsize=9)
ax.set(title='Cadastro e proposta em blocos distintos de proximidade',xlabel='E (m), EPSG:31983',ylabel='N (m)'); ax.ticklabel_format(style='plain',useOffset=False); ax.set_aspect('equal')
y=np.arange(len(cost)); base=cost.estimated_baseline_area_seconds_budget/3600; sensitivity=cost.estimated_additional_sensitivity_seconds_budget/3600
bx.barh(y,base,color='#34758a',label='Pipeline base: orçamento por área')
bx.barh(y,sensitivity,left=base,color='#956c4b',label='Sensibilidade adicional: orçamento por área')
bx.set_yticks(y,[f'{int(n)} corredores' for n in cost.planned_corridors]); bx.invert_yaxis(); bx.set(xlabel='Horas estimadas com fator 3 (um trabalhador)',title='Envelope de planejamento — não é previsão validada')
for i,(a,b,g) in enumerate(zip(base,sensitivity,cost.estimated_derived_bytes_budget/2**30)):
 bx.text(a+b+.03,i,f'{a+b:.2f} h; {g:.2f} GiB',va='center',fontsize=9)
bx.set_xlim(0,float((base+sensitivity).max())*1.32); bx.legend(loc='upper left',bbox_to_anchor=(0,-.12),fontsize=9)
fig.text(.55,.025,'Downloads, referência e tempo humano não estimados.\nCabeçalhos faltantes impedem estimativa completa por registros.\nReservar 20 GiB externos além dos derivados e dos downloads.',fontsize=9,va='bottom')
fig.suptitle('Etapa 11 — proposta condicional pós-piloto, sem novos retornos processados\nGrupos a 1 km não certificam independência; máscara e referência continuam pendentes',fontsize=14)
path=root/'relatorios/etapa11/proposta_e_custo.png'; fig.savefig(path,dpi=180); plt.close(fig); print(path)
