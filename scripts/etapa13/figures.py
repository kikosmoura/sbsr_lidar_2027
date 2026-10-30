"""Figuras científicas em dimensões físicas fixas, com NoData explícito."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/sbsr-lidar-matplotlib13')
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds,bounds as window_bounds
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.font_manager import FontProperties,findfont
from matplotlib.backends.backend_pdf import PdfPages
import textwrap
import warnings
from sbsr_lidar.storage import fingerprint,atomic_write_json,read_json
from .evidence import native,subset

BLUE='#0072B2';ORANGE='#D55E00';GREEN='#009E73';GRAY='#737373';OFFWHITE='#F3F1EA'
LABELS={'kept':'Mantida no top','lost':'Sai do top','gained':'Entra no top','neither':'Fora de ambos'}
SCENARIOS={'resolution_0.5':'Res. 0,5 m','resolution_2':'Res. 2 m','detection_radius_2':'Detecção 2 m',
    'detection_radius_5':'Detecção 5 m','height_2':'H > 2 m','height_5':'H > 5 m',
    'crown_radius_6':'Copa 6 m','crown_radius_12':'Copa 12 m','dalponte_standard':'Dalponte',
    'density_0.5':'Retenção 50%','density_0.25':'Retenção 25%'}


def map_categories(observation,labels):
    if not np.isin(observation,[1,2,3,4,255]).all():raise ValueError('Código de observação desconhecido')
    observed=observation==1;canopy=observed&(labels>0)
    if np.any((labels>0)&~observed):raise ValueError('Copa fora do suporte observado')
    result=np.zeros(observation.shape,dtype='uint8');result[observed]=1
    result[(observation!=1)&(observation!=255)]=2;result[canopy]=3
    return result


def setup(config):
    font=findfont(FontProperties(family=config['font_family']),fallback_to_default=False)
    plt.rcParams.update({'font.family':config['font_family'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,
        'xtick.labelsize':7.5,'ytick.labelsize':7.5,'legend.fontsize':7,'pdf.fonttype':42,'ps.fonttype':42,
        'svg.fonttype':'none','svg.hashsalt':'sbsr_etapa13_v1','axes.linewidth':.6,'xtick.major.width':.6,'ytick.major.width':.6,
        'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
    return fingerprint(Path(font))


def figure(width,height):return plt.figure(figsize=(width/25.4,height/25.4),dpi=150)


def save(fig,path,config,description,inputs,primary=True):
    path.parent.mkdir(parents=True,exist_ok=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');fig.canvas.draw()
    missing=[str(w.message) for w in caught if 'Glyph' in str(w.message) and 'missing' in str(w.message)]
    if missing:raise ValueError(f'Glifo ausente: {missing}')
    renderer=fig.canvas.get_renderer();bounds=fig.bbox;outside=[];sizes=[];boxes=[]
    texts=list(fig.findobj(match=Text))
    for ax in fig.axes:
        for table in ax.tables:
            texts.extend(cell.get_text() for cell in table.get_celld().values())
    texts=list({id(t):t for t in texts}.values())
    for text in texts:
        if not text.get_visible() or not text.get_text().strip():continue
        sizes.append(float(text.get_fontsize()))
        box=text.get_window_extent(renderer)
        boxes.append((text.get_text(),box))
        if box.x0<bounds.x0-1 or box.y0<bounds.y0-1 or box.x1>bounds.x1+1 or box.y1>bounds.y1+1:
            outside.append(text.get_text())
    if outside:raise ValueError(f'Texto fora da figura {path.name}: {outside}')
    overlaps=[]
    for i,(a,x) in enumerate(boxes):
        for b,y in boxes[i+1:]:
            w=min(x.x1,y.x1)-max(x.x0,y.x0);h=min(x.y1,y.y1)-max(x.y0,y.y0)
            if w>1 and h>1 and w*h>4:overlaps.append([a,b])
    if overlaps:raise ValueError(f'Textos sobrepostos em {path.name}: {overlaps}')
    if sizes and min(sizes)<config['minimum_font_pt']:raise ValueError('Fonte menor que o mínimo de apresentação')
    width,height=fig.get_size_inches()*25.4
    for suffix in ['pdf','svg','png']:
        metadata={'Creator':'SBSR etapa13: dados experimentais v0.3.0'}
        if suffix=='pdf':metadata.update(CreationDate=None,ModDate=None)
        if suffix=='svg':metadata.update(Date=None)
        if suffix=='png':metadata={'Software':'Matplotlib: SBSR etapa13 v1.0.0'}
        fig.savefig(path.with_suffix('.'+suffix),dpi=config['png_dpi'],metadata=metadata)
    plt.close(fig)
    return {'figure_id':path.name,'description':description,'primary':primary,'width_mm':float(width),'height_mm':float(height),
        'minimum_font_pt':min(sizes) if sizes else None,'text_outside_canvas':outside,'text_overlaps':overlaps,'missing_glyphs':missing,'inputs':inputs,
        'files':[fingerprint(path.with_suffix('.'+s)) for s in ['pdf','svg','png']]}


def support_plot(evidence,out):
    c=evidence.config;s=evidence.sample.sort_values('corridor_id').reset_index(drop=True)
    fig=figure(c['column_width_mm'],72);ax=fig.add_axes([.28,.27,.68,.64]);y=np.arange(len(s))
    observed=100*s.fraction_observed.to_numpy();missing=np.maximum(0,100-observed)
    ax.barh(y,observed,color=BLUE,height=.70,label='Observado')
    ax.barh(y,missing,left=observed,color='#E2E2E2',edgecolor='#666666',hatch='////',linewidth=.3,height=.70,label='Sem suporte')
    for yy,value in zip(y,observed):ax.text(2,yy,f'{value:.1f}%',va='center',color='white',fontsize=7.5)
    ax.set_yticks(y,[row.corridor_id+('*' if row.role=='development' else '') for row in s.itertuples()]);ax.invert_yaxis()
    ax.set_xlim(0,100);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Área do corredor (%)')
    fig.legend(*ax.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.065),ncol=2,frameon=False,handlelength=1.3,columnspacing=1)
    fig.text(.5,.97,'Suporte do cenário principal',ha='center',va='top',fontsize=9)
    fig.text(.5,.015,'* Desenvolvimento. Fonte: GeoSampa; protocolo v0.3.0.',ha='center',va='bottom',fontsize=7)
    return save(fig,out/'figures/F01_suporte',c,'Área observada nos dez polígonos originais; hachura indica suporte ausente.',
        ['sample_summary','observed_fraction_min','observed_fraction_max'])


def rank_plot(evidence,out):
    c=evidence.config;d=evidence.ranks;n=len(d);k=evidence.metrics['primary_k']['value']
    fig=figure(c['column_width_mm'],88);ax=fig.add_axes([.18,.33,.76,.59])
    styles={'neither':('#888888','.',14),'kept':(GREEN,'o',14),'lost':(ORANGE,'x',20),'gained':(BLUE,'^',19)}
    for status,(color,marker,size) in styles.items():
        g=d.loc[d.disagreement.eq(status)]
        ax.scatter(g.rank_ordinal_A,g.rank_ordinal_3D,c=color,marker=marker,s=size,linewidths=.6,label=f'{LABELS[status]} ({len(g)})',zorder=3)
    ax.plot([1,n],[1,n],color='#555555',linewidth=.6,zorder=1)
    ax.axvline(k+.5,color='#777777',linestyle='--',linewidth=.6);ax.axhline(k+.5,color='#777777',linestyle='--',linewidth=.6)
    ticks=sorted(set([1,*range(25,n,25),n]));ax.set_xticks(ticks);ax.set_yticks(ticks)
    ax.set_xlim(-1,n+2);ax.set_ylim(n+2,-1);ax.set_xlabel('Posição ordinal A');ax.set_ylabel('Posição ordinal A+3D')
    ax.set_aspect('equal',adjustable='box')
    fig.legend(*ax.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.075),ncol=2,frameon=False,columnspacing=.8,handletextpad=.3)
    fig.text(.5,.97,f'Ordenação relativa: avaliação (n={n})',ha='center',va='top',fontsize=9)
    fig.text(.5,.015,'Top20% exato; empates resolvidos por ID. Sem alvo externo.',ha='center',va='bottom',fontsize=7)
    return save(fig,out/'figures/F03_rankings',c,'A versus A+3D no mesmo conjunto de IDs; não representa ganho de acurácia.',
        ['escores_rankings','membros_top','coorte_selecionada','primary_spearman_rho','primary_jaccard_exact'])


def stability_plot(evidence,out):
    c=evidence.config;d=evidence.frames['sensibilidade_rankings_agrupada'];d=d.loc[d.role.eq('evaluation')].set_index('scenario_id').loc[list(SCENARIOS)].reset_index()
    fig=figure(c['column_width_mm'],86);ax=fig.add_axes([.30,.17,.65,.74]);y=np.arange(len(d))
    ax.scatter(d.spearman_rho,y-.12,s=14,c=BLUE,marker='o',label='Spearman')
    ax.scatter(d.jaccard_exact,y+.12,s=14,c=ORANGE,marker='s',label='Jaccard top20%')
    for yy,row in enumerate(d.itertuples()):ax.text(1.025,yy,str(row.paired_eligible_units),va='center',fontsize=7)
    ax.text(1.025,-.95,'n',ha='left',fontsize=7)
    ax.set_yticks(y,[SCENARIOS[s] for s in d.scenario_id]);ax.invert_yaxis();ax.set_xlim(0,1.12);ax.set_xticks([0,.25,.5,.75,1.])
    ax.set_xlabel('Concordância no suporte comum');ax.grid(axis='x',color='#DDDDDD',linewidth=.4)
    ax.legend(loc='upper center',bbox_to_anchor=(.34,1.14),ncol=2,frameon=False,handletextpad=.3,columnspacing=.8)
    fig.text(.5,.015,'n varia por par; não são IC nem acurácia externa.',ha='center',va='bottom',fontsize=7)
    return save(fig,out/'figures/F04_sensibilidade',c,'Estabilidade pareada e tamanho da coorte remanescente; onze cenários alternativos.',
        ['sensibilidade_rankings_agrupada','sensitivity_paired_eligible_units_min','sensitivity_paired_eligible_units_max'])


def read_map(evidence,example):
    cid=example['corridor_id'];root=Path(evidence.execution['case_results'][cid]['root']);case_manifest=read_json(root/'complete.json')
    inventory={p['path']:p for p in case_manifest['outputs']}
    units=evidence.frames['coorte_selecionada'];unit=units.loc[units.unit_id.eq(example['unit_id'])].iloc[0]
    p=unit.geometry.representative_point();side=evidence.config['example_window_m'];half=side/2
    left,bottom=np.floor(p.x-half),np.floor(p.y-half);box=(left,bottom,left+side,bottom+side)
    data={};sources=[]
    for name,path in [('chm',root/'rasters_r1_f1/chm.tif'),('observation',root/'rasters_r1_f1/observation.tif'),('labels',root/'primary/labels.tif')]:
        found=fingerprint(path)
        if inventory.get(found['path'])!=found:raise ValueError(f'Raster da etapa12 mudou: {path}')
        sources.append(found)
        with rasterio.open(path) as ds:
            if ds.crs.to_epsg()!=31983 or ds.res!=(1.,1.):raise ValueError('CRS/resolução de exemplo incompatível')
            window=from_bounds(*box,transform=ds.transform).round_offsets().round_lengths()
            data[name]=ds.read(1,window=window,boundless=True,fill_value=255 if name=='observation' else -1)
    domain=evidence.frames['selecao_corredores_congelada'].set_index('corridor_id').loc[cid].geometry
    return {'arrays':data,'unit':unit.geometry,'measurement':domain,'bounds':box,'sources':sources,'example':example}


def draw_map(evidence,out,prepared,stem,maximum,primary):
    c=evidence.config;d=prepared['arrays'];obs=d['observation'];labels=d['labels'];side=c['example_window_m'];x0,y0,_,_=prepared['bounds']
    observed=obs==1;canopy=observed&(labels>0);outside=obs==255;unknown=~observed&~outside
    categories=map_categories(obs,labels)
    fig=figure(c['double_column_width_mm'],86);axes=[]
    for i,x in enumerate([.08,.56]):
        ax=fig.add_axes([x,.28,.32,.66]);axes.append(ax)
        ax.imshow(categories,origin='upper',extent=[0,side,0,side],cmap=ListedColormap(['#E4E4E4',OFFWHITE,GRAY,GREEN]),vmin=0,vmax=3,interpolation='nearest')
        if i==1:
            height=np.ma.masked_where(~canopy,d['chm']);im=ax.imshow(height,origin='upper',extent=[0,side,0,side],cmap='viridis',vmin=0,vmax=maximum,interpolation='nearest')
        for mask,hatch in [(outside,'////'),(unknown,'....')]:
            if mask.any():
                yy,xx=np.indices(mask.shape);ax.contourf(xx+.5,side-yy-.5,mask.astype(float),levels=[.5,1.5],colors='none',hatches=[hatch],antialiased=True)
        for geometry,color,style,lw in [(prepared['measurement'],'#111111','--',.65),(prepared['unit'],BLUE,'-',1.1)]:
            shifted=gpd.GeoSeries([geometry],crs=31983).translate(xoff=-x0,yoff=-y0)
            shifted.boundary.plot(ax=ax,color=color,linestyle=style,linewidth=lw)
        ax.plot([7,27],[7,7],color='black',linewidth=1.3);ax.text(17,10,'20 m',ha='center',fontsize=7)
        ax.annotate('N',xy=(side-12,side-15),xytext=(side-12,side-37),ha='center',va='center',fontsize=7,arrowprops={'arrowstyle':'->','lw':.7})
        ax.set_xlim(0,side);ax.set_ylim(0,side);ax.set_aspect('equal');ax.set_xticks([0,50,100]);ax.set_yticks([0,50,100])
        ax.set_xlabel('ΔE (m)',labelpad=1);ax.set_ylabel('ΔN (m)',labelpad=1)
        ax.set_title('a) Copa detectada (2D)' if i==0 else 'b) Hmáx dentro da copa',pad=3)
    colorbar=fig.add_axes([.91,.28,.014,.66]);cb=fig.colorbar(im,cax=colorbar);cb.set_label('H (m)',labelpad=1);cb.ax.tick_params(labelsize=7)
    handles=[Patch(facecolor=GREEN,label='Copa estimada'),Patch(facecolor=OFFWHITE,edgecolor='#777777',label='Observado sem copa detectada'),
        Patch(facecolor=GRAY,hatch='....',label='NoData no contexto'),Patch(facecolor='#E4E4E4',hatch='////',label='Não processado')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.10),ncol=4,frameon=False,handlelength=1.1,columnspacing=.8,fontsize=7)
    fig.text(.5,.016,f'GeoSampa 2020; EPSG:31983. Origem: E={x0:.0f} m, N={y0:.0f} m. Tracejado: P; azul: unidade.',ha='center',va='bottom',fontsize=7)
    record=save(fig,out/f'figures/{stem}',c,'Mesmo recorte, suporte e máscara em 2D/H; norte da grade UTM; exemplo ilustrativo.',
        ['coorte_selecionada','selecao_corredores_congelada'],primary=primary)
    record.update(example_id=prepared['example']['unit_id'],status=prepared['example']['disagreement'],bounds_utm=prepared['bounds'],epsg=31983,
        raster_inputs=prepared['sources'],height_scale_m=[0,maximum],category_counts={str(i):int((categories==i).sum()) for i in range(4)},
        height_cells_clipped_above_maximum=int((canopy&(d['chm']>maximum)).sum()))
    datafile=out/'maps'/f'{stem}.npz';datafile.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(datafile,observation=obs,labels=labels,chm=d['chm'],categories=categories,bounds=np.asarray(prepared['bounds']))
    record['window_data']=fingerprint(datafile)
    return record


def all_figures(evidence,out):
    setup(evidence.config);prepared=[read_map(evidence,evidence.main_example)]
    prepared += [read_map(evidence,e) for e in evidence.examples]
    maxima=[float(np.max(d['arrays']['chm'][(d['arrays']['labels']>0)&(d['arrays']['observation']==1)])) for d in prepared]
    maximum=max(5.,float(np.ceil(max(maxima)/5)*5))
    records=[support_plot(evidence,out),draw_map(evidence,out,prepared[0],'F02_exemplo_2D_H',maximum,True),rank_plot(evidence,out),stability_plot(evidence,out)]
    for d in prepared[1:]:
        records.append(draw_map(evidence,out,d,'S_'+d['example']['disagreement']+'_2D_H',maximum,False))
    return records
