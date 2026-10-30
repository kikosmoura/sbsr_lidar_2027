# Etapa 08 — indicadores físicos e suporte por unidade

Implementada e executada em **25/10/2026**, somente nos dois casos do piloto.
Foram produzidas **426 linhas, com 114 colunas**, em GeoParquet/CSV: 286 do
principal e 140 do adverso. A máscara **baseline_h3**, H e unidades das etapas
04/06/07 foram reutilizados e conferidos por hash, sem reconstrução silenciosa.

I1, I4, I5, I6 e I7 foram implementados. I2/I3 foram implementados e testados
analiticamente, mas **permanecem ausentes no piloto real**: o principal não tem
eixo aceito e nenhum segmento do adverso atende ao suporte longitudinal.
Comprimentos/censuras continuam como diagnósticos físicos. I8/I9/I10 estão
fora do núcleo. Nenhum escore, ranking, rótulo humano ou acurácia foi criado.

Para a próxima etapa, o universo registrado é **grade, por caso e escala**.
Na escala principal de 50 m, há **58 unidades do principal e duas do adverso**
elegíveis para comparação com altura. Uma unidade adicional do principal tem
cobertura candidata zero e suporte areal suficiente; é um estrato separado,
com altura indefinida, sem penalidade adicional inventada. Esses números não
constituem comparação de rankings ou inferência municipal.

## Entregas e rastreabilidade

| Caso | Execução final | Linhas | Produto no HD |
|---|---|---:|---|
| Principal | `20261025T221430Z_ad89ab6173` | 286 | `experimento/etapa08/main/20261025T221430Z_ad89ab6173/` |
| Adverso | `20261025T221433Z_a9f46ac6fe` | 140 | `experimento/etapa08/adversarial/20261025T221433Z_a9f46ac6fe/` |

Raiz dos produtos: `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027`.
Em cada diretório:

- `indicadores.parquet`: GeoParquet, geometria WKB e CRS EPSG:31983;
- `indicadores.csv`: mesmos atributos, geometria em `geometry_wkt`;
- `intersecoes_manchas.parquet` e `.csv`: ligação unidade↔mancha contextual,
  com área de interseção e flags de censura da mancha;
- `dicionario_dados.json`: esquema completo de colunas, fórmulas, unidades,
  estimandos, regras de suporte e ausência.

Uma cópia local do dicionário está em
[`dicionario_indicadores_etapa08.json`](dicionario_indicadores_etapa08.json).
Essa cópia corresponde ao principal; tipos de armazenamento de colunas inteiras
null podem variar por caso, conforme o dicionário no diretório de cada execução.
As unidades de medição têm ID estável `unit_id` e `measurement_id` combinando
unidade/cenário. São registrados IDs de corredor/parte/ramo, família, escala,
folhas, geometria, referência linear/comprimento quando aplicável, cenário,
resolução, conectividade e IDs de execução de terreno/máscara/unidades/indicadores.

`source_units_file`, `units_source_layer`, `source_height_file` e hash da
geometria permitem seguir cada linha até os arquivos fonte. Manifestos locais
em `relatorios/execucoes/<run_id>/` registram entradas, parâmetros, ambiente,
código, produtos, log e cache. As referências curtas estão em
`relatorios/etapa08/execucao_{main,adversarial}.json`.

Primeiras execuções desta etapa foram preservadas sob referências
`execucao_*_antes_censura_explicita.json`; os diretórios finais acima acrescentam
flags explícitas de censura mesmo em unidades longitudinais inelegíveis.

## Dicionário científico do núcleo

Sejam A=área total da unidade, O=área observada comum, T=área de copa candidata
dentro da unidade e N=número de IDs distintos de manchas com área positiva nela.

| Campo | Fórmula/estimando | Unidade | Suporte/ausência |
|---|---|---|---|
| I1 | T/O | fração | Null se O=0; valor descritivo com O parcial não implica elegibilidade |
| I4 | N/(O/10.000) | manchas/ha observado | Null se O=0; N não é número de árvores |
| Maior mancha | max área(U∩mancha), mais fração em T | m²/fração | Fração null se T=0; área externa inteira não é atribuída à unidade |
| I5 | média de H dos retornos vegetais selecionados | m | T≥10 m² e pelo menos 50 retornos válidos |
| I6 | P95 de H, interpolação linear | m | Mesmos retornos e suporte de I5 |
| I7 | P75(H)−P25(H) | m | IQR dos mesmos retornos; não heterogeneidade de CHM |
| I2 | comprimento de lacuna observável / comprimento observável | fração linear | Somente eixo aceito e unidade longitudinal elegível |
| I3_local_m | maior interseção de lacuna do ramo com intervalo da unidade | m | Preserva censura no corte e no ramo; null sem elegibilidade |
| I3_local_over_observable_length | I3_local_m / comprimento observável | fração linear | Mesmo domínio de I2 |
| I3_branch_m | comprimento completo da lacuna associada à maior interseção local | m | Null se censurada, não associada ou inelegível |

Quantis são exatos, com `numpy.quantile(method="linear")`. Não se usa amostra
aleatória, `user_data` arredondado, elevação Z absoluta ou P95 dos máximos por
célula como substituto. O estimando é a **distribuição de retornos da aquisição**,
com influência de densidade, retornos múltiplos e oclusão; não é média por árvore
ou média de alturas ponderada pela área da copa. I5 é auxiliar; I6/I7 são os
dois descritores 3D primários, sem direção ecológica universal atribuída.

Os retornos selecionados têm classes 3/4/5, H finito≥3 m, `terrain_status=0`,
sem bit de exclusão de QC, pixel pertencente à copa/V congelados e XY dentro
da copa de medição. A classe 3 é preservada quando compatível com H. Alerta
de altura extrema é contabilizado, sem novo filtro silencioso. Registros
repetidos internos ao MDS são preservados; não equivalem a observações independentes.

## Cobertura, observação e elegibilidade

A área O é o mesmo V congelado que exige observação MDS, terreno no centro e
algum H válido. Não é área total do polígono nem apenas envelope de pontos.
Todas as áreas são interseções vetoriais exatas em metros; contagens de centros
de célula são diagnósticos separados, sem substituir A/O/T.

Cada linha reporta O/A, 1−O/A e limites geométricos para a cobertura total:

```text
limite inferior = T/A
limite superior = (T + A − O)/A
```

São limites sobre suporte não observado, não intervalos de confiança nem
correção de erro de classificação. Incerteza semântica dos bits 1/2/4/8/16 é
quantificada e permanece em O. Não se retira uma área difícil do denominador
para aumentar cobertura ou tornar métodos aparentemente comparáveis.

Áreas por motivo de suporte também estão na tabela: com qualquer MDS, com
MDS após QC, sem MDS, sem terreno/H comum, somente registros excluídos por QC,
terreno válido e eventual parte fora dos estados do raster de observação.
Os estados comuns conservam toda A, inclusive os vazios. Terreno raster válido
e H válido por ponto têm contagens próprias, sem presumir que sejam equivalentes.

`eligible_A` exige A≥25 m² e O/A≥0,95. `height_support_sufficient` exige
O>0, T≥10 m² e n_retornos_vegetais≥50. `eligible_A_plus_3D` é a interseção
dos dois critérios. Alguns valores de altura são calculáveis em unidades
parcialmente observadas, mas isso não as torna elegíveis para comparação.
Todas continuam na tabela com `exclusion_reason_*` e `*_missing_reason`.

| Caso/família | Escala | Unidades | Elegíveis A | Elegíveis A+3D | Elegíveis B |
|---|---:|---:|---:|---:|---:|
| Principal/grade | 25 m | 192 | 161 | 150 | 0 |
| Principal/grade | 50 m | 67 | 59 | 58 | 0 |
| Principal/grade | 100 m | 27 | 25 | 25 | 0 |
| Adverso/grade | 25 m | 59 | 11 | 5 | 0 |
| Adverso/grade | 50 m | 25 | 3 | 2 | 0 |
| Adverso/grade | 100 m | 10 | 0 | 0 | 0 |

As 46 linhas longitudinais do adverso são mantidas para auditoria física:
26/13/7 nas escalas 25/50/100 m. Algumas têm métricas areais/alturas disponíveis,
mas nenhuma atende aos critérios de B. Não misturar essas linhas à grade para
simular mais unidades ou reativar uma comparação B/C indisponível.

## Unidades sem copa e métricas indefinidas

Com O>0 e T=0, I1 e I4 podem ser zero. I5/I6/I7 permanecem null, com motivo
`sem_vegetacao`, ou `classificacao_incerta_sem_copa_detectada` quando houver
suspeita semântica pertinente. Isso representa ausência detectada pela regra,
condicional à máscara não validada, sem alegar ausência confirmada em campo.

Com O=0, I1/I4/altura são indefinidos: não se preenche nenhum deles com zero.
Sem observação, falta de terreno/H e exclusão por QC têm estados diferentes.
Com T positivo, mas T<10 m² ou menos de 50 retornos, a altura também fica
ausente com motivo específico. Não se confunde essa insuficiência com ausência
de vegetação nem se aplica penalidade de altura fictícia.

No principal, a unidade de 50 m
`CO_BT_01_E_P001_G50_X6474_Y147839_F01` atende à área/observação, tem T=0 e
altura ausente. É o estrato de ausência detectada adicional às 58 unidades com
altura elegível. Não foi integrada a nenhum escore nesta etapa.

## Manchas, bordas e posse dos registros

I4 usa os componentes **8 vizinhos da etapa 06**, reconstruídos no contexto
antes do recorte. Um mesmo ID pode aparecer em várias unidades, uma vez em
cada uma; fragmentar sua geometria em U não multiplica o ID. Somar N entre
unidades não estima o número de manchas do corredor. A resolução congelada
de 1 m e a conectividade influenciam N e ficam registradas.

As manchas que somente tocam U sem área não entram. Área máxima/fração de
maior mancha usam apenas a interseção. Censura por limite contextual ou suporte
inválido é preservada na tabela de ligações. Há **87 IDs únicos no principal
e 37 no adverso**, constantes entre escalas/famílias, em conformidade com a máscara.

Cada registro MDS recebe exatamente um dono por família/escala. Em fronteiras
compartilhadas, prefere-se a unidade com maior área de interseção com o pixel
semiaberto do ponto; empate por ID lexicográfico. Isso conserva contagens e
evita atribuir altura a unidade que apenas toca uma célula candidata externa.
A mesma regra é usada nas contagens de centros, que não são áreas.

Cada grade conserva **1.395.109 registros MDS e 774.284 retornos vegetais** no
principal; **98.688 e 2.621**, respectivamente, no adverso. São os registros
dentro de P, não a leitura contextual inteira: 1.967.742 e 225.983 registros
contextuais foram lidos uma vez por caso em blocos de até 65.536.

Densidades têm denominadores explícitos: registros MDS/A, H válido no suporte
comum/O e retornos vegetais/T. São registros por m², não pulsos independentes,
árvores por hectare ou densidade municipal. Os conjuntos de alturas são
limitados a seis milhões de valores armazenados entre famílias/escalas;
estouro desse orçamento interrompe a execução, sem aproximar quantis silenciosamente.

## Lacunas: diagnóstico físico e indicadores indisponíveis

As seções, sequências no ramo e seus limites vêm da etapa 07. O cálculo integra
comprimentos efetivos, inclusive o último intervalo parcial, e não substitui
lacuna longitudinal por área sem copa.

No adverso, as quatro lacunas candidatas de 1/1/2/26 m continuam associadas aos
mesmos IDs. Campos `length_*`, `max_detected_gap_intersection_m`, posições e
flags de corte/censura são preservados mesmo com I2/I3 ausentes. A lacuna de
82 a 108 m continua ligada aos segmentos vizinhos que atravessa; seu comprimento
detectado de 26 m não é apresentado como comprimento completo conhecido quando
há censura por suporte. A referência ao arquivo da etapa 07 conserva também
todas as demais ligações de lacunas de uma mesma unidade.

Na grade, campos longitudinais são null por definição. Em unidade longitudinal
sem ≥95% de comprimento observável ou sem suporte areal, I2/I3 também são null.
Os testes cobrem um ramo sintético com lacuna conhecida de 80 m: o corte em
50 m preserva o comprimento original e sua interseção local; um trecho de
suporte desconhecido interrompe a sequência e conserva as censuras.

## Resultados observados e limites de interpretação

Somando interseções na grade, sem média simples entre células:

| Caso | Área P (m²) | Área O (m²) | Área T (m²) | O/P | T/O |
|---|---:|---:|---:|---:|---:|
| Principal | 65.807,713 | 65.233,110 | 38.528,344 | 99,13% | 59,06% |
| Adverso | 13.144,745 | 6.076,513 | 623,595 | 46,23% | 10,26% |

T/O é cobertura **candidata no suporte observado**, não cobertura validada
do corredor inteiro. O adverso permanece CO_SE_06∩3312-431, não todo CO_SE_06.
Os dois casos são tipologias/escopos distintos, não réplicas independentes.

Nas 58 unidades elegíveis de 50 m do principal, I6 variou de **7,20 a 23,62 m**
e I7 de **0,41 a 11,42 m**. Nas duas elegíveis do adverso, I6 ficou em
**10,85–11,47 m** e I7 em **2,76–7,42 m**. São intervalos descritivos dos
retornos selecionados nestas unidades; não evidenciam vantagem de 3D,
significância, prioridade de intervenção, biomassa ou conectividade funcional.

A validação da máscara, anotações/adjudicação e referências externas continuam
pendentes. A disponibilidade numérica não prova qualidade semântica. Na próxima
etapa, deve-se manter o mesmo universo elegível na comparação pareada, reportar
perdas de suporte e respeitar o estrato sem copa detectada; o caso adverso tem
amostra muito pequena. Não houve comparação/ranking nesta entrega.

## Testes, auditoria e comandos

Passaram **134 testes científicos** (18 novos), **25 testes do downloader com
dois subtestes** e **44 verificações dos produtos reais**. Os sete avisos de
depreciação Rasterio/Affine são dos testes de IO existentes.

Testes novos cobrem área/copa conhecida, altura constante, quantis analíticos,
classe 3, exclusão de edificação e retornos baixos, copa cruzando borda, mesmo
ID multipartes, toque sem área, NoData, ausência detectada de copa, falta de
terreno, incerteza no denominador, insuficiência de altura, lacuna/censura,
posse de fronteira, limites de memória, esquema, IO, cache e origem alterada.

A auditoria real recalculou contagens e quantis de **14 unidades de 50 m**, sete
por caso, usando o Parquet original de H. Média por soma compensada e quantis
por ordenação/interpolação manual conferiram com as saídas. Todas as unidades
foram conferidas quanto a áreas, manchas contextuais, suporte, elegibilidade,
fórmulas e motivos de ausência. CSV/GeoParquet e censuras também conferiram.

As execuções finais foram sequenciais no mesmo processo: tempo instrumentado
**3,20 s principal / 2,04 s adverso**; pico RSS cumulativo do processo
**363,32 MiB**. O pico do adverso inclui o histórico do processo, sem constituir
medição isolada desse caso. Pré-verificação/hash de entradas tem custo adicional.
Não extrapolar esses tempos a um lote municipal.

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml indicators --case main
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml indicators --case adversarial
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa08.py
```

`--no-cache` cria uma nova execução. O cache funcionou nos dois casos. Entradas
de máscara/unidades/terreno/H são conferidas contra suas versões ancestrais;
mudança em produto congelado provoca recusa. A verificação se repete ao fim do
cálculo. Configuração, código e ambiente fazem parte da identidade do cache.
Originais LAZ/ZIP, downloader, polígonos, rótulos e produtos das etapas anteriores
foram preservados. O protocolo continua 0.1.0 com parâmetros aditivos registrados,
sem alegar pré-registro confirmatório de escolhas exploratórias.

Para renderizar os mapas:

```bash
.venv-cientifico/bin/python scripts/visualizar_indicadores_etapa08.py CAMINHO/indicadores.json --output-dir relatorios/etapa08
```

Mapas: [principal](../relatorios/etapa08/indicadores_50m_main.png) e
[adverso](../relatorios/etapa08/indicadores_50m_adversarial.png). Hachuras indicam
unidade inelegível segundo o indicador exibido; cinza indica métrica ausente.
As cores são valores físicos, sem direção normativa ou ranking.

APIs primárias utilizadas:
[NumPy quantile](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html),
[Shapely STRtree](https://shapely.readthedocs.io/en/stable/strtree.html) e
[GeoPandas GeoParquet](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_parquet.html).

Etapa 08 concluída no alcance exploratório. Próxima etapa:
**09 — comparação 2D/3D**, somente quando acionada.
