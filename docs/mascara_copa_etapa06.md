# Etapa 06 — Máscara candidata de copa e incerteza

Implementada e executada em 25/10/2026 nos dois domínios do piloto. Foram
preservadas a baseline e uma versão experimental de refino para H mínimo
2/3/5 m. **Nenhuma máscara está validada por rótulos humanos.** A verificação
atual da etapa 05 continua retornando zero anotações concluídas e 100 tarefas
pendentes. Não houve treinamento supervisionado, matriz de erro ou precisão/
recall/F1/IoU medidos. A etapa 07 não foi iniciada.

## Resultados e acesso

- Principal CO_BT_01_E: `20261025T184324Z_169e51b078` —
  [relatório completo](../relatorios/execucoes/20261025T184324Z_169e51b078/mascara_copa.json),
  [resumo e caminhos](../relatorios/execucoes/20261025T184324Z_169e51b078/mascara_copa.md),
  [mapas](../relatorios/etapa06/copa_main.png),
  [sensibilidade de altura](../relatorios/etapa06/sensibilidade_altura_main.png).
- Adverso CO_SE_06 ∩ 3312-431: `20261025T184450Z_36a402772a` —
  [relatório completo](../relatorios/execucoes/20261025T184450Z_36a402772a/mascara_copa.json),
  [resumo e caminhos](../relatorios/execucoes/20261025T184450Z_36a402772a/mascara_copa.md),
  [mapas](../relatorios/etapa06/copa_adversarial.png),
  [sensibilidade de altura](../relatorios/etapa06/sensibilidade_altura_adversarial.png).

Os produtos grandes ficaram no HD, em
`<dados>/experimento/etapa06/<caso>/<run_id>/`. Não houve novos downloads,
reescrita de originais, alteração de H ou edição das anotações humanas.

| Caso | Células de medição | Domínio válido comum, centros | Área observada exata em P (m²) | Sem MDS, centros | Sem terreno/H, entre observadas |
|---|---:|---:|---:|---:|---:|
| Principal | 65.817 | 65.245 | 65.233,110 | 3 | 569 |
| Adverso | 13.142 | 6.075 | 6.076,513 | 5.219 | 1.848 |

O domínio de medição principal tem 65.807,713 m²; no adverso são 13.144,745 m²
da interseção, não os 90.388,141 m² do corredor completo. O adverso possui
suporte comum somente em parte do recorte. Seus vazios não foram tratados
como ausência de árvores, água ou recomendação de plantio.

| Versão / H mínimo | Área candidata principal em P (m²) | Área candidata adverso em P (m²) |
|---|---:|---:|
| Baseline, 2 m | 38.983,948 | 852,911 |
| **Baseline, 3 m — escolha provisória** | **38.528,344** | **623,595** |
| Baseline, 5 m | 37.157,461 | 157,485 |
| Refino experimental, 2 m | 38.438,845 | 849,911 |
| Refino experimental, 3 m | 37.985,639 | 620,783 |
| Refino experimental, 5 m | 36.614,146 | 156,485 |

As áreas são interseções vetoriais exatas das células candidatas reconstruídas
em contexto com o polígono de medição. **São áreas detectadas por regras,
não cobertura arbórea validada.** Não comparar os dois casos como réplicas
equivalentes nem escolher H mínimo pelo valor mais favorável a uma narrativa.
Não foram calculados rankings, prioridades ou comparações A/B/C.

No cenário de 3 m, há 87 manchas baseline que têm área no principal e 37 no
adverso. São componentes de células, que podem reunir várias árvores ou erros;
não representam números de árvores. O refino marca 1.335/27 células de
medição como incertas, respectivamente. Essas células continuam observadas,
no mesmo denominador, e não viram ausência confirmada.

## Baseline, ocupação e suporte

O H utilizado é o produto float64 da etapa 04, calculado com TIN/5 m e sem nova
normalização. Antes de processar, os hashes dos arquivos/protocolo usados na
etapa 04 foram comparados aos atuais: um H obsoleto não pode ser ligado a um
LAZ modificado. A seleção nominal de folhas e seus índices de registros são
reutilizados; não se somam os halos duplicados de exportação.

A baseline exige pelo menos **um registro MDS** em classes **3/4/5**, com
H≥2/3/5 m conforme cenário, H finito, status de terreno válido no ponto e sem
exclusão de QC. Não é usada apenas classe 5. Terreno/edificação/classes 2/6/8
não são promovidos por altura ou cor. Classes 1 altas são auditadas separadamente.

A ocupação é atribuída à célula de 1 m que contém XY. Origem global (0,0),
EPSG:31983 e transformação são os mesmos do DTM. Células só podem receber
decisão de copa se houver observação MDS elegível, DTM válido no centro e pelo
menos um H válido em ponto da célula. Isso define o domínio comum V, fixo
entre alturas e versões. A máscara do contexto usa centros de células.

Contagens são de registros, não pulsos independentes. Não se removem duplicatas
MDS dentro de uma folha. Uma regra de um retorno evita apagar automaticamente
copas pequenas, mas é sensível à densidade. Por isso foram registrados também
os resultados de exigir dois retornos: na medição principal, H≥3 m, 38.533
células têm ≥1 e 37.336 têm ≥2; no adverso, 624/436. Essa diferença é diagnóstico
de sensibilidade, sem selecionar um cenário pela vantagem de C. Não houve
dilatação, fechamento, preenchimento de buracos ou filtro de área mínima.

Os pontos fisicamente no contexto cujo pixel tem centro fora da máscara do
contexto são contabilizados como excluídos da grade: 6.270 no principal. A
auditoria por classe usa o Parquet inteiro; as contagens da máscara e atributos
espectrais usam a convenção de grade. Os registros originais permanecem intactos.

Na auditoria integral do principal, classe 3 tem H válido entre aproximadamente
1,85 e 11,25 m; 344.048 registros do contexto atingem H≥3 m. Portanto não foi
interpretada automaticamente como arbusto. Isso tampouco comprova que toda
classe 3 seja árvore: a separação de árvores baixas, arbustos, gramíneas altas,
edificações e estruturas precisa de referência humana adequada.

### Estados e incerteza

`observabilidade.tif`:

| Código | Significado |
|---|---|
| 1 | MDS elegível, terreno de centro válido e algum H válido na célula |
| 2 | Sem observação MDS |
| 3 | Observação elegível, mas sem suporte de terreno ou H válido |
| 4 | Somente registros excluídos por QC |
| 255 | Fora do contexto |

Nas máscaras de copa, 0 significa **sem candidato detectado pela regra**, 1
significa candidato e 255 significa fora de V. No refino, 2 identifica
ambiguidade adicional. Todos os positivos ainda são candidatos não validados;
o código 1 não significa confirmação humana. `dominio_valido.tif` contém
1 em V, 0 no contexto sem V e 255 fora do contexto. Os rasters `estados_*`
distinguem candidato, ausência detectada, classificação incerta, falta de
observação, falta de terreno e somente registros excluídos.

Incerteza não é removida do denominador por conveniência. Nenhum pixel incerto
do refino vira copa aceita ou ausência conhecida. A baseline preserva suas
decisões originais com as flags correspondentes; futuras análises devem
quantificar a sensibilidade a essa incerteza.

## Refino experimental e atributos auxiliares

Os parâmetros foram registrados antes das execuções reais, como regras
operacionais exploratórias, não limites validados de árvore/telhado/poste.

Vizinhanças geométricas usam pontos com H válido≥2 m no contexto. Somente
para esses atributos, retém-se o primeiro XYZ por voxel de 0,1 m; isso reduz
multiplicidade local sem alterar as contagens/máscaras baseline. Há limite
de 2 milhões de registros antes da redução e orçamento de memória. A árvore
XY usa raio de 1,5 m, até 32 vizinhos, mínimo de 6 para PCA, em consultas de
4.096 células, com um trabalhador. Não se carrega o município inteiro.

Para autovalores ordenados λ1≤λ2≤λ3 da covariância XYZ local:

- Planaridade = (λ2−λ1)/λ3.
- Linearidade = (λ3−λ2)/λ3.
- Rugosidade = √λ1, distância RMS aproximada ao plano local.
- Dispersão XY = raiz do maior autovalor da covariância XY.

As coordenadas são transladadas localmente antes da covariância. No principal,
1.014.925 registros entraram nessa seleção, reduzidos a 996.406 voxels; 57.000
de 57.466 células consultadas tiveram geometria confiável pela regra numérica.
Isso não valida sua interpretação semântica. Raio, limite de vizinhos, geometria
de aquisição e mistura de camadas podem alterar esses atributos.

O refino transforma em **incerto (2)**:

1. Um candidato sustentado por só um registro, sem outro pixel candidato no
   entorno de 3×3 células. A consulta de vizinhança não expande a copa.
2. Conflito planar: candidato, planaridade≥0,80, rugosidade≤0,15 m e fração de
   pontos classe 6≥0,50 entre retornos H≥2 m. Não é diagnóstico confirmado de telhado.
3. Estrutura delgada candidata: linearidade≥0,90, dispersão XY≤0,50 m e fração
   de retornos únicos≥0,90. Pode confundir poste, tronco e vegetação; não é exclusão definitiva.
4. Presença de classe vegetal sem H válido em célula que tem outros retornos
   e suporte suficientes para V.
5. Célula sem candidato baseline, mas com classe 1 alta válida: possível omissão.

Classe 1 nunca é promovida automaticamente a copa. Células mantidas como copa
no refino são subconjunto da baseline; os demais casos acima são desconhecidos,
não falsos positivos demonstrados. Diferença entre H mínimo 2/5 m e geometria
insuficiente são flags diagnósticas adicionais, sem apagar por si só a copa.

Foram calculadas frações de retornos múltiplos/primeiros, brilho RGB relativo,
excesso de verde normalizado e índice auxiliar (NIR−R)/(NIR+R), ligados por
índice aos mesmos registros LAS. Denominador zero é NoData. RGB/NIR não têm
calibração de refletância nem época fotográfica da colorização demonstradas;
**nenhum limiar espectral universal foi imposto**. Atributos ficam disponíveis
para revisão/validação, não como prova independente de vegetação.

No principal, a média auxiliar NIR/R entre retornos H≥2 m foi aproximadamente
0,345 na classe 3 e 0,027 na classe 6. São descrições condicionais dos próprios
rótulos LAS e da seleção, não validação espectral ou justificativa para um
limiar de NDVI municipal. Os relatórios incluem os denominadores por classe.

## Auditoria e escolha da versão

Em H≥3 m, 978 células válidas de medição do principal e 24 do adverso têm
classe 1 alta. Destas, 791/23 não contêm candidato baseline: são locais de
possíveis omissões, sem contagem de omissões confirmadas. O principal tem
99 células de medição com hipótese de estrutura delgada; o adverso nenhuma.
Não ocorreram flags de conflito planar na medição, o que não prova ausência
de telhados/falsos positivos. Foram exportadas 300 células de QA por caso,
priorizando conflitos planar/delgado e sorteando o restante com semente 2027;
`manual_status=pendente`. O mapa integral de flags cobre também as células
não incluídas nessa amostra de inspeção, que não é amostra probabilística municipal.

As flags de `incerteza_h*.tif` são bits: 1 classe 1 alta; 2 classe vegetal sem
H válido; 4 registro candidato único isolado; 8 conflito planar/estrutura;
16 estrutura delgada; 32 sensibilidade de altura; 64 geometria insuficiente;
128 pista de classe LAS 9 (água); 256 pista de classe LAS 17 (ponte). NoData
65535 fora de V. Não se inferiu água ou ponte de vazio ou ausência dessas classes.

**A versão de análise provisória é `baseline_h3` nos dois casos.** Ela corresponde
ao cenário do protocolo e preserva classe 3 e candidatos pequenos; o refino
usa limiares ainda não validados e pode sinalizar árvores verdadeiras como
ambíguas. Não se afirma que baseline ou refino seja mais acurado. A escolha é
provisória por ausência de evidência de qualidade para substituir a baseline,
sem consultar ranking ou vantagem da configuração C.

Os campos matriz de erro, precisão, recall, F1, IoU, omissões e falsos positivos
confirmados permanecem null. A referência da etapa 05 continua intacta e
pendente. Quando houver rótulos reais, será necessário revisar qualidade,
adjudicação, treino/teste e áreas elegíveis, reportar erros por classe/contexto/
borda e o alcance intencional da amostra antes de treinar ou calcular acurácia.
Esta versão da CLI implementa regras; não executa classificador supervisionado.

Os mapas desta etapa são previsões/regras e material administrativo de QA.
Não foram inseridos no projeto cego da etapa 05. Não os mostrar aos intérpretes
antes de salvar a primeira passagem; eventual exposição deve ser registrada.

## Manchas e áreas de borda

Componentes são construídos na máscara de contexto com conectividade 8 e
identificador preservado no recorte de medição. Para evitar anéis inválidos
em conexões diagonais, polygoniza-se cada fragmento com conectividade 4 e
unem-se fragmentos do mesmo rótulo 8, admitindo MultiPolygon. Isso não modifica
pixels nem cria pontes entre células. Não se liga o corredor principal ao adverso.

Cada geometria contextual é recortada ao contexto vetorial, depois intersectada
exatamente com P. Copas externas não contribuem com sua área inteira por tocar
o corredor; contatos sem área ficam fora da camada de medição. `patch_id` é
preservado entre contexto/medição; registra-se contato com limite do contexto,
borda de P e vizinhança de suporte inválido. As manchas podem estar censuradas.

A área de centro de célula (contagem×1 m²) difere da interseção vetorial. Por
exemplo, na baseline de 3 m, o principal tem 38.533 centros candidatos e
38.528,344 m² de interseção exata. A estabilidade das áreas, monotonicidade
com H e correspondência com as geometrias foram verificadas. Essas definições
devem permanecer explícitas nas futuras unidades/indicadores; não misturar
um numerador por interseção exata com denominador por contagem de centros.

## Arquivos e reprodução

Cada diretório de execução no HD contém:

- `copa_{baseline,refinada}_h{2,3,5}_{contexto,medicao}.tif`.
- `observabilidade.tif`, `dominio_valido.tif`, `mascara_medicao.tif`,
  `estados_*`, `incerteza_h*` e rasters de contagem.
- `geometria_auxiliar.tif`, `espectral_auxiliar.tif`, `retornos_auxiliares.tif`.
- `manchas_*.tif` com rótulos dos componentes (0 sem candidato; NoData negativo).
- `mascaras_manchas.gpkg`: medição/contexto, suporte observado, manchas
  contextuais e intersectadas de cada cenário, e `celulas_qa` pendentes.
- `auditoria_classes.csv`: contagens e intervalos reais de H por classe,
  sem generalizar as distribuições ao acervo municipal.

Na raiz do projeto, com HD montado:

```bash
.venv-cientifico/bin/sbsr-lidar --config configs/terreno_congelado_etapa04.yaml canopy --case main
.venv-cientifico/bin/sbsr-lidar --config configs/terreno_congelado_etapa04.yaml canopy --case adversarial
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa06.py
```

`--no-cache` força nova execução em diretório próprio. O cache inclui arquivos
de H, fontes, configuração, código, ambiente e estado atual dos arquivos de
anotação, e verifica os produtos. Funcionou nos dois casos reais. Originais,
anotações, guias e produtos usados na etapa 04 foram reconferidos por hash.

Para renderizar mapas, use o `report` retornado pela CLI:

```bash
.venv-cientifico/bin/python scripts/visualizar_copa_etapa06.py CAMINHO/mascara_copa.json --output-dir relatorios/etapa06
```

Passaram **103 testes científicos, 25 testes do downloader com dois subtestes
e 33 verificações dos produtos reais**. Foram verificados pontos originais de
H contra contagens/máscaras, domínio comum, refinamento sem promoção de classe,
áreas/interseções, geometrias, alinhamento, monotonicidade, ausência de métricas
fictícias e cache. Testes incluem caso sem copa com observação, sem observação,
sem terreno, classe 3, exclusão de terreno/edificação, plano/coluna sintéticos,
copas cruzando bordas, conexões diagonais e H obsoleto. Os sete avisos de
depreciação Rasterio/Affine vêm dos testes anteriores de IO; não houve falha.
As referências `execucao_*.json` e logs do verificador correspondem a esta entrega.

Tempo/pico RSS dos processos: principal **24,72 s / 763,09 MiB**; adverso
**15,07 s / 428,37 MiB**. Isso não prevê custo municipal. A configuração
recebeu parâmetros aditivos da máscara, mantendo TIN/5 m e o protocolo 0.1.0.
As escolhas desta etapa são exploratórias, não pré-registro confirmatório.

As implementações usam as APIs primárias de
[NumPy para autovalores](https://numpy.org/doc/stable/reference/generated/numpy.linalg.eigvalsh.html),
[SciPy para vizinhanças](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.query.html)
e [Rasterio para formas/máscaras](https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html).
Essas bibliotecas não validam os limiares semânticos adotados no piloto.

Etapa 06 concluída no alcance de **baseline/refino exploratórios**. Validação
humana, qualidade semântica e referência externa permanecem pendentes. Próxima
etapa: **07 — segmentação multiescala**, somente quando acionada.
