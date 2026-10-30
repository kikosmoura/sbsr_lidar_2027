"""Figuras, relatório e cópia editorial com resultados complementares rastreáveis."""
from pathlib import Path
import json
import os
import re
import shutil
import sys

os.environ.setdefault('MPLCONFIGDIR', '/tmp/sbsr_complemento17_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sbsr_lidar.storage import read_json, atomic_write_json, fingerprint

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etapa14.audit import json_pointer, abstract_counts, verify_registry, claims_matrix, bibliography_checks
from etapa14.build import display
from etapa15.editorial import compile_at


def save_figure(fig, directory, name):
    for extension in ['pdf', 'svg', 'png']:
        fig.savefig(directory/f'{name}.{extension}', dpi=600)
    plt.close(fig)


def figures(out):
    directory = out/'figuras'; directory.mkdir(exist_ok=True)
    summary = read_json(out/'resultados.json')
    plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 7.5,
                         'axes.labelsize': 7.5, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    pairs = pd.read_csv(out/'complementaridade_disjoint.csv').sort_values(['corridor_i', 'unit_i', 'unit_j'])
    fig, axes = plt.subplots(1, 2, figsize=(86/25.4, 93/25.4), sharey=True)
    fig.subplots_adjust(left=.23, right=.98, top=.85, bottom=.13, wspace=.25)
    y = np.arange(len(pairs)); labels = []
    counts = {}
    for cid in pairs.corridor_i:
        counts[cid] = counts.get(cid, 0)+1; labels.append(f'{cid.removeprefix("CO_")} /{counts[cid]}')
    for ax, prefix, title in zip(axes, ['P95', 'IQR'], ['P95(H) (m)', 'IQR(H) (m)']):
        x, z = pairs[f'{prefix}_i_m'].to_numpy(), pairs[f'{prefix}_j_m'].to_numpy()
        ax.hlines(y, np.minimum(x, z), np.maximum(x, z), color='#929292', linewidth=.8)
        ax.scatter(x, y, s=12, color='#17638f', label='Unidade i', zorder=3)
        ax.scatter(z, y, s=12, color='#bc591c', marker='s', label='Unidade j', zorder=3)
        ax.set_xlabel(title); ax.grid(axis='x', color='#dddddd', linewidth=.4); ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False); ax.set_xlim(left=0)
    axes[0].set_yticks(y, labels); axes[0].invert_yaxis()
    fig.suptitle(f'Pares semelhantes em I1/I4 no mesmo corredor\n{len(pairs)} pares sem reutilização de IDs', fontsize=7.5, y=.98)
    handles, lab = axes[0].get_legend_handles_labels(); fig.legend(handles, lab, loc='upper center', bbox_to_anchor=(.62, .91), ncol=2, fontsize=7, frameon=False, handletextpad=.2, columnspacing=.6)
    save_figure(fig, directory, 'F05_pares_horizontais')
    data = pd.read_csv(out/'estabilidade_comparisons.csv'); loss = pd.read_csv(out/'perdas_elegibilidade.csv')
    scenario_ids = list(loss.scenario_id)
    variable = data.query("cohort == 'variable_pairwise'").set_index('scenario_id').loc[scenario_ids]
    fixed = data.query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'method_on_pair_support'").set_index('scenario_id').loc[scenario_ids]
    labels = ['Res. 0,5 m', 'Res. 2 m', 'Det. 2 m', 'Det. 5 m', 'H > 2 m', 'H > 5 m', 'Copa 6 m', 'Copa 12 m', 'Dalponte', 'MDS 50%', 'MDS 25%']
    fig, ax = plt.subplots(figsize=(86/25.4, 87/25.4)); fig.subplots_adjust(left=.25, right=.88, top=.80, bottom=.15)
    for col, color, offset, label in [('spearman_rho', '#17638f', -.11, 'Spearman'), ('jaccard_exact', '#bc591c', .11, 'Jaccard')]:
        yy = np.arange(len(fixed))+offset
        ax.scatter(variable[col], yy, facecolors='none', edgecolors=color, s=28, linewidths=.8)
        ax.scatter(fixed[col], yy, color=color, s=13, label=label)
    for y, n in enumerate(variable.n): ax.text(1.03, y, str(n), fontsize=7, va='center')
    ax.set_yticks(range(len(labels)), labels); ax.invert_yaxis(); ax.set_xlim(.45, 1.02)
    ax.set_xticks([.5, .75, 1.], ['0,50', '0,75', '1,00']); ax.set_xlabel('Concordância com o principal')
    ax.grid(axis='x', color='#dddddd', linewidth=.4); ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.01), ncol=2, fontsize=7, frameon=False, handletextpad=.2, columnspacing=.5)
    fig.suptitle(f'A+3D: coorte fixa versus coortes de cada par\n● fixa ({summary["strict_fixed_units"]} IDs); ○ variável (n à direita)', fontsize=7.5, y=.98)
    save_figure(fig, directory, 'F06_estabilidade_coorte_fixa')


def metrics_for_article(project, out, article):
    registry = read_json(article/'dados/numeros_rastreaveis.json'); summary = read_json(out/'resultados.json')
    additions = {
        'comp_pairs': ('/matching/horizontal_within_corridor/n_pairs', 0),
        'comp_units': ('/matching/horizontal_within_corridor/n_unique_units', 0),
        'comp_p95': ('/matching/horizontal_within_corridor/P95_difference_median_m', 2),
        'comp_iqr': ('/matching/horizontal_within_corridor/IQR_difference_median_m', 2),
        'comp_ge5': ('/matching/horizontal_within_corridor/P95_difference_ge_5m_n', 0),
        'comp_disjoint': ('/matching/disjoint_within_corridor/n_pairs', 0),
        'comp_disjoint_p95': ('/matching/disjoint_within_corridor/P95_difference_median_m', 2),
        'comp_fixed': ('/strict_fixed_units', 0),
        'comp_rhomin': ('/fixed_A_plus_3D_method_ranges/spearman_rho/min', 3),
        'comp_rhomax': ('/fixed_A_plus_3D_method_ranges/spearman_rho/max', 3),
        'comp_jmin': ('/fixed_A_plus_3D_method_ranges/jaccard_exact/min', 3),
        'comp_jmax': ('/fixed_A_plus_3D_method_ranges/jaccard_exact/max', 3),
        'comp_k': ('/fixed_primary_A_vs_A_plus_3D/k', 0)}
    additions.update({
        'comp_support_rhomin': ('/fixed_A_plus_3D_support_ranges/spearman_rho/min', 4),
        'comp_worst_excluded': ('/lowest_retention/excluded_units', 0),
        'comp_worst_observation': ('/lowest_retention/excluded_with_insufficient_observed_fraction', 0),
        'comp_worst_other': ('/lowest_retention/excluded_other_eligibility_only', 0)})
    fp = fingerprint(out/'resultados.json')
    for key, (pointer, decimals) in additions.items():
        registry['metrics'][key] = {'value': json_pointer(summary, pointer), 'decimals': decimals, 'scale': 1,
            'source': fp, 'json_pointer': pointer, 'classification': 'exploratoria_pos_resultados',
            'analysis_version': summary['analysis_version']}
    scientific_config = project/'configs/complemento_analitico_etapa17.yaml'
    registry['parameters']['comp_fragmentation_caliper'] = {'value': .1, 'literal': True, 'source': fingerprint(scientific_config), 'pointer': '/horizontal_matching/primary_fragmentation_rank_caliper'}
    commands = (article/'numeros.tex').read_text()
    for key in additions:
        record = registry['metrics'][key]
        for prefix, english in [('ev', False), ('en', True)]:
            commands += '\n'+r'\expandafter\def\csname '+prefix+'@'+key+r'\endcsname{'+display(record['value'], record['decimals'], english, 1)+'}'
    commands += '\n'+r'\expandafter\def\csname par@comp_fragmentation_caliper\endcsname{0{,}10}'+'\n'
    (article/'numeros.tex').write_text(commands)
    atomic_write_json(article/'dados/numeros_rastreaveis.json', registry)
    shutil.copyfile(out/'resultados.json', article/'dados/complemento_resultados.json')
    return registry


def replace_paragraph(text, prefix, replacement):
    blocks = text.split('\n\n'); pattern = re.compile('^'+re.escape(prefix), re.M)
    indices = [i for i, p in enumerate(blocks) if pattern.search(p)]
    if len(indices) != 1: raise ValueError(f'Parágrafo não encontrado univocamente: {prefix}')
    i = indices[0]; match = pattern.search(blocks[i])
    blocks[i] = blocks[i][:match.start()]+replacement
    return '\n\n'.join(blocks)


def article(project, out):
    src = project/'artigo/revisao_etapa15'; dest = project/'artigo/complemento_etapa17'
    if dest.exists(): raise ValueError('Cópia editorial já existe; não sobrescrever revisão humana')
    # Verificar o pacote anterior antes de criar nova cópia.
    manifest = read_json(project/'docs/manifesto_etapa15.json')
    for record in manifest['artifacts']:
        path = Path(record['path'])
        if path.is_relative_to(src):
            if fingerprint(path) != record: raise ValueError(f'Artigo anterior alterado: {path}')
            target = dest/path.relative_to(src); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
    registry = metrics_for_article(project, out, dest)
    text = (dest/'manuscrito.tex').read_text()
    text = text.replace('Rascunho exploratório; protocolo 0.3.0', 'Rascunho exploratório; complemento analítico pós-resultados 0.3.1')
    text = text.replace(' A média $I_5$ e a densidade de sementes foram auxiliares.', '')
    text = replace_paragraph(text, r'\section*{Resumo}', r'''\section*{Resumo}
% EVIDENCIA: C14_R | exploratoria | C13_01,C13_03,C17_01,C17_02
\noindent Este estudo exploratório investiga informação vertical entre unidades semelhantes em indicadores horizontais e estabilidade de ordenações em corredores verdes urbanos. Analisaram-se \Ev{corridors_total} perímetros de São Paulo disponíveis em \Par{geometry_year}, com LiDAR GeoSampa de \Par{lidar_year} e rotinas PyCrown, reunindo \Ev{units_evaluation} unidades de avaliação. Um complemento pós-resultados identificou \Ev{comp_pairs} pares do mesmo corredor semelhantes em cobertura e fragmentação, com diferença mediana de P95 de \Ev{comp_p95}~m; \Ev{comp_disjoint} pares sem reutilização de IDs tiveram mediana de \Ev{comp_disjoint_p95}~m. Na coorte fixa de \Ev{comp_fixed} IDs elegíveis em todos os cenários, Spearman variou de \Ev{comp_rhomin} a \Ev{comp_rhomax}, e Jaccard de \Ev{comp_jmin} a \Ev{comp_jmax}. A informação vertical distingue descritivamente unidades próximas em 2D antes de aplicar pesos. A estabilidade dos sobreviventes coexiste com perda de elegibilidade. Sem referência independente, não se demonstram acurácia de copas ou melhora de diagnóstico.''')
    text = replace_paragraph(text, r'\section*{\textit{Abstract}}', r'''\section*{\textit{Abstract}}
\begin{otherlanguage}{english}\itshape
% EVIDENCIA: C14_A | exploratoria | C13_01,C13_03,C17_01,C17_02
\noindent This exploratory study investigates vertical information among units with similar horizontal indicators and ranking stability in urban green corridors. We analysed \En{corridors_total} São Paulo perimeters available in \Par{geometry_year}, using \Par{lidar_year} GeoSampa LiDAR and PyCrown routines, comprising \En{units_evaluation} evaluation units. A post-result extension identified \En{comp_pairs} within-corridor pairs similar in cover and fragmentation, with a median P95 difference of \En{comp_p95}~m; \En{comp_disjoint} pairs without reused IDs had a median of \En{comp_disjoint_p95}~m. In the fixed cohort of \En{comp_fixed} IDs eligible across all scenarios, Spearman ranged from \En{comp_rhomin} to \En{comp_rhomax} and Jaccard from \En{comp_jmin} to \En{comp_jmax}. Vertical information descriptively distinguishes horizontally similar units before ranking weights are applied. Survivor stability coexists with eligibility loss. Without independent reference data, crown accuracy and improved diagnosis were not demonstrated.''')
    text = replace_paragraph(text, 'Métodos de delineamento', 'Métodos de delineamento identificam máximos e expandem regiões em modelos de altura~\\cite{dalponte2016,zorner2018}. Seus segmentos estimados não equivalem a árvores confirmadas; concordância entre produtos da mesma nuvem não valida sua interpretação semântica.')
    text = replace_paragraph(text, 'Este trabalho pergunta', r'''Investigam-se H1, variação vertical entre unidades semelhantes em cobertura e fragmentação, antes de calcular escores; e H2, estabilidade de ordenações separada da perda de elegibilidade. A contribuição descritiva não será inferida somente da mudança esperada ao adicionar variáveis. O recorte é retrospectivo: LiDAR de \Par{lidar_year} nos perímetros disponíveis em \Par{geometry_year}, sem causalidade sobre implantação.''')
    text = replace_paragraph(text, 'Os escores foram arredondados', r'''Os escores usam 12 casas nos empates; Spearman usa postos médios e Jaccard listas superiores de \Par{top_percent}\%, $k=\lceil\Par{top_fraction}n\rceil$, com desempate por ID. Controles incluem pesos 0/0,25/0,5/0,75, sinal oposto de $I_7$, $I_6$ isolado/duplicado. Para H1, o pareamento original exigia diferença de $I_1\leq\Par{cover_tolerance}$ e razão de áreas observadas $\leq\Par{area_ratio}$. Um complemento exploratório pós-resultados acrescentou $|\Delta R(I_4)|\leq\Par{comp_fragmentation_caliper}$, R calculado nos \Ev{units_evaluation} IDs, e restringiu os pares ao mesmo corredor. São limites de semelhança operacional, não equivalência estatística. Avaliaram-se as nove combinações de limites I1=0,025/0,05/0,10 e R(I4)=0,05/0,10/0,20. Uma seleção gulosa sem reutilização de IDs ordenou distâncias horizontais e IDs, sem consultar alturas. Pares e vizinhos espaciais não são réplicas independentes.''')
    text = replace_paragraph(text, 'Os \\Par{scenario_count} cenários', r'''Os \Par{scenario_count} cenários variaram resolução, limiar de altura, raios, algoritmo e retenção MDS de 50/25\%, uma variável por vez e uma semente; o MDT não foi rarefeito. Em 2~m, o raio nominal de detecção 3~m corresponde a 4~m. Cada par principal/cenário foi recalculado na interseção vetorial observada. O complemento fixou a interseção dos IDs elegíveis em ambos os lados de todos os 11 pares e renormalizou cada receita nesses mesmos IDs. Separaram-se três contrastes: principal/cenário no suporte do par; principal nativo/principal no suporte do par; principal nativo/cenário nesse suporte. Não se somam rho/Jaccard desses contrastes. IDs fixos não implicam geometria observada global fixa. Sem independência estabelecida, não se calcularam IC ou $p$~\cite{hurlbert1984}.''')
    text = replace_paragraph(text, '% EVIDENCIA: C14_R2', r'''% EVIDENCIA: C14_R2 | exploratoria | C13_04,C17_01
Os \Ev{similar_cover_pairs} pares originais tinham diferença mediana de P95 de \Ev{pairs_absolute_P95_difference_m_median}~m. Ao controlar também fragmentação e corredor, restaram \Ev{comp_pairs} pares, \Ev{comp_units} unidades, nos oito corredores: mediana de \Ev{comp_p95}~m para P95 e \Ev{comp_iqr}~m para IQR; \Ev{comp_ge5} pares diferiram pelo menos 5~m em P95. A checagem sem reutilização reteve \Ev{comp_disjoint} pares, mediana P95 de \Ev{comp_disjoint_p95}~m (Figura~\ref{fig:pares}). O controle reduz a magnitude, mas preserva variação vertical observada antes de atribuir pesos. Isso sustenta complementaridade descritiva nesses limites, sem provar ganho ecológico ou diferenças superiores ao erro de medição. A Figura~\ref{fig:mapa} ilustra o suporte, sem validar a máscara.''')
    # Trocar o gráfico de mudança mecânica de postos pela comparação vertical direta.
    text = re.sub(r'\\begin\{figure\}\[t\]\s*\\centering\\includegraphics\[width=86mm\]\{figuras/F03_rankings.pdf\}.*?\\end\{figure\}', r'''\begin{figure}[t]
\centering\includegraphics[width=86mm]{figuras/F05_pares_horizontais.pdf}
\caption{P95/IQR dos retornos nos \Ev{comp_disjoint} pares sem reutilizar IDs, selecionados somente por semelhança horizontal. Linhas unem unidades do mesmo corredor; números distinguem pares. Não são alturas por árvore nem pares independentes.}
\label{fig:pares}
\end{figure}'''.replace('\\', '\\\\'), text, flags=re.S)
    text = text.replace(r' (Figura~\ref{fig:rank})', '')
    text = replace_paragraph(text, '% EVIDENCIA: C14_R5', r'''% EVIDENCIA: C14_R5 | parcialmente_sustentada | C13_05,C17_02
As comparações originais tinham \Ev{sensitivity_paired_eligible_units_min}--\Ev{sensitivity_paired_eligible_units_max} IDs por par, $\rho$=\Ev{sensitivity_spearman_rho_min}--\Ev{sensitivity_spearman_rho_max}. A coorte fixa reteve \Ev{comp_fixed}/\Ev{units_evaluation} IDs dos oito corredores. Nela, o contraste principal/cenário no suporte comum teve $\rho$=\Ev{comp_rhomin}--\Ev{comp_rhomax} e $J$=\Ev{comp_jmin}--\Ev{comp_jmax}, com $k=\Ev{comp_k}$ (Figura~\ref{fig:sens}). No contraste de suporte, $\rho\geq\Ev{comp_support_rhomin}$ e as listas superiores coincidiram; o efeito foi pequeno entre sobreviventes, sem garantir estabilidade dos excluídos. Na retenção MDS 25\%, perderam-se \Ev{comp_worst_excluded} IDs: \Ev{comp_worst_observation} por fração observada insuficiente e \Ev{comp_worst_other} por outros critérios. Elegibilidade e observabilidade não são sinônimos. A análise fixa mostra concordância global elevada, mas composição do grupo superior ainda sensível, sem atribuir toda discordância à perda de unidades.''')
    text = text.replace('figuras/F04_sensibilidade.pdf', 'figuras/F06_estabilidade_coorte_fixa.pdf')
    text = text.replace('Concordância com o A+3D principal no suporte comum de cada par; $n$ é o número remanescente de IDs. Os cenários não compartilham necessariamente a mesma subcoorte. Não se representam IC ou acurácia externa.', 'Contraste principal/cenário no suporte de cada par: coorte fixa de \Ev{comp_fixed} IDs e subcoortes variáveis. Os n à direita pertencem às subcoortes variáveis. Spearman elevado não assegura coincidência das listas superiores; sem IC ou acurácia externa.')
    text = replace_paragraph(text, '% EVIDENCIA: C14_C', r'''% EVIDENCIA: C14_C | exploratoria | C13_03,C17_01,C17_02,C13_06
Nos \Ev{corridors_evaluation} corredores de avaliação, unidades próximas em cobertura e fragmentação apresentaram diferenças verticais antes da aplicação de pesos. A redução da diferença após controlar corredor e fragmentação delimita essa complementaridade. Nos \Ev{comp_fixed} IDs sempre elegíveis, a concordância global elevada coexistiu com mudanças nas listas superiores. A contribuição do LiDAR é descrever contrastes estruturais omitidos por esses dois descritores horizontais; sua utilidade para diagnóstico ou intervenção exige alvo independente. A máscara não validada, o caráter pós-resultados e a perda de elegibilidade limitam a conclusão.''')
    (dest/'manuscrito.tex').write_text(text)
    for name in ['F05_pares_horizontais', 'F06_estabilidade_coorte_fixa']:
        shutil.copyfile(out/f'figuras/{name}.pdf', dest/f'figuras/{name}.pdf')
    for name in ['matriz_afirmacoes_evidencias.json', 'verificacao_editorial.json', 'manuscrito.pdf', 'manuscrito_texto_extraido.txt']:
        (dest/name).unlink(missing_ok=True)
    claims = read_json(dest/'dados/resultados_publicaveis.json')['claims']+[
        {'claim_id': 'C17_01', 'limitations': ['extensao_pos_resultados', 'semelhanca_operacional_nao_equivalencia', 'sem_validacao_externa', 'dependencia_espacial']},
        {'claim_id': 'C17_02', 'limitations': ['estabilidade_condicional_aos_68_sobreviventes', 'geometria_comum_por_par_nao_global', 'sem_IC_ou_p', 'perdas_nao_imputadas']}]
    atomic_write_json(dest/'matriz_afirmacoes_evidencias.json', {'stage': '17', 'claims': claims_matrix(text, registry, claims),
        'new_results': fingerprint(out/'resultados.json'), 'source_article': fingerprint(src/'manuscrito.tex')})
    checks = {'registry': verify_registry(registry), 'abstracts': abstract_counts(text, registry),
              'bibliography': bibliography_checks(text, (dest/'referencias.bib').read_text())}
    atomic_write_json(out/'checagens_fonte_artigo.json', checks)
    (dest/'README.md').write_text('''# Revisão com complemento analítico da etapa17

Rascunho para revisão do autor; não submetido. Resultados PyCrown v0.3.0
preservados, com extensão analítica pós-resultados v0.3.1-complemento.
Manuscrito LaTeX editável, figuras e evidências locais. A versão anterior está
em ../revisao_etapa15. Não executar os finalizadores14/15 sobre esta cópia.

O arquivo dados/numeros_rastreaveis.json autentica valores antigos e novos.
As receitas e tabelas integrais estão no relatório apontado por
../../relatorios/etapa17/ultima_analise.json. Os limites de pareamento são
operacionais; a coorte fixa de68IDs tem suporte comum por par, não global.

Endereço institucional e revisão/aprovação do autor continuam pendentes.
O estilo LaTeX é adaptação local declarada; a equivalência integral ao modelo
do evento ainda não foi certificada. Não classificar como pronto para submissão.
''')
    compile_at(project, dest, out/'compilacao.txt')
    print(json.dumps({'article': str(dest), 'checks': checks}, ensure_ascii=False))


def report(project, out):
    r = read_json(out/'resultados.json'); h = r['matching']['horizontal_within_corridor']; d = r['matching']['disjoint_within_corridor']
    loss = pd.read_csv(out/'perdas_elegibilidade.csv'); c = pd.read_csv(out/'estabilidade_comparisons.csv')
    fixed = c.query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'method_on_pair_support'")
    support = c.query("cohort == 'strict_fixed' and method == 'A_plus_3D' and contrast == 'support_only'")
    # Publicar também a composição dos sobreviventes, sem inferência causal sobre perdas.
    membership = pd.read_csv(out/'estabilidade_fixed_membership.csv'); profiles = []
    for status, frame in membership.groupby('in_fixed_cohort'):
        for field in ['I1', 'I4', 'I6', 'I7', 'area_total_m2', 'area_observed_m2', 'n_vegetation_records']:
            profiles.append({'in_fixed_cohort': bool(status), 'n_units': len(frame), 'indicator': field,
                **{name: float(frame[field].quantile(q)) for name, q in [('q25', .25), ('median', .5), ('q75', .75)]}})
    pd.DataFrame(profiles).to_csv(out/'perfil_sobreviventes_excluidos.csv', index=False)
    lines = ['# Informação complementar e estabilidade em coorte fixa', '',
        f'Execução `{r["run_id"]}`; fonte PyCrown `{r["source_run_id"]}`. Extensão exploratória pós-resultados solicitada pelo autor, sem nova segmentação, escolha de peso favorável ou validação externa.', '',
        '## 1. Informação vertical antes de calcular escores', '',
        f'Os 538 pares anteriores foram reproduzidos integralmente (mediana |ΔP95|=5,34m). Ao exigir também |ΔR(I4)|≤0,10 e mesmo corredor, além de |ΔI1|≤0,05 e razão de áreas≤2, restaram **{h["n_pairs"]} pares de {h["n_unique_units"]} unidades nos {h["n_corridors"]} corredores**. R(I4) é calculado uma única vez nos114IDs primários.', '',
        f'A mediana de |ΔP95| foi **{h["P95_difference_median_m"]:.2f}m**, quartis {h["P95_difference_q25_m"]:.2f}–{h["P95_difference_q75_m"]:.2f}m; |ΔIQR| mediano={h["IQR_difference_median_m"]:.2f}m. {h["P95_difference_ge_5m_n"]}/{h["n_pairs"]} pares tiveram |ΔP95|≥5m. Cinco metros é corte descritivo, não limiar ecológico ou erro de medição validado.', '',
        f'A seleção gulosa apenas por proximidade horizontal, sem reutilização de IDs, reteve **{d["n_pairs"]} pares/{d["n_unique_units"]} unidades**, com |ΔP95| mediano={d["P95_difference_median_m"]:.2f}m e |ΔIQR| mediano={d["IQR_difference_median_m"]:.2f}m. Os IDs completos e valores estão em `complementaridade_disjoint.csv`. Não há pares adjacentes nessa seleção; ainda assim, dependência espacial não foi excluída.', '',
        '**Interpretação:** a evidência já não depende de mudar pesos: existem contrastes verticais nas unidades operacionalmente próximas em dois descritores horizontais. O controle reduz a diferença de5,34m para2,40m e essa atenuação deve ser apresentada. O achado sustenta complementaridade descritiva local; não prova independência, relevância ecológica, discriminação de espécies ou superioridade de diagnóstico. Diferenças pequenas e pares quase idênticos também constam nas tabelas. A ausência de máscara/altura validadas impede separar integralmente estrutura real e erro.', '',
        'As nove combinações de limites estão em `complementaridade_sensitivity.csv`, com escopos dentro/entre/todos os corredores. As medianas por unidade e os oito resumos por corredor evitam apresentar538 ou25pares como tamanho amostral independente. A seleção sem reutilização também é sensível ao pareamento: não representa todos os pares nem maximiza a diferença vertical.', '',
        '## 2. Ordenação entre os mesmos IDs e perda de elegibilidade', '',
        f'A interseção dos IDs elegíveis em ambos os lados de todos os11pares reteve **{r["strict_fixed_units"]}/114IDs ({100*r["strict_fixed_units"]/114:.1f}%)**, dos oito corredores. Os46IDs excluídos não foram repostos. `coorte_por_corredor.csv` e `perfil_sobreviventes_excluidos.csv` mostram composição e seleção dos sobreviventes; CO_MG_02 reteve apenas4/11. A estabilidade não deve ser generalizada aos114IDs.', '',
        f'Em A+3D, principal/cenário no mesmo suporte de cada par e mesmos68IDs: **rho={fixed.spearman_rho.min():.3f}–{fixed.spearman_rho.max():.3f}; J={fixed.jaccard_exact.min():.3f}–{fixed.jaccard_exact.max():.3f}**. Todas as seleções têm k=14. Compartilham de{int(fixed.top_intersection_n.min())} a{int(fixed.top_intersection_n.max())} dos14IDs. O deslocamento médio absoluto varia de{fixed.mean_absolute_rank_shift.min():.2f} a{fixed.mean_absolute_rank_shift.max():.2f} posições. As11sensibilidades anteriores também foram reproduzidas em suas coortes variáveis.', '',
        '| Cenário | Elegíveis por par | Perdas com observação<95% | Outras perdas | rho fixo | J fixo |',
        '|---|---:|---:|---:|---:|---:|']
    for row in loss.itertuples():
        f = fixed.loc[fixed.scenario_id.eq(row.scenario_id)].iloc[0]
        lines.append(f'| {row.scenario_id} | {row.paired_eligible_units} | {row.excluded_with_insufficient_observed_fraction} | {row.excluded_other_eligibility_only} | {f.spearman_rho:.3f} | {f.jaccard_exact:.3f} |')
    lines += ['', f'O contraste principal nativo/principal recalculado só no suporte do par teve rho≥{support.spearman_rho.min():.6f}, J=1 e deslocamento médio≤{support.mean_absolute_rank_shift.max():.3f} posições em F*. Assim, entre esses sobreviventes, a restrição de suporte teve efeito pequeno sobre a ordenação; isso não minimiza a exclusão dos demais. Os contrastes de método, suporte e total estão separados em `estabilidade_comparisons.csv`, também para A. Não são componentes aditivos.', '',
        '**Geometria:** F* fixa os IDs, não uma interseção global de pixels. Cada comparação herda a mesma interseção vetorial observada nos dois lados, autenticada nas fontes da etapa12. O suporte pode variar entre cenários; `estabilidade_area.csv` registra isso por unidade. Portanto não se declara robustez sob geometria global idêntica. Normalizadores usam os mesmos68IDs, com indicadores novamente medidos e postos recalculados.', '',
        '## 3. Como a mensagem científica muda', '',
        'Formulação sustentada: “Atributos de altura revelam contrastes verticais entre unidades semelhantes em cobertura e fragmentação, sem depender da ponderação do índice. Entre IDs elegíveis em todas as sensibilidades, a concordância global é elevada, mas a composição das listas superiores permanece sensível. A perda de elegibilidade constitui um segundo limite, quantificado separadamente.”', '',
        'Evitar “o LiDAR melhora a prioridade”, “as diferenças são significativas”, “há equivalência2D comprovada” ou “68unidades representam os corredores”. O resultado mais forte é a mensuração da heterogeneidade vertical condicional e da fragilidade da seleção superior, não uma recomendação de intervenção. Pareamento pós-resultados e semântica de copa não validada permanecem limites explícitos.', '',
        '## Reprodução e verificações', '',
        '```bash', '.venv-cientifico/bin/python scripts/analisar_complemento_etapa17.py', '.venv-cientifico/bin/python -m pytest tests/cientifico/test_complementary_analysis.py -q', '```', '',
        'Cada execução cria pasta própria. Regras e protocolo são copiados antes dos cálculos; SHA-256 dos arquivos de entrada, selos recursivos e código constam em `proveniencia.json`. O uso das fontes não altera suas chaves ou caches. Figuras PDF/SVG/PNG600dpi estão em `figuras/`. A revisão de artigo fica em `artigo/complemento_etapa17/`; a versão15 foi preservada.', '',
        'Como referência metodológica geral, a necessidade de examinar os efeitos da ponderação e a robustez das inferências em indicadores compostos é discutida no [guia do JRC](https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en). Os limites de pareamento e a coorte desta análise são decisões locais documentadas, não regras prescritas pelo guia.']
    (project/'docs/complemento_analitico_etapa17.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    project = Path(__file__).resolve().parents[1]
    out = Path(read_json(project/'relatorios/etapa17/ultima_analise.json')['output_root'])
    figures(out); report(project, out); article(project, out)
