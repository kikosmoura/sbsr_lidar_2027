"""Figuras locais revisáveis de estimativas e estabilidade; sem alegar acurácia."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr-lidar-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds,Window
import shapely
import sys
from sbsr_lidar.storage import read_json


def main():
    preview=Path(sys.argv[1]) if len(sys.argv)>1 else None
    if preview is None:
        result=read_json(Path('relatorios/etapa12/execucao.json'));root=Path(result['products_root'])
        selection=gpd.read_parquet(root/'coorte_selecionada.parquet')
    else:
        qc=read_json(preview/'qc.json');cid=qc['domain']['corridor_id'];result={'case_results':{cid:{'root':str(preview)}}}
        selection=gpd.read_parquet(preview/'primary/coorte_50m.parquet');selection=selection.loc[selection.selected_primary_cohort]
    out=Path('relatorios/etapa12/figuras');out.mkdir(parents=True,exist_ok=True)
    for cid,case in result['case_results'].items():
        base=Path(case['root']);units=selection.loc[selection.corridor_id.eq(cid)].sort_values('selection_hash')
        if not len(units):continue
        center=units.iloc[0].geometry.representative_point();bounds=(center.x-65,center.y-65,center.x+65,center.y+65)
        tops=gpd.read_parquet(base/'primary/topos_estimados.parquet');crowns=gpd.read_parquet(base/'primary/copas_estimadas.parquet')
        fig,axes=plt.subplots(1,3,figsize=(14,5),constrained_layout=True)
        for ax,name in zip(axes,['chm','crowns','observation']):
            source=base/'rasters_r1_f1'/('chm.tif' if name!='observation' else 'observation.tif')
            with rasterio.open(source) as ds:
                w=from_bounds(*bounds,ds.transform).round_offsets().round_lengths();a=ds.read(1,window=w,boundless=True,masked=True);b=rasterio.windows.bounds(w,ds.transform)
            extent=[b[0],b[2],b[1],b[3]]
            if name=='observation':
                colors=ListedColormap(['#d9edca','#333333','#e7a23c','#bc4444']);im=ax.imshow(np.ma.masked_where(a==255,a),extent=extent,cmap=colors,vmin=.5,vmax=4.5,interpolation='nearest')
                cb=fig.colorbar(im,ax=ax,shrink=.7,ticks=[1,2,3,4]);cb.ax.set_yticklabels(['válido','sem MDS','sem terreno/H','excluído QC'])
                ax.set_title('Suporte observado')
            else:
                im=ax.imshow(a,extent=extent,cmap='viridis',vmin=0,vmax=35,interpolation='nearest')
                if name=='chm':fig.colorbar(im,ax=ax,shrink=.7,label='H candidato (m)');ax.set_title('CHM, 1 m, sem preencher lacunas')
                else:
                    window=shapely.box(*bounds);c=crowns.loc[crowns.intersects(window)];t=tops.loc[tops.intersects(window)]
                    if len(c):c.boundary.plot(ax=ax,color='#ffca66',linewidth=.7)
                    if len(t):
                        ax.scatter(t.geometry.x,t.geometry.y,s=11,c='white',marker='+',label='semente CHM')
                        ax.scatter(t.apex_return_x,t.apex_return_y,s=7,c='#ff5252',marker='o',label='maior Z no segmento')
                        ax.legend(fontsize=7,loc='lower right')
                    ax.set_title('Copas e topos estimados, PyCrown')
            units.geometry.boundary.plot(ax=ax,color='#ef67d3',linewidth=.7)
            ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(labelsize=6)
            ax.set_xlabel('E (m), SIRGAS 2000 / UTM 23S');ax.set_ylabel('N (m)')
        fig.suptitle(f'{cid}: janela ilustrativa da primeira unidade por hash — sem referência externa',fontsize=12)
        fig.savefig(out/f'{cid}_estimativas.png',dpi=170);plt.close(fig)
    if preview is not None:return
    sens=pd.read_parquet(root/'sensibilidade_cenarios.parquet');agreements=pd.read_parquet(root/'concordancia_ablacao.parquet')
    primary=agreements.loc[agreements.variant_id.eq('A_plus_3D__I6_I7__Vplus__w0.5')&agreements.scope.eq('conditional_canopy')&agreements.top_fraction.eq(.2)]
    fig,axes=plt.subplots(1,3,figsize=(15,5),constrained_layout=True)
    counts=selection.groupby(['corridor_id','role']).size();counts.plot.bar(ax=axes[0],color='#367da5');axes[0].set_ylabel('Unidades selecionadas, 50 m');axes[0].set_title('Amostra real');axes[0].set_xlabel('corredor / papel')
    order=sens.scenario_id.drop_duplicates().tolist()
    axes[1].boxplot([sens.loc[sens.scenario_id.eq(s),'canopy_union_IoU_common_support'].dropna().to_numpy() for s in order],tick_labels=order,showfliers=True)
    axes[1].tick_params(axis='x',rotation=90,labelsize=7);axes[1].set_ylim(0,1.05);axes[1].set_ylabel('IoU da união de copas no suporte comum');axes[1].set_title('Estabilidade interna entre cenários')
    axes[2].bar(primary.case.str.replace('sample_','',regex=False),primary.spearman_rho,color='#c67c48');axes[2].set_ylim(-1,1);axes[2].set_title('A × A+3D, peso vertical 0,5');axes[2].set_ylabel('Spearman descritivo');axes[2].axhline(0,color='gray',linewidth=.5)
    fig.suptitle('Etapa 12, v0.3.0 — descritores exploratórios; sem inferência municipal ou acurácia externa')
    fig.savefig(out/'amostra_e_estabilidade.png',dpi=170);plt.close(fig)


if __name__=='__main__':main()
