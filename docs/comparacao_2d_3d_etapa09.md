# Etapa 09 — comparação exploratória 2D/3D

Implementada e executada em **25/10/2026**, nos dois casos do piloto, com os
indicadores congelados da etapa 08. Foram produzidos universos de análise,
descrições físicas, correlações, ablações, escores, rankings, listas superiores,
deslocamentos, mapas de desacordos e pareamentos de cobertura semelhante.

O resultado principal de 50 m é **A versus A+3D em 58 unidades com copa do
CO_BT_01_E**: Spearman **0,8734**; os conjuntos dos 20% superiores compartilham
**8 de 12 unidades**, Jaccard exato **0,50**. Incluindo todo o empate no corte,
o Jaccard é **0,5625**. Isso descreve mudança de ordenação sob a fórmula adotada,
sem demonstrar ganho de acurácia ou benefício ecológico.

**B/C permanecem indisponíveis** pela falta de eixo/suporte longitudinal. No
adverso, duas unidades de 50 m e escores A empatados não sustentam comparação
substantiva. Nenhum alvo independente, p-valor, treinamento ou validação da
máscara foi inventado. A etapa 10 não foi iniciada.

## Execuções e entregas

| Caso | Execução | Fonte da etapa 08 |
|---|---|---|
| Principal | `20261025T223954Z_8963243109` | `20261025T221430Z_ad89ab6173` |
| Adverso | `20261025T224013Z_39ef25675a` | `20261025T221433Z_a9f46ac6fe` |

Produtos em `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa09/`,
em subdiretórios `<case>/<run_id>/`. Cada execução contém:

| Arquivo-base, em Parquet e CSV | Conteúdo |
|---|---|
| `universo_unidades` | Todas as unidades fonte, métricas originais, geometria e papel/exclusão na comparação |
| `universos_comparacao` | Contagens/áreas por caso, família e escala, com perdas de suporte |
| `disponibilidade_metodos` | Disponibilidade de A, A+3D, B e C e motivos de insuficiência |
| `estatisticas_indicadores` | Mínimo, quartis, mediana, máximo e n finito; descritores antes dos escores |
| `correlacoes_indicadores` | Spearman descritivo de I1/I4/I5/I6/I7 no universo pareado |
| `normalizadores` | Universo de ajuste, n, extremos, constância e método de postos |
| `escores_rankings` | Escores, componentes normalizados, postos médios e ordem operacional |
| `concordancia_ablacao` | Concordância A/A+3D por peso/orientação/escopo/top 10/20/30% |
| `membros_top` | Pertinência de cada unidade às listas exatas e inclusivas dos empates |
| `deslocamentos` | Mudança por unidade, em posto médio e ordem operacional |
| `pares_cobertura_semelhante` | Pareamentos H1 com áreas comparáveis, diferenças de P95/IQR e distância espacial |
| `controles` | Ablações determinísticas e motivos de não executar permutações/modelos preditivos |
| `desacordos_espaciais` | Geometrias originais e entrada/saída das listas no cenário principal |

`universo_unidades` e `desacordos_espaciais` são GeoParquet EPSG:31983; seus CSVs
levam WKT. `metodologia_escores.json` registra fórmulas, parâmetros e limites.
Cópia local: [`metodologia_comparacao_etapa09.json`](metodologia_comparacao_etapa09.json).

Relatórios/manifestos/logs ficam em `relatorios/execucoes/<run_id>/`, com
referências curtas em `relatorios/etapa09/execucao_{main,adversarial}.json`.
Todas as tabelas recebem `source_indicator_run_id` e `comparison_run_id`.
O universo preserva as 426 linhas fonte; os milhares de registros de cenários
não são milhares de observações independentes.

## Universo comum, perdas e estratos

Cada comparação usa a mesma máscara **baseline_h3**, V observado, geometria,
resolução e regras de elegibilidade das etapas anteriores. O universo é definido
antes dos escores por `eligible_A_plus_3D`, sem escolher casos pela vantagem de C.
Famílias, escalas e casos são separados; nenhuma normalização é transferida entre eles.

A referência A é **bidimensional, mas também deriva da máscara LiDAR**, inclusive
do limiar de H usado para definir copa candidata. A comparação acrescenta
descritores verticais à mesma representação de copa; não é uma comparação entre
sensores independentes. Essa máscara não é usada como verdade para medir acurácia.

| Caso/grade | Escala | Total | Pareado com copa | Estrato sem copa detectada | Só descritores A | Excluídas |
|---|---:|---:|---:|---:|---:|---:|
| Principal | 25 m | 192 | 150 | 2 | 9 | 31 |
| Principal | 50 m | 67 | 58 | 1 | 0 | 8 |
| Principal | 100 m | 27 | 25 | 0 | 0 | 2 |
| Adverso | 25 m | 59 | 5 | 2 | 4 | 48 |
| Adverso | 50 m | 25 | 2 | 0 | 1 | 22 |
| Adverso | 100 m | 10 | 0 | 0 | 0 | 10 |

Unidades elegíveis para A com copa e altura insuficiente continuam com seus
descritores físicos e motivo de exclusão. Elas não entram apenas em A na tabela
pareada, pois isso alteraria o universo entre métodos. As 46 unidades longitudinais
do adverso ficam explicitamente excluídas da comparação B/C: nenhum segmento
atende ao suporte longitudinal. Não se projetam lacunas sobre a grade.

Na grade de 50 m, o universo pareado cobre **62.359,855 m² observados** do
principal e **1.187,216 m²** do adverso. O estrato comum sem copa detectada
adiciona **54,599 m²** no principal. O domínio A elegível soma 62.414,453 m²
observados no principal e 1.301,617 m² no adverso. Portanto, o suporte adicional
de A no adverso não é apresentado como se estivesse na comparação pareada.
Áreas e motivos por unidade permanecem disponíveis, sem omitir os vazios.

Há dois escopos de lista, sempre identificados:

- `conditional_canopy`: somente unidades pareadas com copa, n=58 no principal/50 m;
- `joint_strata`: acrescenta a mesma classe superior de ausência detectada aos
  dois métodos, n=59 nesse caso, sem atribuir altura ou escore à classe.

A classe sem copa detectada é empatada internamente e ordenada por ID apenas
para operação. Não recebe uma segunda penalização por altura zero. Ausência
detectada continua condicionada à máscara não validada; flags de classificação
incerta são preservadas, sem alegar ausência comprovada em campo.

## Indicadores separados e redundância

As distribuições físicas são expostas antes da agregação. Não se introduz
cobertura e seu complemento como duas variáveis de evidência: o complemento
é apenas orientação do mesmo indicador. I5 permanece auxiliar, conforme a
decisão anterior à comparação, sem selecioná-lo para maximizar mudança de ranking.

No principal/50 m, no mesmo universo de 58 unidades:

| Variáveis | Spearman descritivo |
|---|---:|
| I1 × I4 | −0,3672 |
| I1 × I6 | 0,6640 |
| I1 × I7 | 0,5698 |
| I5 × I6 | 0,9297 |
| I6 × I7 | 0,8908 |

Há redundância elevada entre média/P95 e entre os dois descritores verticais.
Assim, I5 não ganha peso adicional junto de I6. A ablação somente I6 examina
o efeito de incluir I7. Essas correlações não certificam independência de erros,
validade ecológica, causalidade ou poder preditivo.

## Fórmulas e controles predefinidos

Para o mesmo universo pareado, `R(x)=(posto_médio−0,5)/n`. Variável constante
recebe R=0,5, sem criar diferenças artificiais. Não há imputação de altura ou
ajuste de normalização usando um alvo externo inexistente. A transformação é
descritiva do próprio universo; não é normalizador treinado para previsão.

```text
D_cov = 1 − R(I1)
D_frag = R(I4)
S_A = (D_cov + D_frag)/2

D_gap = (R(I2) + R(I3_local/L_observável))/2
S_B = (S_A + D_gap)/2                 [somente se B estiver disponível]

V+ = (1 − R(I6) + 1 − R(I7))/2
V− = (1 − R(I6) + R(I7))/2
S_C = (1−w) S_B + w V                [somente se B/C estiverem disponíveis]
S_A+3D = (1−w) S_A + w V             [ablação executada em grade]
```

A+3D não é renomeado C. As fórmulas de B/C foram implementadas e testadas
analiticamente, mas o piloto não dispõe dos indicadores longitudinais necessários.

O cenário principal é **w=0,5, V+**, fixado no protocolo. Executaram-se pesos
**0/0,25/0,5/0,75**, V+/V− e altura isolada, sem otimização pelo ranking mais
favorável. V− inverte somente a orientação de I7: não há direção ecológica
universal verificada para heterogeneidade. Maior altura tampouco é recomendação
universal de planejamento; a direção usada é uma escolha de contraste relativo.

O controle de altura duplicada usa `V=(D_altura+D_altura)/2` e reproduz
exatamente altura isolada. Peso vertical zero reproduz A. São controles
**determinísticos de fórmula**, não distribuições nulas estatísticas. Existem
17 variantes por universo disponível: A e 16 combinações de ablação/controle.
As duas orientações e todos os pesos permanecem nos arquivos, sem seleção posterior.

## Rankings, empates e listas superiores

Escores são arredondados a **12 casas decimais somente para empates numéricos**;
indicadores físicos e escores brutos permanecem armazenados. Postos médios são
usados para concordância. A ordem operacional desempata por `unit_id` estável.

Listas de 10/20/30% usam **k=ceil(q·n)** nos dois métodos, com cardinalidade
igual. Registram-se o grupo empatado no corte e uma segunda lista que inclui
todo esse empate. Não se confunde lista operacional de k com classificação
substantivamente resolvida entre unidades empatadas.

Jaccard é null quando **k<5**, inclusive quando a lista inclusiva dos empates
fica maior. Spearman é null com n<3 ou variável constante. Os mínimos são
guardas de relato descritivo, não cálculo de poder. Não se calculam p-valores.
Não se compara Jaccard diretamente entre IDs de 25 e 100 m; as análises são
dentro de cada escala, com correspondências espaciais da etapa 07 disponíveis
para eventual comparação posterior sobre suporte comum.

Resultado principal A/A+3D, escopo `conditional_canopy`, top 20%:

| Caso/escala | n | k | Spearman | Jaccard exato | Jaccard com empate completo |
|---|---:|---:|---:|---:|---:|
| Principal/25 m | 150 | 30 | 0,8729 | 0,5385 | 0,5385 |
| Principal/50 m | 58 | 12 | 0,8734 | 0,5000 | 0,5625 |
| Principal/100 m | 25 | 5 | 0,8557 | 0,6667 | 0,6667 |
| Adverso/25 m | 5 | 1 | Indefinido: A constante | Não reportado: k<5 | Não reportado |
| Adverso/50 m | 2 | 1 | Não reportado: n<3 | Não reportado: k<5 | Não reportado |

No principal/50 m, oito unidades permanecem em ambas as listas de 12, quatro
saem e quatro entram. O deslocamento absoluto médio de posto é **6,7586**,
máximo **19**. O corte de A+3D divide um empate de duas unidades; incluir ambas
aumenta sua lista para 13 e altera o Jaccard. Isso é parte do resultado, não
um detalhe removido para favorecer concordância ou discordância.

No escopo `joint_strata` do mesmo caso, n=59 e k=12 incluem a ausência detectada
comum. Spearman é 0,8797; Jaccard exato 0,4118 e inclusivo 0,4706. O universo
e a quota de unidades com copa são diferentes: esses números são reportados
separadamente, sem substituí-los pelos do escopo condicional.

No adverso, o escore A ficou constante nos universos de 25 e 50 m. A lista
operacional depende fortemente do desempate por ID; não representa discriminação
confirmada de prioridades. Em 50 m, não mudar postos empatados não é prova de
equivalência científica ou de baixo valor do 3D na população municipal.

## Pesos, orientação e dimensionalidade

No principal/50 m, mantendo as mesmas 58 unidades:

| Vertical | Peso | Spearman com A | Jaccard top 20% |
|---|---:|---:|---:|
| I6+I7, V+ | 0 | 1,0000 | 1,0000 |
| I6+I7, V+ | 0,25 | 0,9744 | 0,8462 |
| I6+I7, V+ | 0,50 | 0,8734 | 0,5000 |
| I6+I7, V+ | 0,75 | 0,7733 | 0,4118 |
| I6+I7, V− | 0,50 | 0,9795 | 0,8462 |
| Somente I6 | 0,50 | 0,8975 | 0,5000 |
| I6 duplicado | 0,50 | 0,8975 | 0,5000 |

A mudança depende de peso/orientação, e a elevada correlação I6/I7 limita a
interpretação de duas dimensões independentes. O controle duplicado confirma
que repetir a mesma informação, mantendo a média do grupo, não cria incremento.
Não substitui um controle estatístico de variáveis adicionais sob um desenho
espacial permutável. Nenhum peso/sinal foi escolhido como vencedor após a análise.

## H1: alturas sob cobertura semelhante

Pareiam-se somente unidades da mesma coorte, com diferença de I1≤0,05 e razão
entre áreas observadas≤2. A tolerância numérica de fronteira é 10⁻¹², sem
arredondar as observações para produzir mais pares. Registram-se IDs, valores,
diferenças de P95/IQR, distância entre centroides e contato entre unidades.

| Caso/escala | Pares | Unidades únicas nos pares | Mediana da diferença absoluta de P95 | Máximo da diferença absoluta de P95 |
|---|---:|---:|---:|---:|
| Principal/25 m | 649 | 146 | 3,4062 m | 14,0298 m |
| Principal/50 m | 76 | 50 | 2,7304 m | 10,9850 m |
| Principal/100 m | 13 | 15 | 5,9012 m | 8,1944 m |
| Adverso/25 m | 1 | 2 | 8,0572 m | 8,0572 m |
| Adverso/50 m | 0 | 0 | Indefinida | Indefinido |

No principal/50 m, a mediana de diferença absoluta de IQR é **1,2818 m**.
Os 76 pares reutilizam 50 unidades e compartilham estrutura espacial. Não são
76 réplicas independentes. Os critérios controlam cobertura e área observada,
sem alegar igualdade de todos os demais descritores 2D, causalidade ou melhoria
ecológica. O resultado documenta variação vertical sob cobertura semelhante.

## Referência externa, blocos e inferência

A referência foi reavaliada: **100 tarefas pendentes, zero rótulos humanos
concluídos e nenhum alvo independente de prioridade**. Não houve treinamento,
teste preditivo ou ganho de acurácia alegado. Os dois casos já foram examinados
em QC; não são apresentados como teste externo intocado.

Cada caso pertence a um único grupo de corredores reservado na etapa 05:
principal `G05_4fb63a28d01c69`, adverso `G05_9ec0ce7d48680d`. O principal tem
13 células diagnósticas de 200 m com unidades pareadas em cada escala, mas
isso não demonstra 13 blocos independentes ou permutáveis. O adverso tem ainda
menos suporte. A guarda operacional exige ao menos seis grupos independentes,
e mesmo essa contagem não dispensaria justificar a permutabilidade no desenho.

Assim, permutações/substitutas espaciais e p-valores **não foram executados**.
Ablações de peso, orientação e duplicação foram executadas como controles
determinísticos. A limitação estatística permanece explícita para o desenho
da amostra científica futura; não é ocultada tratando pixels, pares ou cenários
como novas observações independentes.

A interpretação admissível é: os retornos contêm variação vertical dentro dos
critérios de cobertura semelhante e a inclusão de descritores verticais muda
rankings conforme pesos/sinais. Sem alvo externo e validação da máscara, não
se demonstra método vencedor, diagnóstico melhor, causalidade, biomassa,
conectividade funcional ou prioridade real de intervenção. H3 permanece não testada.

## Verificações, custo e reprodução

Passaram **154 testes científicos** (20 novos), **25 testes do downloader com
dois subtestes** e **49 verificações dos produtos reais**. Sete avisos de
depreciação Rasterio/Affine vêm dos testes de IO existentes.

Os testes novos cobrem fórmulas A/B/C, normalização por postos, constantes,
equivalência com peso zero, duplicação, orientação de I7, empates/ID, cardinalidade,
listas pequenas, ausência sem altura fictícia, universo fixo, exclusões, pares,
limites de recursos, IO, cache e recusa de fonte alterada. A auditoria real
recalcula fórmulas/postos/listas, pesos, correlações, descrições físicas, todos
os pares admissíveis, Jaccard exato/inclusivo, deslocamentos e geometrias fonte.

Tempo/RSS observados em processos separados: principal **6,05 s / 301,91 MiB**;
adverso **1,28 s / 253,15 MiB**. Os tempos instrumentados não incluem todo o
custo de hash/pré-verificação e não predizem o custo municipal. Cache comprovado
nos dois casos, sem alterar produtos congelados ou anotações.

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml compare --case main
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml compare --case adversarial
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa09.py
```

`--no-cache` cria nova execução. O cache inclui fonte, ancestralidade, estado
atual das referências, configuração, código e ambiente; valida produtos por
hash. Mudança em indicador congelado ou ancestral provoca recusa. O protocolo
continua 0.1.0, com parâmetros aditivos registrados nesta etapa, sem pré-registro
retroativo ou otimização pelo desfecho.

```bash
.venv-cientifico/bin/python scripts/visualizar_comparacao_etapa09.py CAMINHO/comparacao.json --output-dir relatorios/etapa09
```

Figuras inspecionadas:
[rankings principal](../relatorios/etapa09/rankings_50m_main.png),
[descritores/ablações principal](../relatorios/etapa09/altura_pesos_50m_main.png),
[rankings adverso](../relatorios/etapa09/rankings_50m_adversarial.png),
[descritores/ablações adverso](../relatorios/etapa09/altura_pesos_50m_adversarial.png).

APIs primárias consultadas:
[SciPy rankdata](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rankdata.html)
e [definição de Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html).
O código calcula a correlação dos postos sem produzir p-valores.

Etapa 09 concluída no alcance **descritivo/exploratório com dependências
científicas explícitas**. Próxima: **10 — sensibilidade e validação**, somente
quando acionada. As ablações predefinidas de pesos desta entrega não iniciam
a sensibilidade de máscara, terreno, resolução ou halo da etapa 10.
