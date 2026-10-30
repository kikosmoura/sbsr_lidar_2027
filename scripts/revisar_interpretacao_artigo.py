"""Revisão0.3.2: escores experimentais, distribuição dos16pares e QC interno."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import re
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

from sbsr_lidar.storage import read_json, fingerprint, atomic_write_json
from sbsr_lidar.measurement_review import pair_distribution, terrain_holdouts, summarize_terrain

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etapa14.audit import (abstract_counts, verify_registry, bibliography_checks, claims_matrix)
from etapa14.build import display
from etapa15.editorial import compile_at

ATTESTATION_URL = 'https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/intranet/api/records/892c862e-f564-4b1c-a3d0-9d28052e5d58/attachments/voo2020_ATESTADO-T%C3%89CNICO_PMSP.pdf'


def check(path, expected):
    actual = fingerprint(Path(path))
    if actual != expected: raise ValueError(f'Fonte mudou: {path}')
    return actual


def analyze(project, out):
    manifest = read_json(project/'docs/manifesto_etapa17.json'); inventory = {x['path']: x for x in manifest['artifacts']}
    source_analysis = Path(read_json(project/'relatorios/etapa17/ultima_analise.json')['output_root'])
    path = source_analysis/'complementaridade_disjoint.csv'; used = [check(path, inventory[str(path)])]
    pairs = pd.read_csv(path); distribution = pair_distribution(pairs)
    pairs.to_csv(out/'pares16_preservados.csv', index=False); distribution.to_csv(out/'distribuicao_pares16.csv', index=False)
    run = read_json(project/'relatorios/etapa12/execucao.json')
    stage12 = {x['path']: x for x in read_json(project/'docs/manifesto_etapa12.json')['artifacts']}
    rows, unavailable = [], []
    for cid, case in sorted(run['case_results'].items()):
        if case['role'] != 'evaluation': continue
        root = Path(case['root']); seal = root/'complete.json'; used.append(check(seal, stage12[str(seal)]))
        outputs = {x['path']: x for x in read_json(seal)['outputs']}
        qc = root/'qc.json'; used.append(check(qc, outputs[str(qc)]))
        fp = read_json(qc)['internal_validation']; used.append(check(Path(fp['path']), fp))
        r, missing = terrain_holdouts(read_json(Path(fp['path'])), cid); rows.extend(r); unavailable.extend(missing)
    terrain = summarize_terrain(rows)
    pd.DataFrame(rows).to_csv(out/'qc_tin5_por_janela.csv', index=False)
    pd.DataFrame(unavailable).to_csv(out/'qc_tin5_metricas_indisponiveis.csv', index=False)
    directory = out/'fontes'; directory.mkdir(exist_ok=True)
    for name in ['metadados_mds.xml', 'metadados_mdt.xml', 'atestado_tecnico_2020.pdf']:
        original = project/'relatorios/diagnostico_2026-10-25/fontes'/name
        shutil.copyfile(original, directory/name); used.append(fingerprint(original))
    pdf = directory/'atestado_tecnico_2020.pdf'
    text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)
    (directory/'atestado_tecnico_2020.txt').write_text(text)
    normalized = ' '.join(text.split())
    match = re.search(r'(\d+) pontos para o controle da qualidade', normalized)
    if match is None: raise ValueError('Número de pontos de controle não encontrado no atestado')
    metrology = {'source_url': ATTESTATION_URL, 'official_document': fingerprint(pdf),
        'check_points_declared_for_products': int(match.group(1)), 'check_point_coordinates_supplied': False,
        'declares_PEC_PCD_A': bool(re.search(r'Classe\s*[“\"]A[”\"]', normalized)),
        'numerical_external_vertical_rmse_m': None, 'per_checkpoint_residuals_available_in_consulted_documents': False,
        'source_scope': 'official_MDT_MDS2020_XML_and_linked_2020_attestation_not_all_possible_records',
        'publication_year_of_attestation': None, 'survey_year': 2020,
        'same_sensor_QC_is_not_external_accuracy': True,
        'resolution_or_LAS_scale_not_used_as_vertical_accuracy': True,
        'other_surveys_or_manufacturer_accuracy_not_transferred': True}
    if not metrology['declares_PEC_PCD_A']: raise ValueError('Declaração PEC não localizada')
    # Nenhum valor de precisão é inventado na ausência de relatório de resíduos.
    atomic_write_json(out/'metadados_avaliados.json', metrology)
    summary = {'version': '0.3.2-interpretacao', 'source_scientific_protocol': '0.3.0',
        'source_analytical_extension': '0.3.1-complemento', 'source_run_id': run['run_id'],
        'disjoint_pairs': {x['descriptor']: x for x in distribution.to_dict('records')},
        'internal_TIN5_QC': terrain, 'metrology': metrology,
        'score_interpretation': 'experimental_no_ecological_valence', 'scientific_scores_changed': False,
        'new_LAZ_processing': False, 'new_ground_validation_run': False,
        'external_accuracy_estimated': False, 'difference_above_total_measurement_error_established': False}
    atomic_write_json(out/'resultados.json', summary)
    atomic_write_json(out/'fontes_utilizadas.json', {'inputs': used,
        'module': fingerprint(project/'src/sbsr_lidar/measurement_review.py'),
        'configuration': fingerprint(out/'revisao_interpretacao_v0_3_2.yaml'),
        'official_sources_consulted_on': '2026-10-30', 'external_messages_sent': False})
    write_report(project, out, summary)
    return summary


def write_report(project, out, result):
    d = result['disjoint_pairs']; q = result['internal_TIN5_QC']; m = result['metrology']
    point, block = q['reserved_points'], q['reserved_blocks']
    rows = []
    for name, x in d.items():
        rows.append('| '+name+' | '+' | '.join(f'{x[k]:.2f}' for k in ['minimum_m','q25_m','median_m','q75_m','maximum_m'])+' |')
    content = f'''# Revisão de interpretação ecológica, distribuição dos pares e medição

A revisão mantém todos os escores, os mesmos16pares e a coorte fixa do
complemento17. Os arquivos anteriores foram preservados. É uma revisão
exploratória de interpretação e apresentação, não validação externa.

## Pontuação e significado dos indicadores

I6=P95(H) descreve a cauda superior das alturas dos retornos selecionados;
I7=IQR(H), sua dispersão interquartil. Não são indicadores calibrados de
biodiversidade, qualidade de habitat, biomassa ou necessidade de intervenção.
Os sinais1−R(I6) e1−R(I7) fazem alturas/dispersões menores aumentar o escore por
construção. Essa orientação fica explicitamente identificada como configuração
experimental de ordenação. Não será defendida como relação ecológica universal.
O símbolo Vexp substitui V+ apenas no manuscrito; o identificador histórico
Vplus e os resultados numéricos permanecem os mesmos. A comparação vertical
dos pares independe dessa pontuação.

## Distribuição dos mesmos16pares

Diferenças absolutas em metros, quantis lineares, sem reutilização de IDs.

| Descritor | Mínimo | Q1 | Mediana | Q3 | Máximo |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

A distribuição tem diferenças quase nulas e uma cauda de valores elevados.
A complementaridade descritiva é heterogênea; não se afirma que toda unidade
semelhante em2D difere substancialmente em3D. A mediana de P95={d['P95']['median_m']:.2f}m
não resume sozinha essa assimetria. Os IDs e os valores individuais estão em
`pares16_preservados.csv`; não houve seleção pelos maiores contrastes.

## Metadados do levantamento2020

Foram examinados os XML oficiais MDT/MDS e o [atestado técnico vinculado a
eles]({ATTESTATION_URL}). O documento declara PEC-PCD ClasseA e menciona
{m['check_points_declared_for_products']} pontos para controle da qualidade dos produtos, mas não fornece
as coordenadas desses pontos, resíduos individuais ou RMSE altimétrico.
Portanto, os documentos consultados não permitem estimar numericamente a
acurácia absoluta ou relativa dos percentis usados no estudo. Isso não afirma
que outros relatórios do produtor inexistam: a busca pública não os obteve.

O [contrato33/2022](https://www.prefeitura.sp.gov.br/cidade/upload/contrato_33_2022_-_fototerra_transparncia_1660825403.pdf)
remete ao Termo de Referência; o PDF consultado não contém uma tabela de
resíduos. A notícia/tutorial de2017 e a precisão nominal de equipamento não
foram transferidas ao levantamento2020. Resolução espacial0,50m, densidade e
quantização LAS0,001m também não são medidas de erro vertical.

Há divergências de descrição entre fontes: o XML MDT menciona10pontos/m²,
enquanto o atestado descreve densidade4pulsos/m² após filtragem de terreno.
A linhagem do XML MDS descreve uma subtração MDS−MDT, enquanto a auditoria dos
LAZ demonstrou Z absoluto. Essas descrições não substituem o exame dos dados
reais nem fundamentam uma precisão numérica fictícia. Originais não alterados.

## Checagens internas TIN5 já existentes

Somente oito corredores de avaliação; três janelas por corredor selecionadas
por hash na execução original. Não houve nova normalização ou retenção de
pontos. Os resíduos são contra MDT reservado do mesmo sensor, com TIN5 fixo.

| Retenção | Janelas com RMSE / testadas | RMSE mediano por janela (m) | RMSE mínimo–máximo (m) | Registros com suporte válido |
|---|---:|---:|---:|---:|
| Pontos | {point['n_windows_with_valid_residuals']}/{point['n_windows']} | {point['window_rmse_m']['median']:.3f} | {point['window_rmse_m']['minimum']:.3f}–{point['window_rmse_m']['maximum']:.3f} | {100*point['valid_record_fraction']:.2f}% |
| Blocos | {block['n_windows_with_valid_residuals']}/{block['n_windows']} | {block['window_rmse_m']['median']:.3f} | {block['window_rmse_m']['minimum']:.3f}–{block['window_rmse_m']['maximum']:.3f} | {100*block['valid_record_fraction']:.2f}% |

Cada janela pesa igualmente no resumo dos RMSE. A cobertura válida é razão
entre registros válidos e avaliados, incluindo janelas com zero suporte.
Não atribuir RMSEzero às duas janelas sem resíduos válidos em blocos. As
contagens representam registros dependentes, não réplicas independentes.
Os detalhes estão em `qc_tin5_por_janela.csv` e
`qc_tin5_metricas_indisponiveis.csv`.

Esse controle quantifica consistência de interpolação nas parcelas com
suporte. Não mede erro absoluto de Z, erro da copa, omissão de retornos sob
vegetação ou a totalidade da incerteza em H. A cobertura baixa dos blocos
também impede transferir o RMSE às áreas sem suporte ou tratá-lo como limite
máximo de erro. Não comparar2,80m a esse RMSE para declarar significância.

## Componentes de incerteza e condição para uma conclusão mais forte

Se eH=eZ−eTIN, a variância do erro normalizado depende das variâncias de cada
parcela e de−2Cov(eZ,eTIN). MDT e MDS compartilham observações; independência
e cancelamento de erros não foram demonstrados. Um deslocamento constante em
H altera P95 mas não IQR; se compartilhado pelas duas unidades, cancela na
diferença de P95. Erros espacialmente variáveis, de classificação/segmentação
e de seleção de retornos não têm esse cancelamento garantido. Não dividir um
RMSE por raiz do número de retornos correlacionados.

| Componente | Evidência disponível | O que continua desconhecido |
|---|---|---|
| Georreferenciamento vertical | Datum nos LAZ e declaração do produtor | Viés, resíduos de pontos independentes, erros por faixa/tipo de superfície |
| Interpolação de terreno | Retenções TIN5 do mesmo sensor | Erro absoluto e comportamento sob copa/sem suporte |
| Seleção de retornos e máscara | QC e sensibilidades internas | Omissão/comissão, fusão/divisão e erro de classificação contra referência |
| P95/IQR e diferenças entre unidades | Distribuições observadas e pareamento | Propagação do erro correlacionado e incerteza total dos percentis |

Uma conclusão de diferenças superiores ao erro total requer relatório de
controle do levantamento2020 com coordenadas e resíduos, separação dos pontos
de ajuste/checagem, datum/unidades e avaliação por superfície/faixa; além de
referência/modelo de erro apropriado para a seleção de vegetação. A existência
de controle de terreno, isoladamente, não valida copas. A revisão conserva
essa condição como limitação explícita.

## Reprodução

```bash
.venv-cientifico/bin/python scripts/revisar_interpretacao_artigo.py --analyze
.venv-cientifico/bin/python scripts/revisar_interpretacao_artigo.py --verify
.venv-cientifico/bin/python -m pytest tests/cientifico/test_measurement_review.py -q
```

Fontes, estatísticas e código têmSHA-256. O artigo revisado está em
`artigo/revisao_interpretacao_v0_3_2/`; os resultados e o manifesto estão
apontados por `relatorios/revisao_interpretacao/ultima_execucao.json`.
'''
    content = readable_prose(content)
    (project/'docs/revisao_interpretacao_artigo.md').write_text(content)


def readable_prose(text):
    for a,b in {'mesmos16pares':'mesmos 16 pares', 'dos16pares':'dos 16 pares', 'levantamento2020':'levantamento 2020',
                'levantamento2017':'levantamento 2017', 'de2017':'de 2017', 'ClasseA':'Classe A',
                'sinais1−':'sinais 1−', ' e1−':' e 1−', 'em2D':'em 2D', 'em3D':'em 3D',
                'P95=':'P95 = ', 'contrato33/2022':'contrato 33/2022', 'espacial0,50':'espacial 0,50',
                'LAS0,001':'LAS 0,001', 'menciona10':'menciona 10', 'densidade4':'densidade 4',
                'RMSEzero':'RMSE zero', 'comparar2,80':'comparar 2,80', 'eH=eZ−eTIN':'eH = eZ − eTIN',
                'de−2Cov':'de −2Cov', 'têmSHA':'têm SHA'}.items(): text = text.replace(a,b)
    text = re.sub(r'\b(com|de|dos|nos|em|para|por|RMSE|cobertura|mediano|janela)(?=\d)',r'\1 ',text)
    return re.sub(r'(?<=\d)(m|pontos|pulsos|pares|janelas|IDs|valores|parâmetros|testes|figuras|tabelas|referências)\b', r' \1', text)


def add_numbers(out, article):
    registry = read_json(article/'dados/numeros_rastreaveis.json'); result = read_json(out/'resultados.json')
    keys = {}
    for name in ['P95', 'IQR']:
        for stat in ['q25_m', 'median_m', 'q75_m', 'maximum_m']:
            keys[f'rev_{name}_{stat}'] = (f'/disjoint_pairs/{name}/{stat}', 2, 1)
    keys.update({
        'rev_point_windows': ('/internal_TIN5_QC/reserved_points/n_windows', 0, 1),
        'rev_block_valid_windows': ('/internal_TIN5_QC/reserved_blocks/n_windows_with_valid_residuals', 0, 1),
        'rev_point_rmse': ('/internal_TIN5_QC/reserved_points/window_rmse_m/median', 3, 1),
        'rev_block_rmse': ('/internal_TIN5_QC/reserved_blocks/window_rmse_m/median', 3, 1),
        'rev_point_coverage': ('/internal_TIN5_QC/reserved_points/valid_record_fraction', 1, 100),
        'rev_block_coverage': ('/internal_TIN5_QC/reserved_blocks/valid_record_fraction', 1, 100),
        'rev_declared_checks': ('/metrology/check_points_declared_for_products', 0, 1)})
    commands = (article/'numeros.tex').read_text()
    for key, (pointer, decimals, scale) in keys.items():
        value = result
        for part in pointer.strip('/').split('/'): value = value[part]
        registry['metrics'][key] = {'value': value, 'decimals': decimals, 'scale': scale,
            'source': fingerprint(out/'resultados.json'), 'json_pointer': pointer, 'classification': 'descritiva',
            'revision_version': '0.3.2-interpretacao'}
        for prefix, en in [('ev', False), ('en', True)]:
            commands += '\n'+r'\expandafter\def\csname '+prefix+'@'+key+r'\endcsname{'+display(value, decimals, en, scale)+'}'
    (article/'numeros.tex').write_text(commands+'\n'); atomic_write_json(article/'dados/numeros_rastreaveis.json', registry)


def condense(text):
    """Condensar redundâncias, preservando fórmulas, limiares e limites novos."""
    replacements = {
        'Foram processados': r'''Foram decodificados \Ev{source_files_qc} arquivos (\Ev{source_tile_pairs} pares MDT/MDS), com CRC conferido. Retornos compartilhados não são observações independentes. Janelas de \Par{window}~m e propriedade única limitaram memória e duplicação. A normalização foi $H=Z_{\mathrm{abs}}-\widehat z_{\mathrm{TIN}}(X,Y)$, com suporte máximo de \Par{tin_radius}~m. O MDT foi usado por procedência/QC, sem interpretar classe8 como terreno LAS padrão nem aplicar nova correção geoidal.''',
        'O CHM candidato': r'''O CHM tomou Hmáx das classes3/4/5, sem suavizar/preencher lacunas. A segmentação do contexto integral precedeu recortes, evitando bordas de janelas como fronteiras de copa. Usaram-se máximos locais e crescimento circular originais do PyCrown~\cite{pycrown}, \textit{commit}3d8db4e, com IO adaptado. Centroides de platô fora do máximo foram realocados ao pixel pertencente mais próximo. Não se executou a correção original de topo por MDS.''',
        'Os \\Par{scenario_count} cenários': r'''Os \Par{scenario_count} cenários variaram resolução, limiar H, raios, algoritmo e retenção MDS50/25\%, uma variável por vez/uma semente; MDT não rarefeito. Em2m, o raio nominal3m corresponde a4m. Cada principal/cenário foi recalculado na interseção observada. Fixaram-se os IDs elegíveis em ambos os lados dos11pares, renormalizando cada receita nesses IDs. Compararam-se: principal/cenário no suporte do par; principal nativo/principal nesse suporte; principal nativo/cenário nesse suporte. Rho/Jaccard não são componentes aditivos; IDs fixos não implicam geometria global fixa. Sem independência estabelecida, não se calcularam IC/$p$~\cite{hurlbert1984}.''',
        'A área observada variou': r'''A fração observada variou de \Ev{observed_fraction_min_percent}\% a \Ev{observed_fraction_max_percent}\% (Tabela~\ref{tab:amostra}). Foram \Ev{units_evaluation} unidades de avaliação, abaixo da meta \Ev{target_evaluation}, e \Ev{units_development} de desenvolvimento. Não houve reposição. As estatísticas representam parcelas elegíveis, não polígonos completos ou o município.''',
        'O efeito depende': r'''Os controles (Tabela~\ref{tab:controles}) mostram dependência da receita. Com $w=0{,}5$, inverter $I_7$ produziu $\rho=\Ev{control_reverse_rho}$ e $J=\Ev{control_reverse_jaccard}$. $I_6$ isolado aproximou-se da combinação; duplicá-lo reproduziu os escores. Número de dimensões e sinal escolhido não estabelecem superioridade.''',
        'As rotinas de copa podem': r'''A segmentação pode dividir/reunir objetos e herdar erros das classes. Máscara sem validação externa, filtros geométricos completos do piloto não executados e percentis ponderados por retornos limitam a interpretação. Dados ausentes, vegetação não detectada e ausência real não são equivalentes. Suporte parcial, seleção intencional e perímetros posteriores à aquisição impedem extrapolação municipal ou causalidade sobre planejamento.''',
        'Nos \\Ev{corridors_evaluation} corredores de avaliação': r'''Nos \Ev{corridors_evaluation} corredores de avaliação, unidades semelhantes em cobertura/fragmentação apresentaram contrastes verticais heterogêneos antes de aplicar pesos. O controle horizontal/corredor atenua sua magnitude. Nos \Ev{comp_fixed} IDs sempre elegíveis, concordância global elevada coexistiu com mudanças nas listas superiores. A pontuação é configuração experimental, sem valência ecológica. Utilidade para diagnóstico/intervenção exige alvo independente; máscara não validada, incerteza altimétrica total não quantificada, caráter pós-resultados e perda de elegibilidade limitam a conclusão.'''
    }
    blocks = text.split('\n\n')
    for prefix, replacement in replacements.items():
        pattern = re.compile('^'+re.escape(prefix), re.M); hits = [i for i, block in enumerate(blocks) if pattern.search(block)]
        if len(hits) != 1: raise ValueError(f'Condensação não unívoca: {prefix}')
        i = hits[0]; match = pattern.search(blocks[i]); blocks[i] = blocks[i][:match.start()]+replacement
    text = '\n\n'.join(blocks)
    for a, b in {'classe8': 'classe 8', 'classes3/4/5': 'classes 3/4/5', r'\textit{commit}3d8db4e': r'\textit{commit} 3d8db4e',
                 'MDS50/25': 'MDS 50/25', 'Em2m': 'Em 2~m', 'nominal3m': 'nominal 3~m', 'a4m': 'a 4~m', 'dos11pares': 'dos 11 pares'}.items(): text = text.replace(a,b)
    return text


def build(project, out):
    original = project/'artigo/complemento_etapa17'; article = project/'artigo/revisao_interpretacao_v0_3_2'
    if article.exists(): raise ValueError('Revisão já criada; não sobrescrever edições humanas')
    shutil.copytree(original, article)
    add_numbers(out, article)
    text = (article/'manuscrito.tex').read_text().replace('complemento analítico pós-resultados 0.3.1', 'revisão interpretativa 0.3.2')
    text = text.replace('A receita operacional foi', 'A configuração experimental de ordenação foi')
    text = text.replace('V_+', r'V_{\mathrm{exp}}')
    before = r'O peso principal foi $w=\Par{primary_weight}$; maiores escores definem ordenação relativa nesta receita, não benefício ecológico universal. Análises longitudinais foram excluídas porque os eixos da nova amostra não foram revalidados.'
    after = r'''O peso principal foi $w=\Par{primary_weight}$. Os sinais $1-R(I_6)$ e $1-R(I_7)$ fazem valores menores elevar o escore por construção. Trata-se de configuração experimental para examinar ordenações, sem interpretação de menor altura/dispersão como degradação, déficit ecológico ou necessidade de intervenção. P95 e IQR descrevem retornos; não são indicadores calibrados de biodiversidade ou qualidade de habitat. Análises longitudinais foram excluídas por falta de eixos revalidados.'''
    if before not in text: raise ValueError('Parágrafo da pontuação não localizado')
    text = text.replace(before, after)
    before = r'A checagem sem reutilização reteve \Ev{comp_disjoint} pares, mediana P95 de \Ev{comp_disjoint_p95}~m (Figura~\ref{fig:pares}).'
    after = r'''A checagem sem reutilização reteve \Ev{comp_disjoint} pares (Figura~\ref{fig:pares}); sua distribuição está na Tabela~\ref{tab:distribuicao}. Há contrastes quase nulos e uma cauda elevada: a complementaridade é heterogênea, não universal.'''
    if before not in text: raise ValueError('Parágrafo dos pares não localizado')
    text = text.replace(before, after)
    table = r'''
\begin{table}[t]
\centering\input{tabelas/distribuicao_pares16.tex}
\caption{Diferenças absolutas (m) nos mesmos \Ev{comp_disjoint} pares. Q1/Q3: quartis por interpolação linear. Descrição de pares dependentes, sem reutilização de IDs.}
\label{tab:distribuicao}
\end{table}
'''
    text = text.replace(r'\subsection{Mudança de ordenação e escolhas operacionais}', table+'\n'+r'\subsection{Mudança de ordenação e escolhas operacionais}')
    paragraph = r'''% EVIDENCIA: C32_U | descritiva | C32_02
O atestado do levantamento2020 declara PEC-PCD ClasseA e \Ev{rev_declared_checks} pontos de controle dos produtos, sem publicar resíduos ou RMSE altimétrico~\cite{atestado2020}. Nas \Ev{rev_point_windows} janelas de avaliação já verificadas por TIN5, o RMSE mediano entre janelas foi \Ev{rev_point_rmse}~m com pontos MDT reservados e \Ev{rev_block_rmse}~m com blocos; as frações válidas foram \Ev{rev_point_coverage}\% e \Ev{rev_block_coverage}\%, respectivamente. Nos blocos, só \Ev{rev_block_valid_windows} janelas tiveram resíduos válidos. São erros internos de interpolação do mesmo sensor, não acurácia externa de H/copa. H depende dos erros de Z e TIN e de sua covariância; máscara, oclusão e seleção dos retornos acrescentam incerteza. Não se demonstrou que as diferenças entre percentis superam o erro total de medição.

'''
    text = text.replace('% EVIDENCIA: C14_D1', paragraph+'% EVIDENCIA: C14_D1')
    text = text.replace('O atestado do levantamento2020 declara PEC-PCD ClasseA', 'O atestado do levantamento de 2020 declara PEC-PCD Classe A')
    text = text.replace('A máscara não validada, o caráter pós-resultados e a perda de elegibilidade limitam a conclusão.', 'A configuração de escores é experimental, sem valência ecológica. Máscara não validada, incerteza altimétrica total não quantificada, caráter pós-resultados e perda de elegibilidade limitam a conclusão.')
    # Associar a ampliação dos pares à nova fonte de distribuição, preservando as anteriores.
    text = text.replace('% EVIDENCIA: C14_R2 | exploratoria | C13_04,C17_01', '% EVIDENCIA: C14_R2 | exploratoria | C13_04,C17_01,C32_01')
    text = text.replace('% EVIDENCIA: C14_M4 | exploratoria | C13_03,C13_05,C13_09', '% EVIDENCIA: C14_M4 | exploratoria | C13_03,C13_05,C13_09,C32_03')
    text = text.replace('% EVIDENCIA: C14_C | exploratoria | C13_03,C17_01,C17_02,C13_06', '% EVIDENCIA: C14_C | exploratoria | C13_03,C17_01,C17_02,C13_06,C32_01,C32_02,C32_03')
    (article/'manuscrito.tex').write_text(condense(text))
    (article/'tabelas/distribuicao_pares16.tex').write_text(r'''\begin{tabular}{lrrrr}
\hline
Diferença & Q1 & Mediana & Q3 & Máximo \\
\hline
$|\Delta P95|$ & \Ev{rev_P95_q25_m} & \Ev{rev_P95_median_m} & \Ev{rev_P95_q75_m} & \Ev{rev_P95_maximum_m} \\
$|\Delta IQR|$ & \Ev{rev_IQR_q25_m} & \Ev{rev_IQR_median_m} & \Ev{rev_IQR_q75_m} & \Ev{rev_IQR_maximum_m} \\
\hline
\end{tabular}
''')
    with (article/'referencias.bib').open('a') as handle:
        handle.write('''\n@misc{atestado2020,
  author = {{Prefeitura do Município de São Paulo}},
  title = {Atestado técnico: levantamentos aéreos realizados em 2020},
  year = {s.d.},
  howpublished = {\\url{'''+ATTESTATION_URL+'''}},
  note = {Contrato 33/2022. Acesso em 30 out. 2026}
}\n''')
    references = read_json(article/'dados/referencias_verificadas.json')
    references['references'].append({'key': 'atestado2020', 'primary_url': ATTESTATION_URL,
        'title': 'Atestado técnico: levantamentos aéreos realizados em2020', 'publication_year_not_stated': True,
        'verified_on': '2026-10-30', 'source_pdf': fingerprint(out/'fontes/atestado_tecnico_2020.pdf')})
    atomic_write_json(article/'dados/referencias_verificadas.json', references)
    shutil.copyfile(out/'resultados.json', article/'dados/revisao_interpretacao_resultados.json')
    (article/'README.md').write_text('''# Revisão interpretativa v0.3.2

Rascunho; mantém as análises v0.3.0/0.3.1, a seleção dos16pares e a pontuação.
Vexp no texto corresponde à receita Vplus histórica. Novidades: orientação
experimental sem valência ecológica, distribuição dos16pares e discussão de
erro apoiada nos metadados e QC TIN5 já existente. Não houve validação externa.

Relatório: docs/revisao_interpretacao_artigo.md na raiz do projeto. A versão
anterior continua em ../complemento_etapa17. Para compilar novamente, usar
scripts/revisar_interpretacao_artigo.py --compile; para auditar, --verify.
Não executar os finalizadores das etapas14–17 sobre esta cópia.

Endereço institucional, equivalência integral ao modelo e aprovação autoral
continuam pendentes. O estilo local está declarado como adaptação. Sem submissão.
''')
    compile_at(project, article, out/'compilacao.txt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze', action='store_true'); parser.add_argument('--build', action='store_true')
    parser.add_argument('--compile', action='store_true'); parser.add_argument('--verify', action='store_true')
    args = parser.parse_args(); project = Path(__file__).resolve().parents[1]
    out = Path(read_json(project/'relatorios/revisao_interpretacao/ultima_execucao.json')['output_root'])
    if args.analyze: print(json.dumps(analyze(project, out), ensure_ascii=False, indent=2))
    if args.build: build(project, out)
    if args.compile: compile_at(project, project/'artigo/revisao_interpretacao_v0_3_2', out/'compilacao.txt')
    if args.verify:
        from verificar_revisao_interpretacao import verify
        print(json.dumps(verify(project, out), ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
