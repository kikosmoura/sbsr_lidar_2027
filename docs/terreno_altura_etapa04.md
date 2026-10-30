# Etapa 04 — Terreno e altura normalizada

Executada em 25/10/2026, restrita aos dois domínios da etapa 03. Foram gerados
DTM, suporte, validação interna e H por ponto. Não foram iniciadas anotações,
máscara arbórea, segmentação ou indicadores das próximas etapas.

## Execuções e acesso aos produtos

- Principal, CO_BT_01_E: `20261025T170202Z_dd72292306` —
  [relatório completo](../relatorios/execucoes/20261025T170202Z_dd72292306/qc_altimetrico.json),
  [resumo e caminhos](../relatorios/execucoes/20261025T170202Z_dd72292306/qc_altimetrico.md),
  [mapa](../relatorios/etapa04/terreno_main.png), [perfis](../relatorios/etapa04/perfis_main.png).
- Adverso, CO_SE_06 ∩ 3312-431: `20261025T170318Z_1bf13e94c0` —
  [relatório completo](../relatorios/execucoes/20261025T170318Z_1bf13e94c0/qc_altimetrico.json),
  [resumo e caminhos](../relatorios/execucoes/20261025T170318Z_1bf13e94c0/qc_altimetrico.md),
  [mapa](../relatorios/etapa04/terreno_adversarial.png), [perfis](../relatorios/etapa04/perfis_adversarial.png).

Os produtos estão em `<dados>/experimento/etapa04/<caso>/<run_id>/`. Os
domínios continuam separados: polígono oficial no principal; interseção com a
folha e contexto truncado no adverso, conforme documentado na etapa 03.
Não houve download adicional ou escrita nos originais.

## Referências, unidades e sobreposições

Os dez cabeçalhos foram reconferidos: EPSG:31983; GeoKeys 3076 e 4099 = 9001
(metros para XY e Z); VLR vertical `Maregr.Imbituba(SC)-MAPGEO2015`.
Não se aplicou correção geoidal. Offsets diferentes entre MDT e MDS foram
decodificados individualmente: por exemplo, na 3313-333, MDT usa
(310000,7340000,0) e MDS usa (320000,7390000,0), ambos com escala de 0,001 m.

O candidato a terreno é exclusivamente o produto MDT, por procedência. A classe
8 foi preservada; nenhum MDS classe 8 foi promovido a terreno e nenhum arquivo
foi reclassificado como classe 2. Withheld, retornos inválidos e classes 7/18
são excluídos do suporte; as classes originais permanecem nos arquivos fonte.

Cada arquivo contribui somente dentro de sua folha nominal e do contexto. Na
borda compartilhada, a menor chave de folha possui o ponto. As faixas externas
dos arquivos exportados não são contadas novamente. Isso pode reduzir suporte
onde o arquivo proprietário não observa pontos que outro exportou: a política
é explícita e conservadora; não substitui análise de omissão/classificação.

No MDT, chaves XYZ/XY em 0,001 m removem coincidências e agrupam colunas XY.
Z é a mediana dos XYZ distintos; colunas com amplitude vertical >0,10 m seriam
excluídas como conflito. No principal houve uma coluna com dois Z, nenhum
conflito acima do limite e **251.439 vértices** finais, de 251.440 registros.
No adverso ficaram **49.139 vértices**, sem agrupamentos múltiplos. Não houve
XYZ idêntico adicional após a seleção nominal. Não se deduplicam registros
MDS dentro da mesma folha; contagens continuam sendo de registros, não pulsos
independentes. MDT e MDS tampouco são observações independentes.

## Interpolação e suporte

O suporte MDT da janela é carregado em memória; leitura dos arquivos é por
blocos de 500 mil. TIN e KD-tree não são algoritmos streaming. O limite é de
1 milhão de registros MDT da janela e há verificação conservadora de memória.
Consultas usam blocos de 50 mil, com um trabalhador.

TIN linear usa Delaunay/bariêntricas em coordenadas XY transladadas para uma
origem local, evitando operar diretamente com as grandes coordenadas UTM.
Para uma consulta interpolada ser válida:

1. Ela deve estar dentro da envoltória dos vértices MDT.
2. O vizinho mais próximo e cada vértice do triângulo devem estar a até r.
3. A maior aresta deve ser ≤2r e o circunraio deve ser ≤r.

Uma coincidência XY exata (tolerância numérica 1e-7 m) copia a observação
conhecida; não constitui extrapolação. Pontos fora da envoltória permanecem
desconhecidos mesmo se um vizinho estiver próximo.

IDW usa potência 2, no máximo oito vizinhos e mínimo de três dentro de r.
Exige também o suporte geométrico acima e vizinhos distribuídos ao redor da
consulta (maior intervalo angular ≤180°). É uma alternativa deliberadamente
conservadora: não interpola a partir de vizinhos concentrados de um único lado.
O mapa de contagem informa todos os vértices dentro do raio; o IDW usa até oito.

Foram comparados raios **3/5/10 m**; o principal permanece **5 m**, como no
protocolo. Ampliar o raio não torna água, pontes ou grandes vazios confiáveis.
Não foram introduzidas barreiras de água/pontes, pois não há referência
independente para desenhá-las. Os limites geométricos são QC, não validação
semântica do terreno.

Rasters têm EPSG:31983, célula de 1 m, origem global (0,0) e NoData −9999.
A mesma extensão/transformação sustenta os produtos de cada caso. Calcula-se
no contexto e só então aplica-se a máscara de medição. A arquitetura aceita
0,5/2 m; alinhamento nessas resoluções foi testado sinteticamente, sem executar
uma análise científica de sensibilidade multirresolução nesta etapa.

## Validação interna e escolha do método

Reservas antes de construir cada superfície de teste, com semente 2027:

- Pontos: seleção aleatória de 10%, limitada a 20 mil. No principal, o teto
  resultou em 20.000 reservados e 231.439 de treino; no adverso, 4.913/44.226.
- Blocos: células espaciais de 10 m selecionadas por hash determinístico em
  aproximadamente 10% dos blocos. Todos os XY dos blocos escolhidos são retirados
  do treino, mesmo quando apenas 20 mil são avaliados. Principal: 24.598
  reservados, 226.841 de treino, 20.000 avaliados; adverso: 4.681/44.458/4.681.

Não separam aquisições independentes. Reservas por ponto ainda têm forte
proximidade do treino; blocos são um teste de estresse de interpolação em vazios.
Não se derivam intervalos de confiança ou acurácia absoluta desses resíduos.

A regra implementada antes da execução seleciona menor RMSE no suporte válido
**comum** do teste por blocos, em r=5 m, com mínimo de 50 consultas. Se esse
suporte for insuficiente, usa a reserva por pontos; se ambas falharem, exige
revisão/fixação explícita do método. Não escolhe o raio pelo resultado favorável.

| Caso, r=5 m | Pontos comuns dos blocos | RMSE TIN comum (m) | RMSE IDW comum (m) |
|---|---:|---:|---:|
| Principal | 349 | 0,1096 | 0,1239 |
| Adverso | 117 | 0,2171 | 0,2195 |

TIN foi escolhido no principal e mantido explicitamente no adverso. A restrição
angular do IDW reduz bastante seu suporte no teste de blocos: no principal,
6400/20000 consultas foram válidas no TIN e apenas 349 no IDW; no adverso,
1315/4681 e 117. A comparação comum cobre, portanto, uma fração pequena e
particular da reserva. **Não prova superioridade universal do TIN.**

Nos pontos aleatórios comuns do principal, r=5 m, RMSE foi 0,0556 m TIN e
0,0578 m IDW (19.022 consultas). No adverso: 0,1732/0,1749 m (4.710).
Os relatórios incluem viés, MAE, RMSE, P95 absoluto, número avaliado e fração
válida de cada cenário, além dos resíduos em `validacao_reservada.csv`.

Esta é uma escolha exploratória após QC, sem mudança nos estimandos do
protocolo 0.1.0. A referência congelada está em
`configs/terreno_congelado_etapa04.yaml` (`method: tin`, raio 5 m).
`configs/piloto.yaml` mantém `pending_qc` para reproduzir a seleção automática.
Uma alteração desses parâmetros requer nova execução e registro; não é
pré-registro retroativo da escolha.

## Suporte, contexto e H observados

| Cenário TIN | Principal: válidas / 65.817 células | Adverso: válidas / 13.142 células |
|---|---:|---:|
| r=3 m | 62.939 (95,63%) | 6.886 (52,40%) |
| **r=5 m** | **65.248 (99,14%)** | **7.803 (59,37%)** |
| r=10 m | 65.804 (99,98%) | 9.495 (72,25%) |

Em r=5 m, permanecem 569 e 5.339 células de medição com DTM ausente. A validade
do terreno não implica observação MDS, presença de copa ou elegibilidade das
futuras unidades amostrais. O adverso não tem suporte para tratar todo o domínio
como observado. Essas áreas não foram preenchidas com zero.

Também se interpolou depois de retirar os pontos do contexto, mantendo a mesma
grade. No principal, o contexto ganhou 593 células válidas e perdeu 2, saldo
591; na borda interna de 2 m ganhou 564 e perdeu 1. No adverso ganhou 315 e
perdeu 2, saldo 313; na borda ganhou 289 e perdeu 0. A triangulação pode mudar
com os pontos externos, razão para registrar também as perdas. O RMSE da
diferença com/sem contexto nas células comuns de medição foi 0,0127 m no
principal e 0,0041 m no adverso; não é erro absoluto de terreno.

H é calculado por registro MDS em float64: **H = Z absoluto − DTM contínuo(X,Y)**.
Não se subtrai `user_data` nem uma segunda altura normalizada. Os GeoTIFFs são
avaliações float32 da mesma superfície nos centros das células; H não é calculado
amostrando pixels arredondados do raster. Os vértices serializados e parâmetros
permitem reconstruir a superfície e H sem duplicar todas as dimensões LAS.

| Caso | Registros MDS no contexto | Na medição | H válido na medição | H ausente na medição |
|---|---:|---:|---:|---:|
| Principal | 1.967.742 | 1.395.109 | 1.382.529 | 12.580 |
| Adverso | 225.983 | 98.688 | 73.019 | 25.669 |

Os registros foram preservados mesmo onde H é desconhecido (`null`). Há
228.544 H negativos no contexto principal e 42.640 no adverso; muitos são
pequenos resíduos de terreno, não árvores com altura negativa. Não foram
truncados. Alertas H<−1 m: 11 no principal, todos fora da medição; 3 no adverso,
2 dentro da medição. São classe 1 e exigem inspeção. Nenhum H válido excedeu o
alerta de 80 m. −1/80 m são flags operacionais, não limiares ecológicos ou
garantia de ausência de extremos entre pontos sem terreno.

O [diagnóstico de alertas](../relatorios/etapa04/diagnostico_alertas.json)
lista coordenadas, índices de origem, comparação TIN/IDW e suporte local. Ele
mostra, por exemplo, amplitudes verticais de alguns triângulos de vários metros
mesmo com vizinhos próximos. Não se pode determinar ponte, muro, ruído ou erro
de classificação sem referência. Flags LAS 9/17 não ocorreram, o que não prova
ausência de água/pontes. A referência/anotação da etapa 05 deve revisar esses locais.

Como conferência de produtos relacionados, 10.000/10.000 pontos da amostra MDS
classe 8 do principal coincidiram em XY e Z a 2 mm com MDT; no adverso foram
9.982/10.000. Não generalizar inclusão completa do MDT, nem usar essa coincidência
como acurácia externa. As diferenças H−user_data das amostras de classes 3/4/5
ficaram majoritariamente próximas da faixa de arredondamento ±0,5 m. Quantis
por classe usam até 10 mil registros uniformes por prioridade aleatória; as
contagens e flags são integrais. A classificação vegetal ainda não foi validada.

## Arquivos e reprodução

Além de `dominios.gpkg`:

- `dtm_{tin,idw}_r{3,5,10}_{contexto,medicao}.tif`.
- `validade_{tin,idw}_r*.tif`: 0 válido, 1 fora da envoltória, 2 vizinho além
  do raio, 3 triângulo sem suporte, 4 poucos vizinhos IDW, 5 IDW unilateral;
  255 fora do contexto. H tem ainda status 6 para ponto excluído por QC.
- `distancia_mdt_mais_proximo.tif`, `contagem_mdt_r*.tif` (vértices XY únicos),
  `triangulos_qc.tif` (aresta máxima/circunraio), `efeito_contexto_dtm.tif` e
  `dtm_sem_contexto_medicao.tif`.
- `vertices_terreno.parquet`, `alturas_pontos.parquet`,
  `contagens_altura.tif` (registros MDS totais/H válido/H<−1 m).
- `validacao_reservada.csv`, `perfis_cartesianos.csv`,
  `pontos_alerta_amostra.csv` (primeiros 1000 alertas; todos os 11/3 couberam).

O Parquet de alturas contém `source_tile`, índice original do registro,
X/Y/Z absoluto, classe, user_data, números de retorno, terreno, H, pertencimento
à medição e flags. RGB/NIR e outras dimensões continuam nos LAZ originais;
o Parquet é um produto parcial ligado a eles, não substituto integral do LAZ.
Perfis são cortes E–W/N–S no ponto representativo do polígono, sem afirmar
que descrevem um eixo longitudinal ou todos os problemas do terreno.

Com o HD montado, na raiz do projeto:

```bash
.venv-cientifico/bin/sbsr-lidar --config configs/piloto.yaml terrain --case main
.venv-cientifico/bin/sbsr-lidar --config configs/piloto.yaml terrain --case adversarial --method tin
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa04.py
```

Para usar explicitamente o método fixado no piloto em execuções futuras:

```bash
.venv-cientifico/bin/sbsr-lidar --config configs/terreno_congelado_etapa04.yaml terrain --case main
```

O cache verifica conteúdos, parâmetros, código, ambiente e produtos. Foi
demonstrado nos dois casos. A configuração congelada é uma identidade de cache
distinta; seu comando produzirá nova execução. `--no-cache` força processamento
completo em novo diretório. Após falha, repetir reutiliza apenas produtos
completos válidos; não há retomada no meio da triangulação ou de um Parquet.

Para mapas/perfis, passar o `report` retornado pela CLI:

```bash
.venv-cientifico/bin/python scripts/visualizar_altimetria_etapa04.py CAMINHO/qc_altimetrico.json --output-dir relatorios/etapa04
```

Verificação desta entrega: **76 testes científicos, 25 testes do downloader
com 2 subtestes e 21 verificações dos produtos reais passaram**. Os testes
cobrem offsets distintos, plano analítico, alinhamento 0,5/1/2 m, NoData versus
zero, extrapolação, triângulo sem suporte, reservas por bloco, preservação de
Z/classe, alturas negativas/extremas e cache. O verificador checou a fórmula H
em todos os registros do Parquet, reconstruiu H a partir dos vértices para uma
amostra e recuperou 29 registros por seus índices nos LAZ para comparar XYZ,
classe e user_data. A amostra de origem não é validação de campo. Referências
`execucao_*.json` e logs do verificador correspondem a esta entrega; atualizá-los
se for criada nova entrega.

Tempo/pico RSS dos processos: principal **37,25 s / 695,33 MiB**; adverso
**6,63 s / 443,99 MiB**. Medições não estimam custo municipal. Originalmente
8 GiB foram o orçamento, não uma medição de consumo.

Implementação usa APIs documentadas de
[Delaunay](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Delaunay.html),
[busca do triângulo](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Delaunay.find_simplex.html),
[KD-tree](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.query.html)
e [coordenadas escaladas LAS](https://laspy.readthedocs.io/en/latest/complete_tutorial.html).
As regras de suporte são escolhas operacionais deste piloto, não garantias
fornecidas por essas bibliotecas.

Etapa 04 concluída. Acurácia absoluta, referência de campo, água/pontes e
classificação arbórea continuam dependências da validação. O experimento completo
ainda não está concluído. Próxima etapa: **05, referência e anotação**.
