"""Mapas e perfis dos produtos altimétricos existentes; não reprocessa nuvens."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr_mpl_etapa04')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.patches import Patch
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.plot import plotting_extent

from sbsr_lidar.storage import read_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    r=read_json(args.report)
    products={Path(p).name:Path(p) for p in r['products']}
    method=r['selected_method'];radius=f"{r['primary_radius_m']:g}"
    aoi=gpd.read_file(products['dominios.gpkg'],layer='medicao')
    fig,axes=plt.subplots(1,3,figsize=(14,8),layout='constrained')
    items=[(f'dtm_{method}_r{radius}_contexto.tif','Elevação do terreno (m)','terrain'),
           ('distancia_mdt_mais_proximo.tif','Distância ao MDT mais próximo (m)','magma_r'),
           (f'validade_{method}_r{radius}.tif','Validade do terreno','status')]
    colors=['#2b806b','#7e8ba5','#d99965','#ba5b66','#795a93','#c7b65c']
    for ax,(filename,title,cmap) in zip(axes,items):
        with rasterio.open(products[filename]) as ds:
            values=ds.read(1,masked=True)
            extent=plotting_extent(ds)
            kwargs={}
            if cmap=='status':
                cmap=ListedColormap(colors)
                kwargs['norm']=BoundaryNorm([-.5,.5,1.5,2.5,3.5,4.5,5.5],6)
            im=ax.imshow(values,cmap=cmap,extent=extent,interpolation='nearest',**kwargs)
            aoi.boundary.plot(ax=ax,color='black',linewidth=.7)
            ax.set_xlim(extent[:2]);ax.set_ylim(extent[2:])
            ax.set_title(title,fontsize=11)
            ax.ticklabel_format(useOffset=False,style='plain')
            ax.tick_params(axis='x',rotation=30,labelsize=8)
            ax.tick_params(axis='y',labelsize=8)
            ax.set_xlabel('E (m)');ax.set_ylabel('N (m)')
            if filename.startswith('validade'):
                ax.legend(handles=[Patch(color=colors[i],label=label) for i,label in
                    [(0,'Válido'),(1,'Fora da envoltória'),(2,'Vizinho além do raio'),(3,'Triângulo sem suporte')]],
                    loc='lower left',fontsize=7)
            else: fig.colorbar(im,ax=ax,shrink=.45)
    fig.suptitle(f"Terreno — {r['domain']['corridor_id']} / {method.upper()}, raio {radius} m\n"
                 'EPSG:31983 · linha preta: medição · branco: NoData/exterior · sem validação altimétrica externa',fontsize=12)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.output_dir/f"terreno_{r['domain']['case']}.png",dpi=160)
    plt.close(fig)
    profiles=pd.read_csv(products['perfis_cartesianos.csv'])
    fig,axes=plt.subplots(2,1,figsize=(11,6),layout='constrained')
    for ax,(name,group) in zip(axes,profiles.groupby('profile')):
        coordinate='x' if name=='E_W' else 'y'
        start=group[coordinate].min()
        grid_index=np.rint((group[coordinate]-start)/r['grid']['resolution_m']).astype(int)
        group=group.set_index(grid_index).reindex(range(int(grid_index.max())+1))
        group[coordinate]=start+group.index*r['grid']['resolution_m']
        ax.plot(group[coordinate],group.tin,label='TIN',linewidth=1)
        ax.plot(group[coordinate],group.idw,label='IDW',linewidth=1,alpha=.75)
        ax.set_title(f"Perfil cartesiano {name} — valores ausentes mantêm descontinuidade",fontsize=10)
        ax.set_xlabel('E (m)' if coordinate=='x' else 'N (m)')
        ax.set_ylabel('Elevação (m)');ax.legend();ax.grid(alpha=.2)
        ax.ticklabel_format(useOffset=False,style='plain')
    fig.suptitle(f"{r['domain']['corridor_id']} — perfis de inspeção; não são eixo longitudinal validado",fontsize=12)
    fig.savefig(args.output_dir/f"perfis_{r['domain']['case']}.png",dpi=160)
    plt.close(fig)


if __name__=='__main__': main()
