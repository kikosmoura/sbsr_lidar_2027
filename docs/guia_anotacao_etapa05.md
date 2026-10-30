# Guia de referência e anotação — piloto 2020

Este guia orienta pessoas a produzir referência auditável. O pacote é preparado
automaticamente; **nenhuma classe humana, inspeção de campo ou precisão foi
produzida pela automação**. A/B são posições de revisão, não identidades reais.

Janelas regulares de 20 m exigem ao menos 100 m² de contexto e 50 m² no polígono
de medição; janelas obrigatórias de alerta podem ser exceções de QA. Esses
limites operacionais evitam que uma faixa externa mínima vire amostra principal.
Não representam cálculo de poder ou mínimo ecológico.

## Abrir e preservar o material

1. Abra `anotacao_cega.qgz` no QGIS. Os marcadores de janela são IDs estáveis.
   O projeto começa com RGB derivado dos pontos e Z absoluto, sem ranking,
   máscara prevista, classe LAS ou H exibidos como proposta de verdade.
2. Localize uma janela pela tabela `janelas`, selecione seu ID e use zoom na
   seleção. A camada `contextos` delimita onde existe material do experimento;
   a janela quadrada pode incluir áreas fora desse recorte. Anote somente no
   contexto da janela. A camada `medicao` distingue o domínio científico.
3. Consulte `trabalho/tarefas.csv`: escolha sua tarefa e slot A ou B. Cada
   janela tem tarefas separadas de vegetação, altura, lacunas e prioridade.
   Nas janelas sorteadas para dupla anotação haverá A e B em cada finalidade.
4. Edite somente `trabalho/anotacoes.gpkg`, `trabalho/tarefas.csv` e, para novas
   fontes reais, `trabalho/fontes_referencia.json`. Preserve os modelos, plano,
   recortes e quadro de seleção. Faça cópia de segurança do diretório `trabalho`.

No projeto inicial, as camadas `Anotar vegetacao`, `Anotar lacunas` e
`Anotar prioridade` recebem polígonos; `Anotar altura` recebe pontos. Ao criar
uma feição, selecione `task_id`: janela/slot são preenchidos a partir da tarefa.
Confira-os. `annotation_id` recebe UUID. A geometria deve ficar dentro do
contexto; use ajuste/recorte e confira o limite, especialmente nos recortes finos.
Não altere IDs, limites ou reserva de grupos para fazer um rótulo ser aceito.

Cada janela contém:

- `mds_rgb_original.laz`: recorte real dos pontos MDS, com dimensões originais
  e campos extras de índice do ponto e da fonte. Abra como nuvem de pontos no
  QGIS para inspecionar em 3D; qualquer índice criado deve ficar junto do recorte.
- `rgb_pontos_lidar.tif`: imagem de cor do ponto mais alto em células de 0,5 m.
  **Não é ortofoto independente.** Transparência significa ausência de ponto
  naquela célula, não sombra, água ou ausência de vegetação. A conversão de
  canais uint16 para uint8 usa divisão por 257; não representa refletância calibrada.
  2020 é a época da nuvem; a origem e a data fotográfica de sua colorização
  não foram verificadas. Cor sozinha pode não sustentar um rótulo temporal de 2020.
- `ficha_cega.png`: RGB e perfis E–W/N–S de Z absoluto, sem previsão de classe.
- `pontos_altura.parquet` e `perfis_pontos.csv`: dados derivados da etapa 04
  para a segunda passagem de QA. Perfis são cortes cartesianos de ±1 m em
  torno do centro da janela, não eixos longitudinais validados.

## Passagens de interpretação e fontes

Na primeira passagem, trace a interpretação manual a partir de RGB/XYZ bruto
e, se houver, imagem externa datada apropriada. Não copie a classificação LAS
ou uma máscara calculada para os campos de referência. Registre `incerto`
quando os dados não permitirem distinguir feições. Congele/salve essa primeira
versão antes de abrir `qa_insumos.qgz`, H, classe LAS ou propostas algorítmicas.
Se mudar uma interpretação após QA, preserve a anterior e explique a mudança;
a referência alterada passa a ter dependência do algoritmo e não pode ser
usada como teste independente dele sem essa ressalva.

O QGIS permite alternar simbolização manualmente. A configuração inicial ajuda
a primeira passagem; não impede que um intérprete abra outros arquivos.
A cegagem depende de seguir o protocolo e registrar qualquer exposição.
Rankings/índices das futuras etapas não integram este pacote. Intérpretes de
prioridade não devem receber esses rankings antes de concluir a avaliação.

O catálogo inicial tem duas fontes, referentes à época observada de 2020:

| source_id | Uso | Independência |
|---|---|---|
| lidar_rgb_xyz_2020 | Interpretação manual inicial do RGB/XYZ | Pode ser independente da regra de máscara, mas é o mesmo sensor |
| terreno_derivado_2020 | Conferência de H/DTM/suporte | Dependente do algoritmo e do sensor; apenas consistência interna |

Não se localizaram automaticamente ortofotos, campo ou referência altimétrica
independente de 2020 nos insumos disponíveis. Se uma fonte real for obtida,
adicione seu registro ao catálogo, preservando os anteriores: `kind`, `path`,
`year`, `available`, `independent_algorithm`, `independent_sensor`, descrição,
data de aquisição e limitações. `year` é o ano da observação, não da criação do
arquivo derivado. Caminhos relativos são resolvidos a partir da pasta do pacote.
O arquivo deve existir e a data/procedência precisam ser verificáveis.

Tipos de fonte aceitos conforme a finalidade: `raw_lidar`, `derived_lidar`,
`orthophoto`, `field`, `independent_altimetry`, `external_priority`.
`model_prediction` nunca é referência humana. Não declare independência apenas
porque mudou o programa que calculou a mesma variável. Se a primeira passagem
foi guiada por classe/H, use fonte dependente e registre a exposição.

Campo atual ou imagem de outro ano não se convertem automaticamente em verdade
de 2020. Use `temporal_compatible=nao` ou `incerto`, documentando a diferença.
O verificador não aceita `sim` automático para fonte cujo ano difere de 2020.
Uma declaração de fonte não substitui sua auditoria científica.

## Esquema e finalidades

Campos comuns: `annotation_id`, `task_id`, `window_id`, `purpose`,
`reviewer_slot`, `state`, `observer`, `annotation_date`, `confidence`, `source_id`,
`source_year`, `temporal_compatible`, `method` e `notes`. Use data ISO
`AAAA-MM-DD`, confiança `baixa/media/alta`, método
`manual/medicao_campo/registro_externo` e estado `pendente/concluido`.
Nome/ID de intérprete deve corresponder à pessoa que efetivamente trabalhou.
Não use identidade de LLM ou observador presumido.

### Vegetação e superfícies

Trace polígonos de referência homogêneos, sem tratar a janela inteira como seu
objeto dominante. `purpose=vegetacao`; `label`:

- `arvore_copa`: projeção de copa atribuível a árvore pela interpretação, sem
  converter toda elevação em árvore ou impor a classe LAS como resposta.
- `arbusto`: vegetação arbustiva distinguível; se altura/forma não bastarem
  para diferenciar árvore baixa de arbusto, use `incerto`.
- `edificacao`: superfície de edificação/telhado identificável.
- `terreno`: superfície de solo/pavimento/terreno, sem afirmar acurácia de cota.
- `agua`: água sustentada por evidência de interpretação/fonte, nunca somente
  por ausência de retornos.
- `outra_estrutura`: poste, fiação, ponte ou estrutura não enquadrada acima;
  descreva em `notes`. Pontos altos estreitos não comprovam poste automaticamente.
- `incerto`: evidência insuficiente ou ambiguidade não resolvida.

Categorias LAS 1/2/3/4/5/6/8 e faixas de H orientaram a escolha de janelas,
**não preenchem esses rótulos**. Nem toda classe 3 é arbusto. Copas baixas/altas,
telhados, postes, sombras e água são alvos de inspeção; sua presença real ainda
precisa ser confirmada. Se algum alvo faltar, registre a lacuna, sem renomear
outro objeto ou buscar uma frequência municipal nesta seleção intencional.

### Alturas

`purpose=altura`, geometria pontual, `value_m`, `value_type` e, quando aplicável,
`vertical_reference` e `uncertainty_m`. Tipos: `altura_objeto` ou `cota_terreno`.
Uma cota exige datum/referência vertical. Registre como a medida foi obtida,
posição, objeto, época e incerteza. Medir H no mesmo LiDAR é conferência interna;
não é erro altimétrico absoluto. Apenas campo/referência altimétrica externa
adequadamente datados e independentes podem sustentar essa última avaliação.
Não preencher esses campos copiando H/DTM gerados como se fossem referência.

### Lacunas e observação

`purpose=lacunas`; `label=sem_copa_observada`, `sem_observacao`,
`sem_suporte_terreno`, `agua` ou `incerto`. Separe evidência de ausência de copa
de impossibilidade de observá-la. Não inferir recomendação de plantio, barreira
ecológica ou inadequação de um curso d'água a partir de uma lacuna.

### Objetivo de priorização

`purpose=prioridade`, nota operacional `priority_score` de 1 a 5, `criterion`
escrito antes de olhar rankings e `saw_rankings=nao/sim` declarado honestamente.
Não há meta normativa universal de altura/cobertura neste piloto. Uma nota só
tem significado à luz de seu critério e fonte independente: justificativa
institucional, avaliação externa ou outro alvo pertinente à época. Uma soma das
próprias alturas não testa a vantagem do 3D. Na ausência desse alvo, mantenha a
tarefa pendente. O catálogo atual não autoriza conclusão H3.

## Divisão espacial e dupla anotação

O treino futuro é o corredor principal. O teste futuro é o grupo inteiro do
adverso, incluindo corredores conectados por interseções, mesmo quando apenas
uma folha de CO_SE_06 é materializada. `grupos_reservados.csv` congela essa
reserva. Partes do mesmo corredor e corredores sobrepostos não devem ser
redistribuídos. `intended_use=qa` identifica janelas de alerta; seus rótulos não
entram automaticamente em treino/teste. Grupo/fold de origem continuam registrados.

Há apenas dois casos de tipologias diferentes. O adverso foi inspecionado em
QC nas etapas anteriores; reserva significa **não usar seus futuros rótulos
para ajuste supervisionado**, não alegar teste municipal jamais observado.
A amostra científica futura precisa de outros blocos/corredores apropriados.
No cenário atual, não há rótulos válidos para treinar modelo supervisionado.

25% das janelas, cobrindo os dois casos, foram reservadas para dois intérpretes.
Cada um trabalha sem ver os rótulos do outro. Para cegagem entre revisores,
faça cópias separadas do diretório `trabalho`, filtre suas tarefas e mantenha
um responsável pela união posterior. O arquivo único inicial não impede que
alguém veja edições de outro revisor; não trabalhem simultaneamente nele.

Após as duas versões serem salvas e identificadas:

1. Compare geometrias e classes A/B dentro da área efetivamente revisada,
   registrando desacordos de fronteira, classe, fonte e confiança.
2. Preserve as duas versões originais. Discuta os desacordos com fonte aberta,
   ou obtenha terceira pessoa independente se necessário.
3. Registre resolução em arquivo de adjudicação separado: IDs de A/B, decisão,
   evidência, pessoa, data e motivo. Nunca substitua silenciosamente os originais.
4. Se a divergência não puder ser resolvida, mantenha `incerto`, com área de
   incerteza explícita. Esse rótulo não entra como verdade por conveniência.

Concordância só pode ser calculada depois dessas anotações reais. Não existem
agora kappa, precisão, recall ou acurácia externa medidos neste pacote.

## Concluir uma tarefa e verificar

Salve os polígonos/pontos realmente anotados e seus campos. Uma tarefa pode ter
várias feições, mas rótulos diferentes de uma mesma revisão não podem se
sobrepor por área >0,01 m². As revisões A/B podem se sobrepor, pois são avaliações
separadas. Geometrias inválidas ou fora do contexto não são aceitas.

Quando a revisão estiver completa, atualize somente `review_state`, `observer`,
`review_date` e `notes` da linha correspondente em `trabalho/tarefas.csv`.
Preserve IDs, finalidade e slot. Para vegetação/lacunas, todo o contexto da
janela deve estar mapeado, admitindo apenas tolerância geométrica de 0,01 m²;
onde não houver referência suficiente, cubra com `incerto`. Não marque revisão
concluída por ter desenhado uma única copa. Altura/prioridade exigem ao menos
uma referência real válida para concluir; caso falte fonte, permanecem pendentes.

Execute, na raiz do projeto, substituindo o caminho do pacote:

```bash
.venv-cientifico/bin/sbsr-lidar --config configs/terreno_congelado_etapa04.yaml check-annotations --package "/CAMINHO/DO/PACOTE" --report relatorios/etapa05/anotacoes_atual.json
```

O comando distingue estrutura válida de rotulagem concluída. Incerto, ano
incompatível, fonte dependente e tarefas de QA não são convertidos em referência
elegível para o modelo. A presença formal de rótulos não garante tamanho,
representatividade ou qualidade suficientes: revisar isso antes de treinar.
Sem rótulos válidos, a etapa seguinte pode produzir somente uma baseline
exploratória documentada, sem treinamento supervisionado ou precisão/recall.

Reexecutar `reference` usa cache do material imutável e avalia o trabalho atual;
não sobrescreve as cópias editáveis. `--no-cache` cria outro pacote versionado.
O manifesto registra hashes iniciais; depois da edição, as cópias de trabalho
mudam legitimamente e são excluídas dos hashes usados para reaproveitar o material.
Arquive versões de anotações e fontes junto de cada avaliação posterior.
