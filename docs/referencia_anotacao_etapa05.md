# Etapa 05 — Preparação da referência e anotação

Preparação concluída em 25/10/2026. **Rotulagem humana pendente: zero rótulos
criados, zero tarefas assinadas e nenhuma precisão/recall calculada.** A etapa
06 não foi iniciada. O material permite iniciar o trabalho de interpretação,
sem pressupor que esse trabalho já tenha sido realizado.

## Abrir o pacote

Execução de referência: `20261025T181025Z_131eb041f1`.

- [Projeto QGIS para primeira passagem](</media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa05/20261025T181025Z_131eb041f1/anotacao_cega.qgz>).
- [Projeto de QA dos insumos](</media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa05/20261025T181025Z_131eb041f1/qa_insumos.qgz>), para consulta após salvar a primeira interpretação.
- [Guia de anotação](guia_anotacao_etapa05.md), também copiado para `GUIA_ANOTACAO.md` no pacote.
- [Relatório da execução](../relatorios/execucoes/20261025T181025Z_131eb041f1/referencia.json),
  [verificações dos produtos](../relatorios/etapa05/verificacoes.json) e
  [mapa administrativo das janelas](../relatorios/etapa05/plano_janelas.png).

Pasta: `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa05/20261025T181025Z_131eb041f1`.

O QGIS 3.22.4 instalado gerou e reabriu os dois projetos: 26 camadas válidas no
projeto de primeira passagem e 30 no de QA. Essa verificação é de arquivo/
provedor, não inspeção humana ou validação da classificação.

## Seleção e divisão espacial

| Caso | Janelas candidatas | Elegíveis por área | Selecionadas | Uso futuro fora de QA | QA |
|---|---:|---:|---:|---:|---:|
| CO_BT_01_E, principal | 353 | 225 | 12 | 10 treino | 2 |
| CO_SE_06 ∩ 3312-431, adverso | 113 | 58 | 8 | 5 teste | 3 |

As janelas são células de 20×20 m alinhadas à origem global da configuração.
Seu domínio efetivo é a interseção com o contexto já preparado. Células com
menos de 1 m² de contexto foram excluídas do quadro. A revisão do primeiro mapa
revelou seleção excessiva de franjas externas. Antes de qualquer rótulo humano,
fixou-se que janelas regulares exigem pelo menos 100 m² de contexto e 50 m² de
medição (25%/12,5% da janela). Somente janelas obrigatórias de alerta podem ser
exceções de QA; uma delas tem 12,40 m² na medição. Esses mínimos operacionais
não são cálculo de poder ou limiares ecológicos. O quadro conserva também as
candidatas rejeitadas e seu motivo de elegibilidade. `amostras_administracao.csv`
registra ambas as áreas. Referência fora da medição serve a desenvolvimento/QA;
futuras métricas devem usar o domínio e suporte comuns definidos para a avaliação.

A seleção é **intencional**, combinando cobertura de proxies e dispersão
espacial, com desempates por semente 2027 no principal e 2028 no adverso.
Todas as cinco janelas que contêm H<−1 m foram incluídas obrigatoriamente como
QA: os 11 pontos do principal e os 3 do adverso estão nos recortes.
Não há probabilidades marginais de inclusão calculadas: o campo correspondente
fica ausente/null, sem pesos municipais ou alegação de representatividade.
Os IDs dependem de corredor, CRS, tamanho e coordenadas da célula; não do run_id.

Os 15 proxies disponíveis em cada caso foram cobertos: presença das classes
LAS 1/2/3/4/5/6/8, H baixo (0,25≤H<2 m), H alto (H≥20 m), alertas negativos,
células sem retorno, terreno inválido, borda e densidades nos quartis extremos.
Esses atributos constam apenas do quadro administrativo. **Não são rótulos
humanos nem limiares ecológicos.** Não há garantia de que todas as classes
semânticas existam, ou de equilíbrio por classe em cada divisão de uso.

| Alvo semântico | Material/proxy disponível | Situação da referência |
|---|---|---|
| Copas baixas/altas e arbustos | Classes/H candidatos, RGB/XYZ e perfis reais | Presença/tipo ainda não confirmados por pessoa |
| Telhados e postes | Classes 1/6, estrutura em XYZ e RGB | Não confirmados; poste não é inferido de altura isolada |
| Água e sombras | Retornos/suporte/RGB para inspeção | Não confirmados; vazio/escuro não prova água/sombra |
| Solo | Classes 2/8 e geometria | Não confirmado como rótulo manual ou cota externa |
| Bordas, densidade e falta de suporte | Geometria e contagens dos próprios dados | Propriedades quantitativas de seleção/QC, não verdade de vegetação |

Os 114 corredores foram agrupados por componentes conexos das interseções
geométricas, inclusive contatos. O principal constitui um grupo unitário.
O grupo do adverso tem **14 corredores**, todos reservados para teste futuro;
os 99 corredores restantes ficam sem atribuição. A lista está em
`grupos_reservados.csv`. Essa reserva documental não processou os outros
corredores nem ampliou as cinco folhas do piloto. Partes do mesmo corredor e
corredores sobrepostos não podem mudar de divisão posteriormente.

Há só um corredor de treino e um caso adverso de outra tipologia. Ambos já
foram inspecionados em QC. A divisão impede usar os futuros rótulos de teste
no ajuste supervisionado; **não constitui teste municipal intocado ou desenho
balanceado para inferência**. A amostra científica futura precisará de outros
blocos/corredores e controle de dependência.

## Material real e campos pendentes

Foram recortados **109.007 registros MDS**, preservando coordenadas, classes,
cores e demais dimensões LAS originais. Campos extras identificam índice do
ponto e fonte. Os recortes LAZ e Parquet têm contagens e XYZ/classe consistentes.
Não foram alterados dados originais, shapefiles ou produtos da etapa 04.

Cada janela contém LAZ, Parquet de H, RGB derivado dos pontos, perfis CSV e ficha
PNG. O RGB usa o ponto mais alto por célula de 0,5 m; transparência significa
falta de ponto, e não deve ser preenchida mentalmente com uma classe. Ele é
do mesmo sensor, **não ortofoto independente nem refletância calibrada**.
2020 identifica a época da nuvem; a origem/data fotográfica da colorização RGB
não foi validada nesta etapa. Avaliar essa limitação ao declarar compatibilidade
temporal de uma interpretação baseada em cor.

O inventário pesquisou `files/`, `MDS_2020/` e `MDT_2020/`: não encontrou imagens
externas locais. Não foi demonstrada inexistência dessas fontes no portal ou
em outros acervos, nem se baixou material adicional. Ortofotos pertinentes,
campo de 2020, referência altimétrica e alvo independente de prioridade seguem
ausentes/não verificados. Campo atual não representa automaticamente 2020.

Arquivos principais:

- `amostras.gpkg`: janelas, contextos e porções de medição; tabela pública sem
  proxies de classe/H, fold ou critérios de seleção.
- `quadro_amostral.gpkg` e `amostras_administracao.csv`: quadro completo e
  seleção com métricas/proxies, para auditoria administrativa.
- `plano_referencia.json`, `integridade_plano.json`, `fontes_lidar.json`:
  reserva, IDs/tarefas e procedência/hashes.
- `modelo_anotacoes.gpkg`: quatro camadas tipadas vazias — vegetação, altura,
  lacunas e prioridade; `modelo_tarefas.csv`, `modelo_fontes_referencia.json`
  e `anotacao.schema.json` completam os modelos.
- `trabalho/anotacoes.gpkg`, `trabalho/tarefas.csv`,
  `trabalho/fontes_referencia.json`: cópias destinadas à edição humana.
- `janelas/<window_id>/`: `mds_rgb_original.laz`, `pontos_altura.parquet`,
  `rgb_pontos_lidar.tif`, `perfis_pontos.csv` e `ficha_cega.png`.

São **100 tarefas**: 20 janelas × quatro finalidades para o slot A, mais quatro
finalidades para o slot B nas **cinco janelas (25%)** de dupla anotação, sorteadas
com semente 2032 e presença dos dois casos. Os nomes reais de intérpretes, datas,
confiança, rótulos e valores de referência não foram inventados. Os sete rótulos
de vegetação previstos são árvore/copa, arbusto, edificação, terreno, água,
outra estrutura e incerto; a geometria deve ser desenhada por uma pessoa.

As quatro finalidades não se substituem: interpretação de vegetação pode usar
fonte do mesmo sensor, com limitação explícita; H/DTM não validam sua própria
acurácia absoluta; lacunas distinguem observação de ausência de copa; prioridade
demanda critério/alvo próprio, não uma combinação das próprias alturas.
Sem esse alvo independente, H3 permanece não testada.

O projeto inicial não carrega rankings, H, classes LAS ou quadro de seleção;
o de QA é separado. A cegagem é uma regra de trabalho, não controle de acesso:
arquivos brutos ainda contêm classes e podem ser abertos pelo intérprete.
A dupla anotação exige cópias de trabalho separadas, avaliadores distintos e
adjudicação documentada, preservando A/B. O guia descreve esse procedimento.
O verificador estrutural não substitui a revisão de qualidade/adjudicação
antes de qualquer uso supervisionado ou estimativa de concordância.

## Comandos e verificações

Na raiz, com o HD montado:

```bash
.venv-cientifico/bin/sbsr-lidar --config configs/terreno_congelado_etapa04.yaml reference
.venv-cientifico/bin/sbsr-lidar --config configs/terreno_congelado_etapa04.yaml check-annotations --package "/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa05/20261025T181025Z_131eb041f1" --report relatorios/etapa05/anotacoes_atual.json
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa05.py
```

O verificador de anotações exige fonte real catalogada, geometria válida dentro
do contexto, finalidade/slot/ID coerentes e metadados de interpretação. Rejeita
previsões como verdade, ano automaticamente compatível quando diferente de
2020, fontes/booleanos inválidos, identidade automática, sobreposições
conflitantes na mesma revisão e a mesma pessoa nos dois slots. Revisão assinada
de vegetação/lacunas exige mapear todo o contexto, admitindo incerto onde
necessário. `incerto`, QA, época incompatível e fonte dependente não habilitam
automaticamente referência de treino/teste ou acurácia externa.

Estrutura válida não significa revisão concluída. O pacote atual retorna
`pending_tasks=100`, `completed_annotations=0`,
`supervised_training_allowed=false`, referências externas de altura/prioridade
=0 e `precision_recall_computed=false`. A preparação está concluída com esses
campos pendentes, como previsto no roteiro.

Cache foi demonstrado sem reconstruir recortes. As cópias editáveis não integram
seus hashes; a avaliação corrente é salva em um novo relatório local. Nenhuma
edição humana é sobrescrita ao retomar. `--no-cache` ou mudança de parâmetros/
código cria outro pacote. O pacote inicial `20261025T175607Z_bc94194c1a` foi
preservado, assim como a versão intermediária `20261025T180109Z_5040d8d38b`.
A referência acima inclui validação de fontes estrita e a revisão geométrica
das janelas. O QGIS acrescenta metadados internos no primeiro acesso
ao GPKG; o selo do plano foi criado após gerar/reabrir os projetos.

Passaram **93 testes científicos, 25 testes do downloader com dois subtestes
e 25 verificações de produtos reais**. As últimas checaram contagens/XYZ/classe
dos recortes, 60 pontos diretamente nos arquivos originais (incluindo RGB/NIR),
ocupação do alfa RGB, perfis, geometria, reserva dos grupos, cobertura dos
14 alertas, vazio das camadas humanas, cache e fontes dos projetos QGIS.
Há sete avisos de depreciação Rasterio/Affine nos testes; não houve falha.
O script de verificação lê referências e logs desta entrega: atualizar
`relatorios/etapa05/execucao.json` se for auditada outra entrega.

Tempo/pico RSS do processo científico principal: **24,27 s / 567,79 MiB**.
O tempo inclui a geração QGIS, mas o RSS não soma o pico do subprocesso QGIS.
Não inclui tempo de interpretação humana ou estima custo municipal. Os arquivos grandes e
projetos ficaram no HD, não no disco interno.

A configuração recebeu somente parâmetros aditivos da referência; TIN/5 m e
os parâmetros científicos anteriores foram preservados. Estado, decisões e
manifesto separam preparação de rotulagem. A etapa 06 poderá produzir apenas
baseline exploratória enquanto faltarem rótulos válidos; não treinar modelo
supervisionado nem reportar precisão/recall fictícios. Ela depende de novo
acionamento do usuário.

As opções de formulários/estilo seguem as funcionalidades do
[QGIS](https://docs.qgis.org/3.40/en/docs/user_manual/working_with_vector/vector_properties.html),
verificadas no QGIS local. As regras de anotação e independência são decisões
metodológicas deste projeto.
