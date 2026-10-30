"""Nova cópia editorial com conferência do extremo e conclusão quantitativa."""
from pathlib import Path
import argparse
import json
import re
import shutil

from sbsr_lidar.storage import read_json,fingerprint,atomic_write_json
from etapa14.build import display
from etapa15.editorial import compile_at


def replace_block(text,prefix,replacement):
    blocks=text.split('\n\n');pattern=re.compile('^'+re.escape(prefix),re.M)
    hits=[i for i,b in enumerate(blocks) if pattern.search(b)]
    if len(hits)!=1:raise ValueError(f'Bloco não encontrado univocamente: {prefix}')
    i=hits[0];start=pattern.search(blocks[i]).start();blocks[i]=blocks[i][:start]+replacement
    return '\n\n'.join(blocks)


def condense_introduction(text):
    text=replace_block(text,'A cobertura de vegetação descreve',r'''Cobertura não determina organização vertical. A fusão LiDAR/espectral foi investigada para discriminar espécies urbanas~\cite{alonzo2014}, mas adicionar atributos não estabelece melhora de diagnóstico.''')
    text=replace_block(text,'Métodos de delineamento identificam',r'''Delineamento por máximos e crescimento de regiões~\cite{dalponte2016,zorner2018} estima segmentos; concordância interna não valida identidade arbórea sem referência independente.''')
    text=text.replace('A contribuição descritiva não será inferida somente da mudança esperada ao adicionar variáveis.', 'Discordância de escores não prova complementaridade.')
    text=text.replace('Esses rótulos não equivalem a conjuntos estatisticamente independentes.', 'Os papéis não asseguram independência.')
    text=text.replace(r'O deslocamento absoluto médio foi de \Ev{primary_mean_absolute_rank_shift} posições. ', '')
    return text


def report(project,out):
    r=read_json(out/'resultados.json');a=r['units'][r['unit_i']];b=r['units'][r['unit_j']]
    def number(value):
        return str(value) if isinstance(value,int) else f'{value:.6f}'.rstrip('0').rstrip('.').replace('.',',')
    table=[]
    for label,key in [('P95 (m)','P95_m'),('IQR (m)','IQR_m'),('Retornos selecionados','n'),
        ('Área observada (m²)','area_observed_m2'),('Fração observada','fraction_observed'),
        ('Cobertura I1','I1'),('Manchas/ha I4','I4'),('Área com flag de incerteza (m²)','uncertain_area_m2'),
        ('Retornos selecionados em pixels incertos','uncertain_pixel_records'),('Manchas censuradas por contexto','n_context_censored'),
        ('Manchas censuradas por suporte','n_support_censored'),('Registros ≥P95','records_at_or_above_P95'),
        ('Células de1m com registros ≥P95','one_metre_cells_at_or_above_P95')]:
        table.append(f'| {label} | {number(a[key])} | {number(b[key])} |')
    v=r['density25_selection'];inf=r['influence'];t=r['normalization_replay']
    text=f'''# Revisão do par máximo e da conclusão quantitativa

Os três pontos solicitados foram examinados sem alterar os pares, escores,
coortes ou cenários principais. O extremo continua no conjunto de16pares.
A investigação específica dele e a exclusão diagnóstica são pós-resultados.

## Par com diferença máxima de P95

Corredor **{r['corridor_id']}**. IDs completos:

- Unidade1: `{r['unit_i']}`.
- Unidade2: `{r['unit_j']}`.

Os centroides estão a{r['centroid_distance_m']:.2f}m; mesmo corredor não significa
mesma vizinhança imediata. A diferença de cobertura é
{100*r['original_cover_difference']:.3f}pontos percentuais; a diferença de
R(I4)={r['original_fragmentation_rank_difference']:.6f}; razão de áreas observadas
{r['original_observed_area_ratio']:.4f}. Satisfazem os limites principais de
0,05,0,10 e2, respectivamente. Não são equivalência estatística/ecológica.

| Evidência | Unidade1 | Unidade2 |
|---|---:|---:|
{chr(10).join(table)}

Percentis lineares recalculados a partir dos retornos normalizados, com a
mesma observação, máscara e propriedade de unidade em bordas. Diferença
**{r['absolute_P95_difference_m']:.8f}m**, arredondada20,91m. As contagens1110/310 e
P95/IQR coincidem com a coorte congelada dentro de1e−9m. Registros de origem
(folha/índice) são únicos; H=Zabsoluto−TIN coincide exatamente, sem dupla
normalização. As classes candidatas são{a['candidate_classes']} na unidade1
e{b['candidate_classes']} na2; isso não valida a classificação do produtor.

Na unidade alta,56registros em10células de1m estão em/acima do P95. Há um
agrupamento alto nos perfis, além de retornos inferiores; o percentil não
decorre de um único registro máximo. O padrão espacial não foi identificado
como copa verdadeira por referência externa. Padrões lineares nos retornos
também não autorizam, por inspeção do próprio LiDAR, reclassificação segura.

### Reprodução localizada do terreno

Foram reconstituídas somente as duas janelas pertinentes a partir dos blocos
MDT já decodificados, sem nova decodificação LAZ, processamento PyCrown ou
escrita nos caches originais:

| Janela200m | Vértices MDT | Retornos verificados | Maior diferença de terreno (m) | Maior distância ao MDT (m) |
|---|---:|---:|---:|---:|
'''
    for row in t:text+=f'| {row["wx"]}/{row["wy"]} | {row["unique_ground_vertices"]} | {row["selected_records_checked"]} | {row["max_terrain_difference_m"]:.9f} | {row["max_nearest_MDT_distance_m"]:.3f} |\n'
    text+=f'''
O terreno foi reproduzido exatamente nos {sum(x['selected_records_checked'] for x in t)} retornos selecionados. Isso é
controle interno da interpolação e da fórmula, não acurácia absoluta.

### Flags, bordas e recortes diagnósticos

Ambas as unidades têm observação integral. Existem5m²/2m² com flag de classe1
alta na unidade, mas **nenhum dos retornos selecionados** cai nesses pixels.
Excluí-los, portanto, não altera os percentis. Essa tela só detecta a condição
específica de classe1 alta e não certifica ausência de outros erros de classe.

A unidade alta intersecta duas manchas que tocam o limite do contexto e
suporte inválido em algum ponto. A censura é atributo da mancha no contexto,
não prova de que os próprios retornos selecionados careçam de terreno. Todas
as alturas selecionadas têm status válido. `contribuicao_manchas.csv` permite
ver os componentes que sustentam cada percentil.

No interior da unidade, a1m da borda, permaneceram{a['interior_1m']['n']} e
{b['interior_1m']['n']}registros, com P95={a['interior_1m']['P95_m']:.3f}m e
{b['interior_1m']['P95_m']:.3f}m. Esse recorte não é nova máscara nem estimativa
de acurácia; apenas mostra que o contraste alto/baixo não se restringe à
atribuição exata dos pontos sobre a fronteira.

O diagnóstico espacial e as distribuições estão em
`diagnostico_par_maximo.pdf/.svg/.png`; os retornos completos das unidades
estão em dois Parquet e os polígonos em `unidades_par_maximo.gpkg`.

### Influência do extremo nas medianas

| Conjunto | Mediana original(m) | Sem apenas o par máximo(m) | Pares originais/remanescentes |
|---|---:|---:|---:|
| Sem reutilização deIDs | {inf['disjoint16']['median_abs_P95_original_m']:.3f} | {inf['disjoint16']['median_abs_P95_without_max_pair_m']:.3f} |16/15 |
| Pareamento principal | {inf['matched25']['median_abs_P95_original_m']:.3f} | {inf['matched25']['median_abs_P95_without_max_pair_m']:.3f} |25/24 |

O máximo influencia a magnitude, mas não cria sozinho a diferença mediana.
Ambos os recortes continuam descritivos e dependentes; não são testes de
significância ou justificativa para selecionar somente pares favoráveis.
As estatísticas principais dos16/25pares foram preservadas.

## Por que medir estabilidade das listas superiores

Spearman resume a ordenação inteira; a permanência no conjunto definido por
um corte é outro estimando. Deslocamentos próximos ao corte podem substituir
unidades sem reduzir muito a correlação global. O experimento investiga a
reprodutibilidade da identificação de unidades sob escolhas de processamento,
não o acerto de uma prioridade ecológica externa.

Na coorte fixa de68IDs, cada lista superior tem14unidades. Na retenção MDS25%,
rho={v['spearman_rho']:.6f}, mas apenas{v['shared_n']}unidades são compartilhadas:
**{v['lost_n']}saem e{v['gained_n']}entram**, substituição de{100*v['replacement_fraction']:.2f}% por lista.
J={v['jaccard']:.6f} é interseção/união=10/18; não significa44,44% de unidades
substituídas. A fração substituída é4/14=28,57%. As listas foram reconstruídas
pelos IDs/ranks, e não inferidas apenas de Jaccard. Todos os11cenários
substituem de{r['top_replacements_min']} a{r['top_replacements_max']}unidades por lista.

Isso delimita a força de uma conclusão baseada somente em rho: a concordância
global pode ser elevada enquanto a identificação de quais unidades pertencem
ao conjunto selecionado permanece sensível. Em um desenho que seleciona
unidades por um corte, é necessário relatar a permanência e os critérios desse
corte para avaliar reprodutibilidade. Aqui, o top20% e os sinais dos escores
continuam escolhas experimentais, sem equivalência a prioridades reais.

`permanencia_selecoes.csv` e `membros_selecoes.json` contêm as onze comparações,
interseções, perdas, entradas e IDs. O universo fixo não representa os46IDs
que não permaneceram elegíveis, nem implica geometria observada global fixa.

## Manuscrito

A discussão inclui a conferência do máximo e o exemplo rho alto/listas
distintas. A conclusão destaca25pares controlados,16pares sem reutilização,
medianas2,40/2,80m, coorte fixa68, faixas rho/J e substituição de1–4 em14IDs.
Semântica, acurácia externa, amostra intencional e análise pós-resultados
continuam limites explícitos. A revisão não aprova ou submete o artigo.

## Reprodução

Os cálculos e fontes estão registrados na execução desta revisão. Para
conferir a entrega e testar as regras de seleção:

```bash
.venv-cientifico/bin/python scripts/verificar_revisao_final_quantitativa.py
.venv-cientifico/bin/python -m pytest tests/cientifico/test_pair_review.py -q
```
'''
    from revisar_interpretacao_artigo import readable_prose
    text=readable_prose(text)
    # Ajustes de apresentação somente; os valores completos ficam no JSON.
    prose,commands=text.rsplit('## Reprodução\n',1)
    text=re.sub(r'(?<=\d)\.(?=\d)',',',prose)+'## Reprodução\n'+commands
    for old,new in {
        'Unidade1':'Unidade 1','Unidade2':'Unidade 2','a547':'a 547',
        'e2,':'e 2,','arredondada20':'arredondada 20','contagens1110':'contagens 1110',
        'são{':'são {','unidade1':'unidade 1','na2':'na 2','e{':'e {',
        'alta,56':'alta, 56','56registros':'56 registros','10células':'10 células',
        'Existem5':'Existem 5','classe1':'classe 1',
        'a1 m':'a 1 m','144registros':'144 registros','original(m)':'original (m)',
        'máximo(m)':'máximo (m)','deIDs':'de IDs','|16/15':'| 16/15',
        '|25/24':'| 25/24','tem14unidades':'tem 14 unidades','MDS25%':'MDS 25%',
        'apenas10unidades':'apenas 10 unidades','4saem':'4 saem','e4entram':'e 4 entram',
        'significa44':'significa 44','é4/14':'é 4/14','os11cenários':'os 11 cenários',
        'a4unidades':'a 4 unidades','permaneceram302':'permaneceram 302',
        'Janela200':'Janela de 200','5m²/2m²':'5 m²/2 m²',
        '0,05,0,10 e 2':'0,05; 0,10; e 2','controlados,16':'controlados, 16',
        'reprodutibilidade da identificação':'robustez da identificação',
        'avaliar reprodutibilidade':'avaliar robustez','top20%':'corte de 20%',
        'os46 IDs':'os 46 IDs','destaca25':'destaca 25','medianas2':'medianas 2',
        'fixa68':'fixa 68','14 IDs':'14 IDs',
    }.items():text=text.replace(old,new)
    (project/'docs/revisao_final_quantitativa.md').write_text(text)


def build(project,out):
    prior=project/'artigo/revisao_interpretacao_v0_3_2';article=project/'artigo/revisao_final_v0_3_3'
    if article.exists():raise ValueError('Nova cópia já existe; não sobrescrever revisão humana')
    shutil.copytree(prior,article)
    r=read_json(out/'resultados.json');registry=read_json(article/'dados/numeros_rastreaveis.json')
    a=r['units'][r['unit_i']];b=r['units'][r['unit_j']]
    metrics={
        'fin_high_P95':(a['P95_m'],f'/units/{r["unit_i"]}/P95_m',2,1),
        'fin_low_P95':(b['P95_m'],f'/units/{r["unit_j"]}/P95_m',2,1),
        'fin_high_n':(a['n'],f'/units/{r["unit_i"]}/n',0,1),
        'fin_low_n':(b['n'],f'/units/{r["unit_j"]}/n',0,1),
        'fin_tail_n':(a['records_at_or_above_P95'],f'/units/{r["unit_i"]}/records_at_or_above_P95',0,1),
        'fin_tail_cells':(a['one_metre_cells_at_or_above_P95'],f'/units/{r["unit_i"]}/one_metre_cells_at_or_above_P95',0,1),
        'fin_without_max_median':(r['influence']['disjoint16']['median_abs_P95_without_max_pair_m'],'/influence/disjoint16/median_abs_P95_without_max_pair_m',2,1),
        'fin_without_max_n':(r['influence']['disjoint16']['n_without_max_pair'],'/influence/disjoint16/n_without_max_pair',0,1),
        'fin_rho25':(r['density25_selection']['spearman_rho'],'/density25_selection/spearman_rho',3,1),
        'fin_shared25':(r['density25_selection']['shared_n'],'/density25_selection/shared_n',0,1),
        'fin_replaced25':(r['density25_selection']['lost_n'],'/density25_selection/lost_n',0,1),
        'fin_replaced_pct25':(r['density25_selection']['replacement_fraction'],'/density25_selection/replacement_fraction',1,100),
        'fin_min_replaced':(r['top_replacements_min'],'/top_replacements_min',0,1),
        'fin_max_replaced':(r['top_replacements_max'],'/top_replacements_max',0,1)}
    commands=(article/'numeros.tex').read_text()
    for key,(value,pointer,decimals,scale) in metrics.items():
        registry['metrics'][key]={'value':value,'json_pointer':pointer,'decimals':decimals,'scale':scale,
            'source':fingerprint(out/'resultados.json'),'classification':'descritiva','revision':'0.3.3-revisao-quantitativa'}
        for prefix,english in [('ev',False),('en',True)]:
            commands+='\n'+r'\expandafter\def\csname '+prefix+'@'+key+r'\endcsname{'+display(value,decimals,english,scale)+'}'
    (article/'numeros.tex').write_text(commands+'\n');atomic_write_json(article/'dados/numeros_rastreaveis.json',registry)
    shutil.copyfile(out/'resultados.json',article/'dados/revisao_final_quantitativa.json')
    text=(article/'manuscrito.tex').read_text().replace('revisão interpretativa 0.3.2','revisão quantitativa 0.3.3')
    text=replace_block(text,'% EVIDENCIA: C14_R2',r'''% EVIDENCIA: C14_R2 | exploratoria | C13_04,C17_01,C32_01
Os \Ev{similar_cover_pairs} pares de cobertura semelhante tinham diferença mediana de P95 de \Ev{pairs_absolute_P95_difference_m_median}~m. Controlando também fragmentação e corredor, restaram \Ev{comp_pairs} pares/\Ev{comp_units} unidades, com medianas de \Ev{comp_p95}~m para P95 e \Ev{comp_iqr}~m para IQR. Nos \Ev{comp_disjoint} pares sem reutilização, a mediana de P95 foi \Ev{comp_disjoint_p95}~m (Figura~\ref{fig:pares}, Tabela~\ref{tab:distribuicao}). A complementaridade é heterogênea e antecede os pesos, sem demonstrar ganho ecológico ou diferenças superiores ao erro total. A Figura~\ref{fig:mapa} ilustra o suporte.''')
    marker=r'\subsection{Mudança de ordenação e escolhas operacionais}'
    extra=r'''% EVIDENCIA: C33_P | descritiva | C33_01,C33_03
O máximo de \Ev{rev_P95_maximum_m}~m foi reproduzido: P95 de \Ev{fin_high_P95}/\Ev{fin_low_P95}~m, com \Ev{fin_high_n}/\Ev{fin_low_n} retornos candidatos. A cauda superior alta abrange \Ev{fin_tail_n} registros em \Ev{fin_tail_cells} células de1m. O TIN reproduzido confirmou consistência interna, sem validar classes/copas. Sem esse par, os \Ev{fin_without_max_n} remanescentes mantiveram mediana de \Ev{fin_without_max_median}~m; o conjunto principal não foi alterado.

'''
    text=text.replace(marker,extra+marker)
    text=replace_block(text,'% EVIDENCIA: C14_R5',r'''% EVIDENCIA: C14_R5 | parcialmente_sustentada | C13_05,C17_02,C33_02
Permaneceram \Ev{sensitivity_paired_eligible_units_min}--\Ev{sensitivity_paired_eligible_units_max} IDs por comparação; \Ev{comp_fixed}/\Ev{units_evaluation} foram elegíveis em todas. Nessa coorte fixa, $\rho$=\Ev{comp_rhomin}--\Ev{comp_rhomax} e $J$=\Ev{comp_jmin}--\Ev{comp_jmax}, com $k=\Ev{comp_k}$ (Figura~\ref{fig:sens}). O contraste de suporte teve $\rho$ mínimo de \Ev{comp_support_rhomin} e listas coincidentes. Na retenção MDS25\%, $\rho=\Ev{fin_rho25}$ coexistiu com apenas \Ev{fin_shared25} unidades compartilhadas: \Ev{fin_replaced25} saíram e \Ev{fin_replaced25} entraram, substituição de \Ev{fin_replaced_pct25}\% por lista. Rho descreve a ordem global; a permanência no corte qualifica a robustez da identificação das unidades selecionadas. Não se trata de prioridade ecológica validada. Nesse cenário perderam-se \Ev{comp_worst_excluded} IDs: \Ev{comp_worst_observation} por observação insuficiente e \Ev{comp_worst_other} por outros critérios. Não extrapolar a estabilidade dos sobreviventes aos excluídos.''')
    text=replace_block(text,'% EVIDENCIA: C14_C',r'''% EVIDENCIA: C14_C | exploratoria | C17_01,C17_02,C32_01,C32_02,C32_03,C33_01,C33_02,C13_06
Após controlar cobertura, fragmentação e corredor, persistiram contrastes verticais: os \Ev{comp_pairs} pares/\Ev{comp_units} unidades apresentaram diferença mediana de P95 de \Ev{comp_p95}~m; nos \Ev{comp_disjoint} pares sem reutilização, foi \Ev{comp_disjoint_p95}~m. Esses contrastes antecedem a ponderação e sustentam complementaridade descritiva do LiDAR nesses limites operacionais de semelhança2D. Nos \Ev{comp_fixed} IDs sempre elegíveis, $\rho$=\Ev{comp_rhomin}--\Ev{comp_rhomax} coexistiu com $J$=\Ev{comp_jmin}--\Ev{comp_jmax} e substituição de \Ev{fin_min_replaced}--\Ev{fin_max_replaced} das \Ev{comp_k} unidades das listas superiores. Portanto, correlação global elevada não assegura manutenção das unidades selecionadas: estabilidade da seleção deve ser verificada separadamente para qualificar a robustez da identificação. A pontuação é experimental, sem valência ecológica. Amostra intencional, análise pós-resultados, incerteza altimétrica total não quantificada e máscara sem validação externa impedem concluir acurácia, melhora de diagnóstico ou prioridade real.''')
    text=text.replace('células de1m','células de 1~m').replace('MDS25','MDS 25').replace('semelhança2D','semelhança 2D')
    (article/'manuscrito.tex').write_text(condense_introduction(text))
    (article/'README.md').write_text('''# Revisão quantitativa v0.3.3

Rascunho para revisão do autor. Artigo anterior preservado em
../revisao_interpretacao_v0_3_2. Escores, coortes, figuras e tabelas principais
mantidos; máximo de20,91m reconstituído dos retornos e TIN de duas janelas.
A conferência é interna e não valida copas/alturas externamente.

Discussão das listas superiores e conclusão ampliadas com números rastreáveis.
Relatório: docs/revisao_final_quantitativa.md na raiz do projeto. Diagnóstico
completo, figuras e retornos estão na execução apontada por
relatorios/revisao_final_quantitativa/ultima_execucao.json.

Compilar: scripts/revisar_conclusao_quantitativa.py --compile.
Auditar: scripts/verificar_revisao_final_quantitativa.py.
Não executar finalizadores das versões anteriores sobre esta cópia.
Pendências: endereço institucional, equivalência integral ao modelo e aprovação
do autor. Sem submissão. O estilo local permanece declarado como adaptação.
''')
    compile_at(project,article,out/'compilacao.txt')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');parser.add_argument('--compile',action='store_true')
    args=parser.parse_args();project=Path(__file__).resolve().parents[1]
    out=Path(read_json(project/'relatorios/revisao_final_quantitativa/ultima_execucao.json')['output_root'])
    report(project,out)
    if args.build:build(project,out)
    if args.compile:compile_at(project,project/'artigo/revisao_final_v0_3_3',out/'compilacao.txt')
