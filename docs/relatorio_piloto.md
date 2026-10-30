# Avaliação do piloto — etapa 11

**Decisão: depende de referência complementar.** Há também ajuste limitado de implementação antes da amostra: driver de múltiplos corredores, coorte conjunta e orçamento por janela. O piloto técnico é executável e rastreável; sua interpretação científica é descritiva e condicional à máscara não validada. Ainda não existe amostra com qualidade e independência demonstradas para sustentar conclusões do artigo.

A etapa 11 foi executada por `evaluate-pilot`, lendo manifestos 01–10, relatórios originais, tabelas físicas e metadados dos vetores/arquivos. Nenhum novo registro de nuvem foi decodificado, nenhum rótulo foi criado e a amostra não foi processada. As fases anteriores continuam históricas e não foram sobrescritas.

Execução: `20261026T002006Z_7afdd4426f`. Foram reconstruídas 15 execuções científicas selecionadas e conferidos 1177 registros de fonte por hashes. Mudanças esperadas em código, estado e decisões não são confundidas com alteração dos produtos científicos imutáveis. Manifestos completos: `docs/manifesto_etapa01.json` a `manifesto_etapa10.json`. Rastreio por execução/comando/configuração/tamanho: `/home/s299259068/Área de Trabalho/Projetos/2026/sbsr_lidar_2027/relatorios/etapa11/20261026T002006Z_7afdd4426f/execucoes_reconstruidas.csv`. Os três arquivos de anotação mutáveis foram conferidos no estado atual, preservando sua natureza de trabalho. A infraestrutura da etapa 02 mantém as evidências históricas de IO, ambiente e retomada. Isto não certifica os bilhões de registros municipais. No plano futuro foram lidos somente cabeçalhos de arquivos existentes; faltantes não tiveram contagens inventadas.

## Respostas técnicas e científicas

|Caso|P (m²)|O comum observado (m²)|O/P|Grade 50: total/elegível A/elegível A+3D|
|---|---:|---:|---:|---|
|principal|65807.713|65233.110|0.9913|67/59/58|
|adverso|13144.745|6076.513|0.4623|25/3/2|

O principal mede o polígono oficial CO_BT_01_E (único existente no cadastro); o adverso mede apenas CO_SE_06∩3312-431, não o corredor inteiro. Perímetros de 2026 e vegetação de 2020 não demonstram condição de implantação/manutenção em 2020. Os casos têm finalidades diferentes e não são duas réplicas intercambiáveis.

**Terreno:** foi utilizável no suporte aceito pelo TIN5. O datum permaneceu EPSG: 31983 e Maregr.Imbituba(SC)-MAPGEO2015; H é Z absoluto menos terreno contínuo. Classe 8 do MDT é tratada por procedência, não convertida em classe 2. A reserva interna de MDT não é referência altimétrica independente.

|TIN5, reserva interna|n válido / avaliado|Fração válida|MAE nos válidos (m)|RMSE nos válidos (m)|
|---|---:|---:|---:|---:|
|main/reserved_points|19850/20000|0.9925|0.02492|0.05816|
|main/reserved_blocks|6400/20000|0.3200|0.05578|0.11252|
|adversarial/reserved_points|4848/4913|0.9868|0.05538|0.17524|
|adversarial/reserved_blocks|1315/4681|0.2809|0.12150|0.32860|

A retenção de blocos remove vizinhanças inteiras: a cobertura cai para 32% no principal e cerca de 28% no adverso. Erro baixo somente nos pontos suportados não prova bom desempenho em vazios, água ou pontes. A comparação TIN/IDW da etapa 04 usa também o subconjunto comum; a tabela acima descreve cada reserva válida de TIN, sem trocar denominadores. Não foi medida acurácia absoluta externa.

**Árvores versus estruturas:** a separação ainda não tem qualidade medida. Há zero anotações humanas concluídas e zero referências independentes de altura/prioridade. Precisão, recall, IoU e confusão permanecem ausentes. Classes LAS, H, diagnósticos de planaridade e RGB/NIR não são verdade de campo; classe 1 alta pode conter omissão e classes 3/4/5 são candidatas. O refino experimental não foi demonstrado superior à baseline. A referência existente contém 20 janelas, 100 tarefas e cinco janelas para dupla anotação, ainda pendentes.

**NoData:** foi tratado tecnicamente. Os estados de falta de MDS, QC excluído, terreno/H sem suporte, classificação incerta e ausência de copa detectada permanecem distintos. O=0 não vira cobertura zero; falta de H não recebe altura zero. T/O é cobertura condicional, acompanhada de O/P e limites geométricos que não incorporam erro de classificação. O/P do adverso não autoriza interpretar a parte sem observação como ausência de árvores.

**Eixos e lacunas:** o principal conservou 31 ramos e 15 junções após a poda, sem um eixo único defensável pela regra fixada. O eixo geométrico do adverso foi aceito, mas 597 das 635 seções têm suporte desconhecido e nenhum segmento de 25/50/100 m cumpre o mínimo longitudinal. Quatro sequências candidatas de lacuna têm censura e não são recomendação de plantio. B/C continuam fora do núcleo; a comparação viável é A/A+3D em grade. Aceitação geométrica não substitui validação independente do eixo.

**Bordas:** existe efeito de contexto, não eliminável por relato de erro médio pequeno. Ao incluir halo 10, a grade de terreno principal ganhou 593 células válidas e perdeu 2; no adverso ganhou 315 e perdeu 2. São contagens por centro, não áreas vetoriais exatas. O adverso omite 793,220 m² do contexto solicitado por seu recorte à folha. Manchas formadas no contexto e censura do limite permanecem explícitas. P.buffer(5/10 m) é outro domínio de medição e não entra na estabilidade de P.

**Indicadores e rankings:** I1 descreve cobertura detectada no suporte comum; I4 descreve IDs de componentes por área observada, com forte dependência de resolução/conectividade. I6/P95 e I7/IQR descrevem retornos ponderados pela aquisição, não altura por árvore ou volume. Quantis e áreas foram verificados; a interpretação semântica depende da referência. A informação adicional não implica benefício ecológico ou ganho de acurácia.

Na grade 50 principal, H1 tem 76 pares e 50 unidades únicas com cobertura semelhante; mediana da diferença absoluta de P95=2,73037 m. Pares reutilizam unidades e não são réplicas. Para H2, A/A+3D principal tem rho=0,873396, Jaccard operacional top 20%=0,50 e inclusivo=0,5625; a amplitude de posto entre dez receitas chega a 33. A orientação alternativa de IQR aproxima rankings de A. O adverso tem apenas duas unidades, A constante e Spearman/Jaccard substantivos indisponíveis. Ausência de alteração em empates não demonstra equivalência.

Na sensibilidade de 60 cenários, a coorte global principal tem 5/1/0 unidades em 25/50/100 m; o adverso tem 0/0/0. Comparações pareadas em suporte comum podem ter correlação alta sem estabilidade universal. A+3D de 25→100 m apresenta Jaccard de área0,13714 sobre a interseção espacial das partições, sem comparar IDs incompatíveis. Com máscara fixa, retenção1/4/s2027 tem mediana absoluta de ΔP95=0,04585 m e máximo2,32024 m; primeiros retornos elevam P95 em mediana0,27011 m. Não se escolheu peso ou cenário por vantagem de 3D.

Os contextos em que 3D pouco acrescenta ou não pode ser julgado incluem: A constante/coorte mínima; alteração pequena de alturas frente ao controle de pesos; redundância I5/I6 e I6/I7; ranking dependente do sinal de IQR; e suporte insuficiente. A baixa interseção entre escalas, a mudança por componentes e a coorte global quase vazia impedem generalização de robustez. H3 não foi testada: falta alvo independente e discordância não é melhora.

## Critérios e inventário de falhas

|Critério|Estado|Decisão|
|---|---|---|
|C11_01 — Rastreabilidade e execução técnica|atendido|Execuções selecionadas e fontes conferidas por hashes, sem repetir processamento de nuvens.|
|C11_02 — Terreno utilizável|parcial|TIN5 utilizável no domínio suportado; acurácia absoluta independente não medida.|
|C11_03 — Separação árvores/estruturas com qualidade medida|dependencia_impeditiva|0 anotações concluídas; precisão/recall/IoU não disponíveis.|
|C11_04 — NoData e observabilidade|atendido_tecnicamente|Ausência de MDS, QC excluído, terreno/H sem suporte e classificação incerta permanecem distintos.|
|C11_05 — Eixo e indicadores B/C|insuficiente_no_formato_atual|Principal ramificado sem eixo único; adverso geométrico com observação longitudinal insuficiente. Adotar A/A+3D em grade.|
|C11_06 — Efeito de borda/contexto|observado|Halo 10 ganha suporte em relação a halo 0; contexto truncado no adverso e componente censurado são explícitos.|
|C11_07 — Interpretação e estabilidade dos indicadores|condicional|I1/I4 são cobertura/componentes detectados; I6/I7 descrevem retornos. I4 depende de resolução/conectividade; primeiros retornos alteram estimando.|
|C11_08 — Robustez global do ranking|limitada|Interseção elegível global principal 25/50/100 m=5/1/0; adverso=0/0/0. Frequências por eixo/receita não substituem suporte global.|
|C11_09 — Ganho frente a alvo independente|nao_testavel_sem_referencia|0 alvos independentes. H3 desabilitada.|
|C11_10 — Amostra para sustentar o artigo|nao_demonstrada|Dois casos heterogêneos, um grupo/caso, desenvolvimento pós-inspeção. Preparar novos blocos e referência.|
|C11_11 — Custo e execução ampliada|requer_ajuste_limitado|Custos medidos em dois recortes; driver de múltiplos corredores, coorte conjunta e janelas limitadas ainda precisam implementação/teste.|

A tabela completa de fontes/limites está em `docs/criterios_evidencias_etapa11.csv`; o inventário em `docs/inventario_falhas_etapa11.csv` contém ação concreta, evidência de aceitação e quais caches seriam afetados. As dependências não foram convertidas em aprovação científica.

A classificação geral é **depende de referência complementar**. O componente A/A+3D requer ainda ajuste limitado do driver; o formato B/C é insuficiente nos casos atuais. Não se declara pronto para amostra científica nem artigo pronto apenas porque o código executa. O próximo passo pode preparar referência e planos, mas a execução científica permanece desabilitada até demonstrar qualidade da referência, suporte, driver e orçamento.

## Continuação e alcance do artigo

O protocolo pós-piloto0.2.0 fixa a proposta antes dos novos rankings: `docs/protocolo_amostra_v0_2_0.md`, `configs/amostra_cientifica_v0_2_0.yaml` e `configs/protocolo_congelado_amostra_v0_2_0.json`. O universo e papéis planejados estão em `docs/proposta_amostra_etapa11.csv` e no quadro vetorial completo com exclusões. A proposta não altera o protocolo histórico0.1.0. Mudanças necessárias depois do congelamento geram nova versão e resultados separados, sem pré-registro retroativo.

O artigo enxuto poderá tratar H1/H2 apenas após medir qualidade da máscara e descrever o suporte/perdas da nova amostra: tabela de unidades/observação e validação, distribuição física condicional, comparação com controles e mapa de estabilidade com incerteza. B/C exigiriam eixo/lacunas defensáveis e outro escopo. H3/utilidade/intervenção exigem alvo próprio. Resultado negativo é admissível: pouco incremento, diferença explicada por pesos, menor estabilidade, ou diferenças menores que a incerteza de referência. Se referência/amostra não forem suficientes, a alternativa é um estudo metodológico de limitações do piloto, sem vender melhoria de diagnóstico municipal.

Custos e recursos estão em `docs/plano_custo_etapa11.md`. Nenhum download complementar ou processamento fora dos dois casos foi iniciado. A etapa 12 recebe **modo amostra_cientifica**, lista/ordem proposta, reservas, blocos e condições de execução; modo municipal permanece desabilitado.

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml evaluate-pilot --design configs/amostra_cientifica_v0_2_0.yaml
.venv-cientifico/bin/python scripts/documentar_piloto_etapa11.py
.venv-cientifico/bin/python scripts/verificar_etapa11.py
```

Verificação: 168 testes científicos (seis novos), 25 testes do downloader e dois subtestes; sete avisos de depreciação anteriores em Rasterio/Affine. A auditoria independente em `relatorios/etapa11/verificacoes.json` confere fontes, papéis/blocos, capacidade geométrica, fórmulas de custo, arquivos faltantes, congelamento e ausência de amostra/rótulos/inferência fabricados. Mapa da proposta e orçamento: `relatorios/etapa11/proposta_e_custo.png`, gerado por `scripts/visualizar_plano_etapa11.py`.
