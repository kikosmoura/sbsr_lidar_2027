"""Tabelas compactas, legendas e provas no tamanho final do modelo fornecido."""
import textwrap
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from sbsr_lidar.storage import fingerprint,atomic_write_json
from .evidence import subset
from .figures import figure,save


def compact_tables(evidence,out):
    t=evidence.sample.sort_values('corridor_id');role={'evaluation':'Aval.','development':'Des.'}
    sample=pd.DataFrame({'Corredor':t.corridor_id,'Uso':t.role.map(role),'P (ha)':t.area_total_m2.map(lambda x:f'{x/10000:.2f}'),
        'Obs. (%)':t.fraction_observed.map(lambda x:f'{x*100:.1f}'),'Eleg./sel.':t.eligible_50m.astype(str)+'/'+t.selected_50m.astype(str)})
    indicators=pd.DataFrame([
        ['I1','T/O','Área de copa detectada / área observada','1'],
        ['I4','10000 Nmanchas/O','Densidade de manchas conectadas; não árvores','1/ha'],
        ['I5 (aux.)','média(H)','Média das alturas dos retornos vegetais selecionados','m'],
        ['I6','P95(H)','Percentil 95 das alturas dos retornos selecionados','m'],
        ['I7','P75(H)−P25(H)','Amplitude interquartil das alturas dos retornos','m'],
        ['E1 (aux.)','10000 Nsementes/O','Sementes CHM estimadas; fora do escore A/A+3D','1/ha']
    ],columns=['Indicador','Definição','Estimando / interpretação','Unidade'])
    f={k:v for k,v in evidence.main_filters.items() if k!='case'}
    scores=subset(evidence.frames['concordancia_ablacao'],f).sort_values('case')
    comparison=pd.DataFrame({'Coorte':scores['case'].map({'sample_evaluation':'Avaliação','sample_development':'Desenvolv.'}),
        'n':scores.n,'k':scores.k,'ρ':scores.spearman_rho.map(lambda x:f'{x:.4f}'),
        'J top20%':scores.jaccard_exact.map(lambda x:f'{x:.4f}'),'Interseção':scores.top_intersection_n})
    frames={'T01_amostra':sample,'T02_indicadores':indicators,'T03_comparacao':comparison};records=[]
    tables=out/'tables'
    for name,frame in frames.items():
        frame.to_csv(tables/f'{name}.csv',index=False)
        (tables/f'{name}.md').write_text(markdown_table(frame))
        (tables/f'{name}.tex').write_text(latex_table(frame))
        w=178 if name=='T02_indicadores' else 86;h={'T01_amostra':57,'T02_indicadores':40,'T03_comparacao':24}[name]
        fig=figure(w,h);ax=fig.add_axes([.015,.03,.97,.94]);ax.axis('off')
        widths={'T01_amostra':[.25,.13,.18,.20,.24],'T02_indicadores':[.09,.19,.63,.09],
            'T03_comparacao':[.25,.10,.10,.17,.20,.18]}[name]
        table=ax.table(cellText=frame.values,colLabels=frame.columns,colWidths=widths,cellLoc='center',loc='center')
        table.auto_set_font_size(False);table.set_fontsize(8)
        table.scale(1,1.15)
        for (r,c),cell in table.get_celld().items():
            cell.set_linewidth(.35);cell.set_edgecolor('#888888')
            if r==0:cell.set_facecolor('#E9ECEF');cell.get_text().set_fontweight('bold')
        records.append(save(fig,out/'tables'/name,evidence.config,'Tabela compacta gerada das fontes e fórmulas declaradas.',
            ['sample_summary' if name=='T01_amostra' else 'concordancia_ablacao' if name=='T03_comparacao' else 'docs/protocolo_pycrown_v0_3_0.md']))
    return records


def markdown_table(frame):
    rows=['| '+' | '.join(frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    rows +=['| '+' | '.join(map(str,row))+' |' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(rows)+'\n'


def latex_table(frame):
    chars={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_',
        '{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}','ρ':r'$\rho$','⁻':r'$^{-}$','¹':r'$^{1}$','−':'-'}
    def escaped(value):return ''.join(chars.get(char,char) for char in str(value))
    rows=[r'\begin{tabular}{'+('l'*len(frame.columns))+'}',r'\hline',
        ' & '.join(escaped(v) for v in frame.columns)+r' \\',r'\hline']
    rows +=[' & '.join(escaped(v) for v in row)+r' \\' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(rows+[r'\hline',r'\end{tabular}'])+'\n'


def captions(evidence):
    m=lambda key:evidence.metrics[key]['value']
    examples={e['status']:e for e in evidence.examples};unit=evidence.main_example['unit_id']
    result={
        'F01_suporte':f"Figura1. Fração observada nos {len(evidence.sample)} corredores, de {100*m('observed_fraction_min'):.1f}% a {100*m('observed_fraction_max'):.1f}%. A hachura indica suporte ausente, não ausência de árvores. Asterisco identifica desenvolvimento. LiDAR2020, perímetros2026; cenário principal v0.3.0.",
        'F02_exemplo_2D_H':f"Figura2. Máscara 2D de copa estimada e máximo H por pixel sob a mesma máscara e suporte. Unidade {unit}, escolhida pelo primeiro hash na coorte de avaliação; exemplo ilustrativo pós-resultados. Coordenadas locais da grade UTM23S, SIRGAS2000, EPSG:31983; origem indicada no gráfico. Fora do contexto = não processado; NoData = contexto sem suporte. Classes3/4/5 e PyCrown, 1m; não são contornos validados.",
        'F03_rankings':f"Figura3. A versus A+3D na avaliação (n={m('units_evaluation')}, peso vertical0,5). As posições ordinais mostram o desempate por ID; ρ={m('primary_spearman_rho'):.4f} foi calculado com ranks médios. Top20%: k={m('primary_k')}, interseção={m('primary_top_intersection_n')}, J={m('primary_jaccard_exact'):.4f}. Mudança de ordenação relativa não demonstra melhora de diagnóstico.",
        'F04_sensibilidade':f"Figura4. Concordância do A+3D principal com cada alternativa no suporte vetorial comum e mesmos IDs elegíveis de cada par. n varia de {m('sensitivity_paired_eligible_units_min')} a {m('sensitivity_paired_eligible_units_max')} entre as {m('units_evaluation')} unidades primárias. As linhas não representam o mesmo subconjunto; não há garantia simultânea para a coorte inteira, IC ou teste de significância.",
        'T01_amostra':f"Tabela1. Suporte em P original e unidades de50m elegíveis/selecionadas. Avaliação n={m('units_evaluation')}, desenvolvimento n={m('units_development')}; déficit de{m('evaluation_shortfall')} frente à meta de{m('target_evaluation')}. Unidades não elegíveis não foram repostas. P em hectares; observação não é qualidade semântica da máscara.",
        'T02_indicadores':"Tabela2. Indicadores físicos e estimandos. O=área observada(m²); T=área da união de copas estimadas(m²); H=Zabsoluto−TIN5(X,Y), em metros. I4 conta manchas, E1 conta sementes estimadas; nenhum é inventário de árvores. I6/I7 usam quantis exatos lineares de retornos, não médias de árvores. I2/I3 e B/C indisponíveis nesta amostra.",
        'T03_comparacao':"Tabela3. A versus A+3D, peso0,5, escopo condicional à copa elegível, grid50m. n=mesmos IDs em ambos; k=ceil(0,2n), desempate exato por ID. ρ usa ranks médios; J usa listas exatas. Valores são descritivos; sem IC, p ou alvo independente."}
    for status,e in examples.items():
        result['S_'+status+'_2D_H']=f"Exemplo suplementar: {status} ({e['group_n']} unidades na categoria). Unidade {e['unit_id']}, primeiro hash dentro da categoria. Regra idêntica para acordo e desacordo; exemplo pós-resultados, sem rótulo independente. Mesma escala de altura, suporte e extensão das demais janelas."
    return result


def wrap_caption(text,width_mm,font=9):
    prop=FontProperties(family='Times New Roman',size=font,weight='bold');limit=width_mm*72/25.4;lines=[];current=''
    for word in text.split():
        trial=(current+' '+word).strip()
        # Split long IDs as text, without modifying their machine-readable form.
        if TextPath((0,0),trial,prop=prop).get_extents().width>limit and current:
            lines.append(current);current=word
        else:current=trial
    if current:lines.append(current)
    return '\n'.join(lines)


def proofs(records,captions,out):
    target=out/'provas_tamanho_final.pdf'
    with PdfPages(target,metadata={'Title':'Provas gráficas etapa13; não é manuscrito','CreationDate':None,'ModDate':None}) as pdf:
        for record in records:
            if not record['primary']:continue
            fig=figure(210,297);w,h=record['width_mm'],record['height_mm'];left,top=19,25
            ax=fig.add_axes([left/210,1-(top+h)/297,w/210,h/297]);ax.imshow(plt.imread(out/('figures' if record['figure_id'].startswith('F') else 'tables')/(record['figure_id']+'.png')));ax.axis('off');ax.set_aspect('auto')
            caption=wrap_caption(captions[record['figure_id']],w)
            fig.text((left+w/2)/210,1-(top+h+3)/297,caption,ha='center',va='top',fontsize=9,fontweight='bold',linespacing=1.08)
            fig.text(19/210,1-12/297,'Prova em tamanho final — não é o manuscrito para submissão',fontsize=9,va='top')
            pdf.savefig(fig,dpi=600);plt.close(fig)
    return fingerprint(target)
