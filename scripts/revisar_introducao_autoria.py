"""Revisão editorial 0.3.4: lacuna, contribuições, autoria e repositório."""
from pathlib import Path
import argparse
import json
import re
import shutil

import yaml

from sbsr_lidar.storage import read_json, atomic_write_json, fingerprint
from etapa15.editorial import compile_at


REVISION = '0.3.4-introducao-autoria'
ARTICLE = 'artigo/revisao_introducao_v0_3_4'
REPOSITORY = 'https://github.com/kikosmoura/sbsr_lidar_2027'
AUTHORS = [
    {'name': 'Carlos Henrique de Moura Silva',
     'affiliation': 'SERPRO – Serviço Federal de Processamento de Dados',
     'address': 'Rua Olívia Guedes Penteado, 941, São Paulo – SP',
     'email': 'carlos-henrique.silva@serpro.gov.br', 'affiliation_marker': 1},
    {'name': 'Luana Martins da Silva',
     'affiliation': 'SERPRO – Serviço Federal de Processamento de Dados',
     'address': 'Rua Olívia Guedes Penteado, 941, São Paulo – SP',
     'email': 'luana.silva@serpro.gov.br', 'affiliation_marker': 2},
]

INTRODUCTION = r'''\section{Introdução}
% EVIDENCIA: C34_I | exploratoria | C34_01,C17_01,C17_02,C13_06
Cobertura e fragmentação descrevem a vegetação horizontalmente; o LiDAR caracteriza sua organização vertical~\cite{lefsky1999}. Sua fusão com dados espectrais foi explorada em árvores urbanas~\cite{alonzo2014}. Acrescentar variáveis a escores não demonstra melhora de diagnóstico. Comparar listas superiores avalia alterações nas funções de ordenação~\cite{fagin2003}; correlações globais podem ocultar substituições no corte.

A lacuna investigada nestes corredores é verificar se persistem diferenças verticais entre unidades semelhantes em 2D e se ordenações aparentemente estáveis preservam as unidades selecionadas quando mudam suporte e elegibilidade. Mudar pesos e obter outra ordem não responde a essas questões.

As duas contribuições são: (1) quantificar contrastes de P95/IQR entre pares do mesmo corredor, controlando cobertura e fragmentação antes da ponderação (H1); (2) avaliar a sensibilidade em coorte fixa, distinguindo concordância global, permanência nas listas superiores e perda de elegibilidade (H2). O recorte exploratório é retrospectivo: LiDAR de \Par{lidar_year} nos perímetros disponíveis em \Par{geometry_year}, sem validação externa de copas ou causalidade sobre implantação.

'''

NEW_BIB = r'''
@article{lefsky1999,
  author = {Lefsky, M. A. and Cohen, W. B. and Acker, S. A. and Parker, G. G. and Spies, T. A. and Harding, D.},
  title = {{Lidar Remote Sensing of the Canopy Structure and Biophysical Properties of Douglas-Fir Western Hemlock Forests}},
  journal = {Remote Sensing of Environment},
  year = {1999},
  volume = {70},
  number = {3},
  pages = {339--361},
  doi = {10.1016/S0034-4257(99)00052-8},
  note = {\url{https://doi.org/10.1016/S0034-4257(99)00052-8}}
}

@article{fagin2003,
  author = {Fagin, Ronald and Kumar, Ravi and Sivakumar, D.},
  title = {{Comparing Top $k$ Lists}},
  journal = {SIAM Journal on Discrete Mathematics},
  year = {2003},
  volume = {17},
  number = {1},
  pages = {134--160},
  doi = {10.1137/S0895480102412856},
  note = {\url{https://doi.org/10.1137/S0895480102412856}}
}
'''


def replace_paragraph(source, prefix, replacement):
    blocks = source.split('\n\n')
    hits = [i for i, b in enumerate(blocks) if re.search('^'+re.escape(prefix), b, re.M)]
    if len(hits) != 1:
        raise ValueError(f'Parágrafo sem identificação única: {prefix}')
    i = hits[0]
    start = re.search('^'+re.escape(prefix), blocks[i], re.M).start()
    blocks[i] = blocks[i][:start]+replacement
    return '\n\n'.join(blocks)


def compact_methods(source):
    """Concisão textual, preservando parâmetros, fórmulas e limites científicos."""
    replacements = [
        ('Utilizaram-se produtos', r'''Usaram-se MDT/MDS LiDAR e perímetros de corredores verdes do GeoSampa~\cite{geosampa}. A seleção intencional reuniu \Ev{corridors_total} corredores propostos em blocos de proximidade: \Ev{corridors_development} de desenvolvimento e \Ev{corridors_evaluation} de avaliação, sem assegurar independência. No protocolo exploratório v0.3.0, mediu-se no polígono original $P$; o contexto externo de \Par{halo}~m serviu só ao processamento, em SIRGAS2000/UTM23S (EPSG:\Par{epsg}).'''),
        ('Foram decodificados', r'''Decodificaram-se \Ev{source_files_qc} arquivos (\Ev{source_tile_pairs} pares MDT/MDS), com CRC conferido. Janelas de \Par{window}~m e propriedade única limitaram memória/duplicação; retornos compartilhados não são independentes. Normalizou-se $H=Z_{\mathrm{abs}}-\widehat z_{\mathrm{TIN}}(X,Y)$, com suporte máximo de \Par{tin_radius}~m. Usou-se MDT por procedência/QC, sem equiparar classe 8 a terreno LAS padrão ou reaplicar correção geoidal.'''),
        ('As grades de', r'''Recortaram-se grades de \Par{scales}~m a $P$, com análise principal em \Par{main_scale}~m. Exigiram-se área efetiva $\geq\Par{area_min}$~m$^2$, fração observada $\geq\Par{observed_min}\%$, copa detectada $\geq\Par{canopy_min}$~m$^2$ e $\geq\Par{returns_min}$ retornos vegetais para alturas. Selecionaram-se até \Par{target_per_corridor} elegíveis por corredor por \textit{hash} de ID/semente \Par{seed}, sem consultar discordâncias ou repor inelegíveis. Ausência de MDS, terreno/H inválido e exclusão por QC diferem de observado sem copa.'''),
        ('O CHM tomou', r'''O CHM usou Hmáx das classes 3/4/5, sem suavizar/preencher lacunas. Segmentou-se o contexto antes dos recortes. O delineamento por máximos/crescimento~\cite{dalponte2016,zorner2018} usou rotinas circulares originais do PyCrown~\cite{pycrown}, \textit{commit} 3d8db4e, com IO adaptado. Centroides de platô fora do máximo foram realocados ao pixel pertencente mais próximo; não se corrigiram topos pelo MDS.'''),
        ('No cenário principal, a resolução', r'''O principal usou resolução \Par{resolution}~m, $H>\Par{height}$~m, raios de detecção/copa \Par{detection_radius}/\Par{crown_radius}~m e limiares relativos 0,7/0,55. A máscara comum uniu as áreas observadas dos segmentos estimados. Definiram-se $I_1=T/O$, $I_4=10^4N_m/O$: $T$ é área dessa união, $O$ área observada e $N_m$ manchas conectadas no contexto que intersectam a unidade, não árvores. $I_6=P_{95}(H)$ e $I_7=P_{75}(H)-P_{25}(H)$ são quantis lineares exatos de retornos vegetais normalizados na máscara, não alturas médias de árvores.'''),
        ('Normalizou-se cada indicador', r'''Normalizou-se por $R(x)=(r_{\mathrm{médio}}(x)-0{,}5)/n$ na mesma coorte; constantes recebem 0,5. A configuração experimental foi
\begin{align}
S_A&=\tfrac12[1-R(I_1)+R(I_4)],\\
V_{\mathrm{exp}}&=\tfrac12[1-R(I_6)+1-R(I_7)],\\
S_{A+3D}&=(1-w)S_A+wV_{\mathrm{exp}} .
\end{align}
O principal usou $w=\Par{primary_weight}$. Por construção, $1-R(I_6)$ e $1-R(I_7)$ elevam escores para menor altura/dispersão: configuração experimental, sem interpretá-las como degradação, déficit ecológico ou necessidade de intervenção. P95/IQR não são indicadores calibrados de biodiversidade/habitat. Excluíram-se análises longitudinais por falta de eixos revalidados.'''),
        ('Os escores usam', r'''Escores usam 12 casas nos empates; Spearman, postos médios; Jaccard, listas superiores de \Par{top_percent}\%, $k=\lceil\Par{top_fraction}n\rceil$, com desempate por ID. Controles: pesos 0/0,25/0,5/0,75, sinal oposto de $I_7$, $I_6$ isolado/duplicado. H1 exigia diferença de $I_1\leq\Par{cover_tolerance}$ e razão de áreas observadas $\leq\Par{area_ratio}$. O complemento pós-resultados acrescentou $|\Delta R(I_4)|\leq\Par{comp_fragmentation_caliper}$ (R nos \Ev{units_evaluation} IDs) e mesmo corredor: semelhança operacional, não equivalência estatística. Testaram-se nove combinações: I1=0,025/0,05/0,10 e R(I4)=0,05/0,10/0,20. A seleção gulosa sem reutilizar IDs ordenou distâncias horizontais/IDs, sem consultar alturas. Pares e vizinhos espaciais não são réplicas independentes.'''),
        ('Os \\Par{scenario_count} cenários', r'''Os \Par{scenario_count} cenários variaram resolução, limiar H, raios, algoritmo e retenção MDS 50/25\%, uma variável por vez/uma semente; MDT não rarefeito. Em 2~m, o raio nominal 3~m equivale a 4~m. Recalcularam-se principal/cenário na interseção observada e renormalizaram-se receitas nos IDs elegíveis dos dois lados de todos os 11 pares. Compararam-se principal/cenário no suporte do par, principal nativo/principal nesse suporte e principal nativo/cenário nesse suporte. Rho/Jaccard não são aditivos; IDs fixos não implicam geometria global fixa. Sem independência, não se calcularam IC/$p$~\cite{hurlbert1984}.'''),
    ]
    for prefix, replacement in replacements:
        source = replace_paragraph(source, prefix, replacement)
    source = source.replace('renormalizaram-se receitas nos IDs elegíveis dos dois lados de todos os 11 pares',
        'renormalizaram-se receitas na coorte fixa dos IDs elegíveis nos dois lados de todos os 11 pares')
    source = source.replace('Unidade escolhida pelo primeiro \\textit{hash} da coorte de avaliação, ilustrativa e pós-resultados; não são contornos validados. Escala comum aos exemplos do pacote. Fonte: GeoSampa e processamento v0.3.0.',
        'Unidade ilustrativa pós-resultados, primeiro \\textit{hash} da avaliação; contornos sem validação. Escala comum ao pacote. Fonte: GeoSampa/processamento v0.3.0.')
    return source


def compact_discussion(source):
    replacements = [
        ('A fração observada variou', r'''A fração observada foi \Ev{observed_fraction_min_percent}\%--\Ev{observed_fraction_max_percent}\% (Tabela~\ref{tab:amostra}). Houve \Ev{units_evaluation} unidades de avaliação (meta \Ev{target_evaluation}) e \Ev{units_development} de desenvolvimento, sem reposição. Representam parcelas elegíveis, não corredores completos ou o município.'''),
        ('Permaneceram', r'''Foram \Ev{sensitivity_paired_eligible_units_min}--\Ev{sensitivity_paired_eligible_units_max} elegíveis por comparação e \Ev{comp_fixed}/\Ev{units_evaluation} em todas. Na coorte fixa, $\rho$=\Ev{comp_rhomin}--\Ev{comp_rhomax}, $J$=\Ev{comp_jmin}--\Ev{comp_jmax} e $k=\Ev{comp_k}$ (Figura~\ref{fig:sens}). No contraste de suporte, $\rho$ mínimo=\Ev{comp_support_rhomin} e listas coincidentes. Com MDS 25\%, $\rho=\Ev{fin_rho25}$, mas só \Ev{fin_shared25} unidades compartilhadas: \Ev{fin_replaced25} saídas/\Ev{fin_replaced25} entradas, substituição de \Ev{fin_replaced_pct25}\% por lista. Rho resume a ordem global; permanência no corte qualifica robustez da identificação, sem prioridade ecológica validada. Nesse cenário perderam-se \Ev{comp_worst_excluded} IDs: \Ev{comp_worst_observation} por observação insuficiente, \Ev{comp_worst_other} por outros critérios. A estabilidade dos sobreviventes não representa os excluídos.'''),
        ('O atestado do levantamento', r'''O atestado de 2020 declara PEC-PCD Classe A e \Ev{rev_declared_checks} controles, sem resíduos/RMSE~\cite{atestado2020}. Nas \Ev{rev_point_windows} janelas TIN5 de avaliação, a mediana dos RMSEs foi \Ev{rev_point_rmse}~m com pontos MDT reservados e \Ev{rev_block_rmse}~m com blocos; frações válidas: \Ev{rev_point_coverage}\%/\Ev{rev_block_coverage}\%. Em blocos, \Ev{rev_block_valid_windows} janelas tiveram resíduos válidos. Esse QC interno não mede acurácia externa de H/copa. Erros de Z/TIN e sua covariância, máscara, oclusão e seleção acrescentam incerteza; não se demonstrou que os contrastes superam o erro total.'''),
        ('A segmentação pode', r'''A segmentação pode dividir/reunir objetos e herdar erros de classe. Máscara não validada, filtros geométricos do piloto incompletos e percentis ponderados por retornos limitam a interpretação. Dados ausentes, vegetação não detectada e ausência real diferem. Suporte parcial, seleção intencional e perímetros posteriores à aquisição impedem extrapolação municipal/causalidade sobre planejamento.'''),
    ]
    # Reutilizar as chaves numéricas existentes para preservar seus valores e fontes.
    for prefix, replacement in replacements:
        source = replace_paragraph(source, prefix, replacement)
    source = source.replace('Contraste principal/cenário no suporte de cada par: coorte fixa de \\Ev{comp_fixed} IDs e subcoortes variáveis. Os n à direita pertencem às subcoortes variáveis. Spearman elevado não assegura coincidência das listas superiores; sem IC ou acurácia externa.',
        'Principal/cenário no suporte de cada par: coorte fixa de \\Ev{comp_fixed} IDs e subcoortes variáveis (n à direita). Spearman elevado não assegura coincidência das listas superiores; sem IC ou validação externa.')
    return source


def prepare(project, out):
    article = project/ARTICLE
    if article.exists():
        raise ValueError('Revisão já existe; preservar edições e usar --compile')
    shutil.copytree(project/'artigo/revisao_final_v0_3_3', article)
    source_path = article/'manuscrito.tex'
    source = source_path.read_text()
    start, end = source.index(r'\section{Introdução}'), source.index(r'\section{Material e métodos}')
    source = source[:start] + INTRODUCTION + source[end:]
    source = source.replace(r'\address{\AutoriaAfiliacoes\\\AutoriaContato}', r'\address{\AutoriaAfiliacoes}')
    source = source.replace('pdfauthor={Carlos Henrique de Moura Silva}',
                            'pdfauthor={Carlos Henrique de Moura Silva; Luana Martins da Silva}')
    source = source.replace('revisão quantitativa 0.3.3', 'revisão de introdução e autoria 0.3.4')
    # A referência de delineamento continua junto ao método correspondente.
    source = source.replace(r'PyCrown~\cite{pycrown}', r'PyCrown~\cite{pycrown,dalponte2016,zorner2018}')
    source = source.replace(r'\renewcommand{\refname}{REFERÊNCIAS}',
        '\\smallskip\\noindent\\textbf{Código.} Os códigos do projeto serão disponibilizados em:\\newline\n'
        '\\url{'+REPOSITORY+'}.\n\n'+r'\renewcommand{\refname}{REFERÊNCIAS}')
    source = compact_discussion(compact_methods(source))
    source_path.write_text(source)
    bibliography = (article/'referencias.bib').read_text()+NEW_BIB
    # Manter o link integral do atestado clicável, com descrição legível no PDF.
    full_url = read_json(article/'dados/referencias_verificadas.json')['references'][-1]['primary_url']
    bibliography = bibliography.replace(r'\url{'+full_url+'}',
        r'\href{'+full_url+r'}{GeoSampa, documentação do levantamento}')
    (article/'referencias.bib').write_text(bibliography)
    (article/'autores.tex').write_text(r'''% Transcrição da figura fornecida pelo usuário em 30/10/2026.
\newcommand{\AutoriaNomes}{\textit{Carlos Henrique de Moura Silva}\textsuperscript{1}, \textit{Luana Martins da Silva}\textsuperscript{2}}
\newcommand{\AutoriaAfiliacoes}{%
\textsuperscript{1}SERPRO – Serviço Federal de Processamento de Dados, Rua Olívia Guedes Penteado, 941, São Paulo – SP, \mbox{carlos-henrique.silva@serpro.gov.br}\\
\textsuperscript{2}SERPRO – Serviço Federal de Processamento de Dados, Rua Olívia Guedes Penteado, 941, São Paulo – SP, \mbox{luana.silva@serpro.gov.br}}
\newcommand{\AutoriaContato}{carlos-henrique.silva@serpro.gov.br}
''')
    (article/'autoria.yaml').write_text(yaml.safe_dump({
        'status': 'informado_pelo_usuario', 'source': 'figura_anexada_pelo_usuario_em_2026-10-30',
        'authors': AUTHORS, 'corresponding_author': 0, 'human_review_completed': False},
        allow_unicode=True, sort_keys=False))
    style = article/'formato_sbsr_local.sty'
    style.write_text(style.read_text().replace('apreciação do autor', 'apreciação dos autores'))
    reference_notes = [
        {'key': 'lefsky1999', 'doi': '10.1016/S0034-4257(99)00052-8',
         'title': 'Lidar Remote Sensing of the Canopy Structure and Biophysical Properties of Douglas-Fir Western Hemlock Forests',
         'primary_url': 'https://doi.org/10.1016/S0034-4257(99)00052-8',
         'author_copy_url': 'https://core2.gsfc.nasa.gov/icesat/papers/1999_rem_sens_envi_LEFSKY%28HARDING%292.pdf',
         'verified_on': '2026-10-30', 'verification': 'Página editorial e texto original disponibilizado pela NASA; autores, título, periódico, volume, ano e páginas conferidos.',
         'use': 'Caracterização vertical da vegetação, complementar à descrição horizontal.',
         'limits': 'Estudo florestal com waveform; não transfere acurácia, biomassa ou validação para os corredores e retornos discretos deste projeto.'},
        {'key': 'fagin2003', 'doi': '10.1137/S0895480102412856',
         'title': 'Comparing Top k Lists',
         'primary_url': 'https://epubs.siam.org/doi/10.1137/S0895480102412856',
         'author_copy_url': 'https://www.biz.uiowa.edu/faculty/nstreet/Fagin03.pdf',
         'verified_on': '2026-10-30', 'verification': 'Página SIAM e artigo original consultados; autores, volume 17(1), páginas 134–160 e ano 2003 conferidos.',
         'use': 'Comparação de listas superiores sob variações da função de ordenação e distinção de rankings completos.',
         'limits': 'Fundamentação metodológica; não valida prioridade ecológica nem introduz novas métricas no experimento.'},
    ]
    atomic_write_json(out/'referencias_adicionadas.json', {'references': reference_notes})
    refs_path = article/'dados/referencias_verificadas.json'
    refs = read_json(refs_path); refs['references'] += reference_notes
    atomic_write_json(refs_path, refs)
    with (article/'notas_referencias.md').open('a') as handle:
        handle.write('\n\n## Ampliação em 30/10/2026\n\n')
        for record in reference_notes:
            handle.write(f'- [{record["title"]}]({record["primary_url"]}): {record["use"]} {record["limits"]}\n')
    atomic_write_json(article/'dados/afirmacoes_introducao.json', {'claims': [{
        'claim_id': 'C34_01', 'statement': 'Lacuna local e duas contribuições: contraste vertical antes de ponderar e estabilidade condicional em coorte fixa.',
        'limitations': ['sem_pioneirismo_bibliografico_alegado', 'exploratorio_pos_resultados',
                        'sem_validacao_externa', 'sem_prioridade_ecologica_validada'],
        'references': ['lefsky1999', 'alonzo2014', 'fagin2003'],
        'evidence': fingerprint(out/'referencias_adicionadas.json')} ]})
    (article/'README.md').write_text('''# Revisão de introdução e autoria — v0.3.4

Rascunho revisado para apreciação dos autores. Versão anterior preservada em
`../revisao_final_v0_3_3`. Lacuna local e duas contribuições explicitadas;
referências de estrutura vertical e comparação de listas superiores incluídas.
Carlos Henrique de Moura Silva e Luana Martins da Silva, com filiações,
endereços, e-mails e marcadores conforme a figura fornecida pelo usuário.

Repositório destinado aos códigos: https://github.com/kikosmoura/sbsr_lidar_2027
A frase no artigo usa o futuro porque o autor informou que ainda incluirá os
códigos. Esta revisão não publicou arquivos ou verificou a disponibilidade deles.

Compilar: `.venv-cientifico/bin/python scripts/revisar_introducao_autoria.py --compile`.
Os resultados científicos, escores e coortes permanecem os da versão anterior.
''')
    return article


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--compile', action='store_true')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    out = Path(read_json(project/'relatorios/revisao_introducao_autoria/ultima_execucao.json')['output_root'])
    if args.prepare:
        prepare(project, out)
    if args.prepare or args.compile:
        print(json.dumps(compile_at(project, project/ARTICLE, out/'compilacao.txt'), ensure_ascii=False))
