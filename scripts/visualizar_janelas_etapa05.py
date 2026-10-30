"""Mapa administrativo da seleção; não integra a primeira passagem de anotação."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr_mpl_etapa05')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import geopandas as gpd

from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=Path('configs/terreno_congelado_etapa04.yaml'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();config=load_config(args.config)
    selected=gpd.read_file(args.package/'quadro_amostral.gpkg',layer='selecionadas')
    fig,axes=plt.subplots(1,2,figsize=(11,8),layout='constrained')
    for ax,case in zip(axes,['main','adversarial']):
        domain=build_domain(config,case)
        gpd.GeoSeries([domain.context],crs=config.grid.epsg).plot(ax=ax,color='#ececea',edgecolor='#b8b8b8',linewidth=.6)
        gpd.GeoSeries([domain.measurement],crs=config.grid.epsg).boundary.plot(ax=ax,color='#333333',linewidth=.8)
        rows=selected.loc[selected.case==case]
        for row in rows.itertuples():
            color='#cb6a37' if row.intended_use=='qa' else '#316d9c'
            gpd.GeoSeries([row.geometry],crs=config.grid.epsg).boundary.plot(ax=ax,color=color,linewidth=1.)
            center=row.geometry.centroid
            ax.annotate(row.window_id[-4:],(center.x,center.y),xytext=(2,1),textcoords='offset points',fontsize=6)
        ax.set_title(f'{domain.corridor_id}\n{len(rows)} janelas / {sum(rows.intended_use=="qa")} de QA',fontsize=11)
        ax.set_xlabel('E (m)');ax.set_ylabel('N (m)')
        ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(labelsize=8,axis='x',rotation=30)
        ax.set_aspect('equal')
    fig.suptitle('Plano de janelas — referência do piloto\nIDs abreviados pelos quatro caracteres finais; rótulos humanos pendentes',fontsize=12)
    fig.legend(handles=[Patch(facecolor='none',edgecolor='#316d9c',label='Janela de treino/teste futuro'),
                        Patch(facecolor='none',edgecolor='#cb6a37',label='Janela de QA'),
                        Patch(facecolor='#ececea',label='Contexto')],loc='outside lower center',ncol=3,fontsize=9)
    args.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(args.output,dpi=180);plt.close(fig)


if __name__=='__main__':main()
