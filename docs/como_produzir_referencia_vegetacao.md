# Como produzir a referência de vegetação

A referência é um conjunto de polígonos interpretados por uma pessoa a partir
de uma fonte identificada, com data e limitações registradas. Depois de salvar
essa interpretação, comparam-se os polígonos com a máscara calculada.

Foi confirmada a existência de **ortofotos de 2020 no GeoSampa**. Elas não haviam
sido encontradas nos arquivos locais do projeto; isso não significava ausência
no portal. O catálogo oficial informa resolução espacial de 0,10 m nas áreas
urbanas e 0,20 m nas rurais. Resolução de pixel não é acurácia medida.

- [Metadados e acesso às ortofotos de 2020](https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/api/records/892c862e-f564-4b1c-a3d0-9d28052e5d58).
- [Metadados do mosaico RGB de 2020](https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/geoprodam/api/records/b0046671-e190-46a8-ba1d-19f39c5bf4c8).

## Primeiro trabalho: vegetação nas 20 janelas existentes

1. Obter as ortofotos RGB de 2020 que cobrem as janelas do piloto. O catálogo
   oficial descreve download por seleção de área/código de faixa no GeoSampa.
   Guardar os arquivos e metadados em pasta própria no HD, sem substituir MDT/MDS.
   Conferir a época da fotografia, o CRS e o alinhamento com feições estáveis.
   A data de publicação de 2022 não é o ano de aquisição da fotografia.
2. Abrir o projeto QGIS existente, com o HD montado:

   `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa05/20261025T181025Z_131eb041f1/anotacao_cega.qgz`

   Adicionar as ortofotos e localizar as janelas pela tabela `janelas`. A área
   a preencher é a camada `contextos`, que pode ser menor que o quadrado de
   20×20 m. Preservar os limites/IDs. Manter a máscara prevista, classes LAS,
   H e rankings ocultos na primeira interpretação.
3. Na camada `Anotar vegetacao`, ativar edição e desenhar polígonos homogêneos.
   Selecionar a tarefa `vegetacao` correspondente à janela/slot no formulário.
   Mapear todo o contexto, usando `incerto` onde a interpretação não for possível.
   Uma janela com árvores, telhado e pavimento precisa de polígonos para cada
   superfície; uma única classe dominante para toda a janela é insuficiente.
4. Preencher os metadados reais e salvar no arquivo de trabalho. Registrar a
   fonte em `trabalho/fontes_referencia.json`, com caminho do arquivo existente,
   ano de observação, procedência e independências verificadas. As ortofotos
   pertencem ao mesmo programa de mapeamento: origem, georreferenciamento e
   eventual fotografia usada para colorir o LiDAR podem ser compartilhados.
   Não declarar independência irrestrita por usar outro arquivo.
5. Uma segunda pessoa interpreta separadamente as cinco janelas já reservadas
   para dupla anotação, sem ver a versão da primeira. Preservar A/B, discutir os
   desacordos e registrar a resolução em arquivo separado. Uma segunda rodada
   da mesma pessoa não conta como segundo intérprete independente.
6. Executar a conferência de esquema/geometrias. Só depois calcular a comparação
   entre referência e máscara, com as áreas válidas, incertas e excluídas
   explicitadas. A conferência estrutural não calcula acurácia por si só.

| Rótulo no formulário | Significado |
|---|---|
| `arvore_copa` | Copa de árvore reconhecível |
| `arbusto` | Vegetação arbustiva distinguível |
| `edificacao` | Edificação/telhado |
| `terreno` | Solo/pavimento/superfície de terreno |
| `agua` | Água sustentada pela imagem/fonte |
| `outra_estrutura` | Estrutura identificável fora das categorias anteriores |
| `incerto` | Sombra, oclusão, dúvida ou evidência insuficiente |

Campos a conferir: `task_id`, `window_id`, `reviewer_slot`, `label`,
`observer`, `annotation_date`, `confidence`, `source_id`, `source_year`,
`temporal_compatible`, `method` e `state`. Usar a identidade de quem efetivamente
anotou, data ISO, `method=manual` quando aplicável. Só declarar compatibilidade
temporal se sustentada pela fonte. Depois de completar o contexto e salvar as
feições, assinar a tarefa correspondente em `trabalho/tarefas.csv` por meio de
`review_state`, `observer` e `review_date`, preservando os demais identificadores.

Arquivos editáveis:

```text
<pacote>/trabalho/anotacoes.gpkg
<pacote>/trabalho/tarefas.csv
<pacote>/trabalho/fontes_referencia.json
```

São **25 tarefas de vegetação**: 20 primeiras revisões e cinco segundas revisões.
O pacote possui 100 tarefas porque também inclui altura, lacunas e prioridade.
Essas outras finalidades podem permanecer pendentes quando não houver fonte;
não preencher valores ou opiniões fictícias para concluir o conjunto.

Na raiz do projeto:

```bash
.venv-cientifico/bin/python -m sbsr_lidar \
  --config configs/terreno_congelado_etapa04.yaml \
  check-annotations \
  --package "/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa05/20261025T181025Z_131eb041f1" \
  --report relatorios/referencia_vegetacao_atual.json
```

## O que essa referência permite afirmar

A interpretação da ortofoto pode avaliar identificação e delimitação visual de
copas, comissões sobre estruturas e omissões observáveis. Fotografia sozinha
não comprova altura ≥3 m, cota do terreno ou acurácia do P95. Registrar casos
de altura desconhecida/limítrofe e não tratar todo desacordo como erro da
máscara com limiar de altura. Essa limitação precisa integrar a comparação.

Após anotações reais, a avaliação deve separar ajuste de teste, inspecionar
desacordos e calcular matriz de confusão, precisão, recall, IoU e erro de
cobertura onde a referência for avaliável. `incerto` não vira ausência. As
janelas foram selecionadas intencionalmente: a qualidade medida nelas não é
automaticamente uma estimativa municipal.

As 20 janelas atuais servem ao desenvolvimento/avaliação do piloto; os casos já
foram inspecionados. O protocolo 0.2.0 propõe mais 40 janelas em novos corredores,
com desenvolvimento/avaliação separados. Campo atual ou imagens de outra época
exigem tratamento temporal próprio e não viram observação de 2020 automaticamente.

Este documento orienta a referência; não cria rótulos, não valida a máscara e
não marca a execução científica da etapa 12 como concluída. O guia detalhado
dos formulários e da adjudicação é `docs/guia_anotacao_etapa05.md`.
