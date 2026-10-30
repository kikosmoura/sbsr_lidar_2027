"""Mapas de regras exploratórias; não mostrar aos intérpretes na passagem cega."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr_mpl_etapa06')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.plot import plotting_extent

from sbsr_lidar.storage import read_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();r=read_json(args.report)
    products={Path(p).name:Path(p) for p in r['products']}
    aoi=gpd.read_file(products['mascaras_manchas.gpkg'],layer='medicao')
    height=r['analysis_version'].split('_h')[-1]
    colors=['#e9e4d5','#2c8068','#dcaa48','#b7bfca','#ffffff']
    with rasterio.open(products['observabilidade.tif']) as ds:
        observation=ds.read(1);extent=plotting_extent(ds)
    context=observation!=255
    def draw(ax,values,title,observation_map=False):
        if observation_map:
            palette=['#b6dbda','#b7bfca','#d6a48f','#b49abf','#ffffff']
            view=np.full(values.shape,4,dtype=np.uint8)
            for index,code in enumerate([1,2,3,4]):view[values==code]=index
            cmap=ListedColormap(palette)
        else:
            view=values.copy();view[values==255]=3;view[~context]=4;cmap=ListedColormap(colors)
        ax.imshow(view,cmap=cmap,vmin=0,vmax=4,extent=extent,interpolation='nearest')
        aoi.boundary.plot(ax=ax,color='#242424',linewidth=.6)
        ax.set_xlim(extent[:2]);ax.set_ylim(extent[2:]);ax.set_aspect('equal')
        ax.set_title(title,fontsize=10);ax.set_xlabel('E (m)');ax.set_ylabel('N (m)')
        ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(axis='x',rotation=30,labelsize=8);ax.tick_params(axis='y',labelsize=8)
    fig,axes=plt.subplots(1,3,figsize=(14,8),layout='constrained')
    draw(axes[0],observation,'Observação e suporte',True)
    axes[0].legend(handles=[Patch(color=color,label=label) for color,label in
        [('#b6dbda','MDS + terreno + H'),('#b7bfca','Sem observação'),('#d6a48f','Sem suporte de terreno'),('#b49abf','Somente excluídos')]],
        loc='lower left',fontsize=6)
    for ax,version,title in zip(axes[1:],['baseline','refinada'],['Baseline','Refino experimental']):
        with rasterio.open(products[f'copa_{version}_h{height}_contexto.tif']) as ds:values=ds.read(1)
        s=r['scenarios'][f'{version}_h{height}']
        draw(ax,values,f"{title}, H≥{height} m\nÁrea candidata em P: {s['candidate_area_measurement_exact_m2']:,.1f} m²")
    fig.suptitle(f"{r['domain']['corridor_id']} — máscara candidata não validada\nLinha preta: medição · cores representam regras, não rótulos humanos",fontsize=12)
    legend=[Patch(color=colors[0],label='Sem candidato na regra'),Patch(color=colors[1],label='Copa candidata'),
            Patch(color=colors[2],label='Classificação incerta'),Patch(color=colors[3],label='Fora do suporte válido')]
    fig.legend(handles=legend,loc='outside lower center',ncol=4,fontsize=9)
    args.output_dir.mkdir(parents=True,exist_ok=True);fig.savefig(args.output_dir/f"copa_{r['case']}.png",dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,len(r['heights_m']),figsize=(14,8),layout='constrained')
    for ax,height in zip(np.atleast_1d(axes),r['heights_m']):
        key=f'baseline_h{height:g}'
        with rasterio.open(products[f'copa_{key}_contexto.tif']) as ds:values=ds.read(1)
        draw(ax,values,f"H≥{height:g} m\nÁrea candidata: {r['scenarios'][key]['candidate_area_measurement_exact_m2']:,.1f} m²")
    fig.suptitle(f"{r['domain']['corridor_id']} — sensibilidade do limiar de altura\nMesmas classes 3/4/5 e domínio observado; sem dilatação ou remoção por área",fontsize=12)
    fig.legend(handles=legend[:2]+legend[3:],loc='outside lower center',ncol=3,fontsize=9)
    fig.savefig(args.output_dir/f"sensibilidade_altura_{r['case']}.png",dpi=170);plt.close(fig)


if __name__=='__main__':main()
