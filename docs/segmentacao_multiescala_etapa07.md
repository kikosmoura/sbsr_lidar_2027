# Etapa 07 — unidades multiescala e avaliação geométrica dos eixos

Implementada e executada em **25/10/2026**, somente nos dois casos do piloto.
Grades de 25/50/100 m, eixos candidatos, podas, junções, seções, segmentos,
regiões de influência e correspondências estão em GeoPackage no HD externo.
A máscara **baseline_h3 da etapa 06 permanece congelada e não validada**.
Nenhum rótulo humano, escore, ranking ou inferência municipal foi criado.

A alternativa operacional para a etapa 08 é **A/A+3D em grade**, por caso e
escala. B está indisponível no principal pela ambiguidade do eixo e no adverso
por suporte longitudinal insuficiente, embora este tenha eixo geométrico aceito.
Isso é uma limitação observada do piloto, não uma falha a ocultar com uma rota
arbitrária ou com lacunas artificiais. A etapa 08 não foi iniciada.

## Execuções e produtos

| Caso | Execução | Polígono de medição | Área P (m²) | Área observada O (m²) |
|---|---|---|---:|---:|
| Principal | `20261025T215146Z_b6c745db6e` | CO_BT_01_E oficial | 65.807,712664 | 65.233,110031 |
| Adverso | `20261025T215241Z_c33075a9ea` | CO_SE_06 ∩ 3312-431 | 13.144,744694 | 6.076,513395 |

Produtos em:

```text
/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa07/
  main/20261025T215146Z_b6c745db6e/
  adversarial/20261025T215241Z_c33075a9ea/
```

Cada diretório contém `unidades_multiescala.gpkg` e três tabelas CSV:
`correspondencia_suporte`, `ligacoes_lacunas`, `vizinhos_segmentos`.
Relatórios JSON/Markdown, manifestos e logs estão nos diretórios locais
`relatorios/execucoes/<run_id>/`. As referências curtas são
`relatorios/etapa07/execucao_{main,adversarial}.json`.

O GPKG possui 18 camadas espaciais e três tabelas sem geometria:

- `partes`, `eixos_candidatos`, `ramos_podados`, `juncoes`, `regioes_juncao`;
- `grade_{25,50,100}m`, `segmentos_{25,50,100}m`, `influencia_{25,50,100}m`;
- `secoes`, `sequencias_ramo`, `influencia_estacoes`, `sobreposicoes_corredores`;
- `correspondencia_suporte`, `ligacoes_lacunas`, `vizinhos_segmentos`.

Camadas longitudinais vazias do principal são **vazias por decisão registrada**,
não produtos científicos simulados. Sua grade é completa. O eixo do adverso
não representa todo CO_SE_06: continua restrito ao recorte da folha.

## Grade e área de suporte

Grades quadradas em EPSG:31983, metros, ancoradas em (0,0), nas três escalas.
Cada célula é intersectada exatamente com cada parte de P. Se a interseção
produzir polígonos desconectados, cada fragmento recebe um ID; não se constrói
ponte nem se anexa resíduo a outra parte. O contexto de 10 m não amplia P.

IDs incluem corredor/parte, escala, índices globais X/Y e fragmento. Registram-se
área nominal, área efetiva, fração da célula, O, O/área, área de classificação
incerta e folhas atravessadas. Os limites das folhas são procedência, sem cortar
unidades. Há **18 unidades de grade que atravessam folhas**, somadas as três
escalas do principal; no adverso o domínio já é limitado a uma folha.

| Caso | Grade nominal | Fragmentos | Área≥25 m² e O/área≥0,95 | Resíduos com área<25 m² |
|---|---:|---:|---:|---:|
| Principal | 25 m | 192 | 161 | 25 |
| Principal | 50 m | 67 | 59 | 6 |
| Principal | 100 m | 27 | 25 | 1 |
| Adverso | 25 m | 59 | 11 | 10 |
| Adverso | 50 m | 25 | 3 | 1 |
| Adverso | 100 m | 10 | 0 | 0 |

Todas as unidades, inclusive resíduos e inelegíveis, são preservadas. Esses
critérios são de área/observação; a elegibilidade de altura por copa/retornos
será avaliada na etapa apropriada. Não significam máscara validada nem população
municipal representada. Casos e escalas não são reunidos em um ranking único.

Cada grade conserva P; a soma de O das unidades conserva a área observada
congelada. As diferenças numéricas ficaram abaixo da tolerância **10⁻⁴ m²**.
Usa-se interseção vetorial exata para numerador/denominador; não substituir a
área por contagem de centros de pixels. Incerteza semântica permanece dentro de O.

O campo auxiliar de incerteza usa a união de células com bits 1/2/4/8/16
de `incerteza_h3.tif`, recortada exatamente em P: 1.513,308570 m² no principal
e 29,600361 m² no adverso. São suspeitas semânticas da etapa 06, incluindo
classe 1 alta, não uma taxa de erro medida nem necessariamente o estado 2 da
máscara refinada. Não se altera a baseline nem se exclui essa área do suporte.

## Eixos: método, poda e decisão

O Voronoi usa pontos da borda externa e de eventuais anéis, com espaçamento
máximo de **2 m**, incluindo vértices originais. Calcula-se em coordenadas
localmente transladadas e conservam-se arestas finitas inteiramente em P.
O grafo é processado por parte, sem usar a máscara de copa para escolher rota.

Vértices coincidentes a até **10⁻⁵ m** são contraídos antes da avaliação de
graus para evitar junções numéricas. Nenhuma contração foi necessária nos
dois casos reais; o teste de corredor curvo cobre essa situação. Caminhos de
grau 2 são colapsados em ramos, preservando a polilinha e o comprimento real.
IDs de ramo usam hash da geometria normalizada, não o ID da execução.

Uma única passagem remove bissetrizes terminais curtas que satisfaçam ambas:
comprimento≤**25 m** e comprimento≤**2,5×raio na junção**, sendo raio a distância
da junção à borda. Cada ramo removido, sua geometria, comprimento, raio e motivo
ficam em `ramos_podados`. Não se faz poda recursiva de ramos crescentemente longos.

O fator 2,5 foi adotado após inspeção geométrica dos quatro braços de canto
do adverso, cortado obliquamente pela folha: 8,88/10,07/17,23/21,67 m com raio
próximo de 10 m. O fator inicial 1,6 deixava dois braços junto a cantos e
alongava artificialmente o caminho aceito. Essa escolha é exploratória e
motivada pela geometria dos cantos, sem consultar copa, indicadores ou vantagem
de C. Os candidatos/podas continuam disponíveis para contestação/revisão.

Aceitação conservadora por parte: **um único caminho aberto**, sem anel no
polígono, comprimento≥25 m e comprimento/largura mediana≥3. A largura auxiliar
é duas vezes a distância à borda, amostrada em 19 posições internas ao ramo.
Partes ramificadas, com ciclos, muito curtas ou largas ficam em grade. Isso não
afirma que nunca seja possível modelar uma rede revisada; essa rede não é
escolhida automaticamente nesta entrega.

| Caso | Sítios da borda | Ramos originais | Podados | Ramos retidos | Junções retidas | Decisão |
|---|---:|---:|---:|---:|---:|---|
| Principal | 1.788 | 85 | 35 | 31 | 15 | Grade; eixo não unívoco |
| Adverso | 684 | 5 | 4 | 1 | 0 | Eixo geométrico provisório |

Após remover ramos, caminhos de grau 2 são novamente unidos: o número de ramos
retidos não é simplesmente originais menos podados. A inspeção dos mapas pelo
agente confirmou ramos que penetram alargamentos e várias rotas possíveis no
principal; não há base para escolher um caminho único entre eles. No adverso,
o ramo central acompanha a faixa estreita e sua mudança de direção. A inspeção
é **geométrica computacional**, sem alegar revisão humana independente,
validação cadastral, eixo de circulação real ou conectividade funcional.

As regiões de junção são a união de buffers pelo raio local, recortados a P,
para diagnóstico visual. Não são unidades usadas na comparação longitudinal.
Partes com junções ficam integralmente na grade, evitando dupla contagem entre
ramos e descarte seletivo de praças/alargamentos. Multipartes são avaliadas
separadamente e jamais ligadas por uma linha fictícia.

## Segmentos, seções e regiões de influência

No adverso, o ramo aceito tem **634,3199586 m**. A direção segue a ordem
lexicográfica dos extremos em E/N, sem significado ecológico de montante/jusante.

| Escala nominal | Segmentos | Comprimento da sobra final | Segmentos com suporte longitudinal suficiente |
|---|---:|---:|---:|
| 25 m | 26 | 9,319959 m | 0 |
| 50 m | 13 | 34,319959 m | 0 |
| 100 m | 7 | 34,319959 m | 0 |

Cada segmento registra início/fim no ramo, comprimento real, ID, parte,
resto curto, vizinhos e censura por recorte. A soma dos comprimentos é o ramo
completo em cada escala. Sobra não é descartada nem alongada até o nominal.

São **635 estações**: intervalos de 1 m mais o último intervalo de 0,319959 m,
representados pelos centros. A tangente usa posições a ±1 m; a seção normal
é intersectada com a parte completa. Só se mantém o componente ligado à estação,
sem saltar para outro braço que a mesma reta atravesse. O número de componentes
intersectados permanece como diagnóstico.

Regiões de influência são o Voronoi dos centros das estações, recortado por parte,
depois unido por segmento. Elas conservam toda a área da parte aceita, sem
sobreposições e com toda a largura. Não são buffers estreitos nem uma partição
pelas folhas. A discretização por estações aproxima o limite espacial do corte;
quando o passo não divide uma escala, usam-se as interseções reais na comparação.

As tampas extremas de P ficam nas regiões inicial/final, sem aumentar o comprimento
do eixo. O ramo não é extrapolado até cantos do polígono. Finais do eixo e
recorte da folha são sinalizados: não se afirma comprimento integral do corredor
nem maior lacuna completa além do domínio observado.

## Lacunas antes dos cortes e suporte desconhecido

A seção exige **≥95% de sua largura observada**. Presença candidata: fração
da largura observada coberta pela baseline≥**0,10**. Para limiar zero, o código
exige fração>0. Se falta suporte, a estação é desconhecida; não é lacuna.
A área/largura com flags semânticas é registrada, sem trocar a máscara ou reduzir
o denominador para favorecer algum método.

Resultado real do adverso:

- 597 estações desconhecidas por suporte; 8 com presença e 30 em lacuna candidata;
- 596,319959 m desconhecidos e 38 m observáveis na regra de largura completa;
- fração observada da largura: mínimo 0, mediana 0,458383, máximo 1;
- **quatro sequências candidatas de lacuna**, de 1, 1, 2 e 26 m;
- todas têm ao menos um extremo censurado por suporte desconhecido;
- nenhuma unidade de 25/50/100 m atinge 95% de comprimento observável.

As sequências foram detectadas no ramo inteiro antes dos cortes. Por exemplo,
a lacuna de 26 m vai de 82 a 108 m: o corte em 100 m a divide localmente, mas o
mesmo `gap_id` conserva o comprimento do ramo e conecta segmentos vizinhos.
`ligacoes_lacunas` registra interseção local, comprimento original e censura
local/externa. Trechos desconhecidos sempre quebram sequências; não se completa
uma lacuna através de água, falta de terreno ou fora da parte. As quatro lacunas
são condicionais à máscara não validada e não são recomendações de plantio.

## Correspondências e sobreposições

Há **451 linhas de correspondência no principal e 382 no adverso**, incluindo
pares de escalas de grade, pares longitudinais onde disponíveis e grade↔influência
na mesma escala. São registrados área de interseção, área observada em comum
e pesos relativos às duas unidades. Não comparar Jaccard diretamente entre IDs
de 25 e 100 m ou entre grade e segmento de igual tamanho nominal.

Sobreposições do caso com outros corredores são explicitamente consultadas e
registradas sem dissolver corredores. Não houve interseção de área positiva com
outro corredor nos dois domínios deste piloto; isso não nega os 43 pares do
cadastro municipal. A camada permanece vazia com esquema definido.

## Verificações, custo e reprodução

Passaram **116 testes científicos** (13 novos), **25 testes do downloader com
dois subtestes** e **29 verificações dos produtos reais**. Os testes cobrem curva,
largura variável, bifurcação com alternativa em grade, multipartes, fragmentos,
resíduos, seção cruzando outro braço, suporte desconhecido, limiar zero,
lacuna cruzando corte, conservação de área, IDs, comprimentos, folha cruzada,
orçamento, congelamento de entradas, GPKG vazio e cache. Sete avisos de
depreciação Rasterio/Affine vêm dos testes de IO existentes.

A primeira regressão do downloader encontrou bloqueio de socket no sandbox;
o log foi preservado em `downloader_regressao_sandbox.log`. A execução autorizada
com o servidor HTTP local de testes passou, sem modificar o downloader.

Custos observados, um trabalhador: principal **12,25 s / 254,57 MiB RSS**;
adverso **6,93 s / 250,36 MiB RSS**. São execuções do piloto, não previsão municipal.
O cache foi confirmado nos dois casos, com mesmos produtos e novo manifesto.

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml segment --case main
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml segment --case adversarial
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa07.py
```

`--no-cache` cria uma nova execução. O cache verifica produtos e depende das
entradas vetoriais/protocolo, produtos congelados, parâmetros, código e ambiente.
Hashes dos produtos de etapa 06 são conferidos contra seu manifesto histórico;
um produto alterado provoca recusa, em vez de usar outra máscara silenciosamente.
As entradas são conferidas novamente antes de aprovar a saída. A versão do
protocolo continua 0.1.0; parâmetros aditivos e escolhas exploratórias estão
registrados nesta entrega e em D66–D74, sem alegar pré-registro retroativo.

```bash
.venv-cientifico/bin/python scripts/visualizar_unidades_etapa07.py CAMINHO/segmentacao.json --output-dir relatorios/etapa07
```

Mapas revisados:
[eixos principal](../relatorios/etapa07/eixos_unidades_main.png),
[eixo adverso](../relatorios/etapa07/eixos_unidades_adversarial.png),
[grades principal](../relatorios/etapa07/grades_multiescala_main.png),
[grades adverso](../relatorios/etapa07/grades_multiescala_adversarial.png).

APIs primárias utilizadas:
[SciPy Voronoi](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Voronoi.html)
e [Shapely Voronoi](https://shapely.readthedocs.io/en/stable/reference/shapely.voronoi_polygons.html).
As bibliotecas não validam por si a semântica do eixo, da copa ou das lacunas.

Etapa 07 concluída com alternativa em grade e limitações explícitas. Anotação
humana/adjudicação, referência externa, validação da máscara e eventual rede
longitudinal revisada no principal permanecem pendentes. Próxima etapa:
**08 — indicadores estruturais**, somente quando acionada.
