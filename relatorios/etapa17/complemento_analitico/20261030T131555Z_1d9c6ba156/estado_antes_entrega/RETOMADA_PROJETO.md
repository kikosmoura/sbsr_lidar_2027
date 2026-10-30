# Comece por aqui ao retomar o projeto

Situação conferida em **26/10/2026**: as etapas científicas/editoriais até15
foram executadas. A etapa16 é o utilitário de retomada e diagnóstico, concluído
nesta sessão. Ela não corresponde a um novo experimento ou a uma submissão.

**Produto atual:** `artigo/revisao_etapa15/manuscrito.pdf`, quatro páginas,
classificado como **rascunho com pendências**. O ponteiro é
`artigo/versao_atual.json`. Os originais da etapa14 foram preservados.

## Leitura mínima para outra conversa ou LLM

1. `docs/estado_projeto.json`: estado operacional e ponteiros reais.
2. `docs/parecer_final_etapa15.md`: conclusões sustentadas, limites e pendências.
3. `docs/diagnostico_retomada_etapa16.md`: caminhos, ambientes e testes atuais.
4. `docs/decisoes_metodologicas.md`: decisões históricas, incluindo D160–D164.
5. O pedido novo do responsável: executar somente o objetivo expressamente
   solicitado, conservando as etapas anteriores.

Quando precisar conferir a integridade, ler o manifesto mais recente
`docs/manifesto_etapa16.json` e seu diagnóstico. Documentos operacionais evoluem;
seus bytes históricos estão nos snapshots registrados, não no arquivo atual.
Uma diferença entre estados de épocas distintas não significa alteração dos
dados científicos. Uma diferença não explicada em dados/configuração/código
precisa de diagnóstico antes de recalcular ou interpretar resultados.

## Escopo científico vigente

- **v0.1.0:** piloto original, preservado.
- **v0.2.0:** proposta confirmatória com dependência de referência; não executada
  nem aprovada como amostra confirmatória.
- **v0.3.0:** execução exploratória PyCrown sem referência externa, autorizada
  pelo usuário e usada no artigo. A chave antiga `versao_protocolo` do estado
  pertence ao piloto; consultar `protocolo_ativo_para_artigo` e o ramo
  `amostra_exploratoria_pycrown` para o artigo atual.

Execução científica fonte: `20261026T034837Z_83581b7eec`. Dez corredores
propostos, dois de desenvolvimento/oito de avaliação; 30/114 unidades,
respectivamente, com meta de avaliação120 não atingida. Seleção por identidade,
sem reposição favorável. Comparação A/A+3D em grade e suporte comum; B/C
longitudinais não foram avaliados nesta amostra.

O artigo trata de mudanças de ordenação, informação estrutural descritiva e
estabilidade condicional. Não demonstra acurácia de copas/topos, melhoria de
diagnóstico, prioridade real, benefício ecológico universal ou inferência
municipal. LiDAR de2020 dentro dos perímetros disponíveis em2026 é um recorte
retrospectivo, sem causalidade sobre implantação dos corredores. Sementes e
segmentos estimados não são árvores verdadeiras. NoData continua separado de
ausência de copa detectada. Referência externa não foi fabricada nem substituída
pela concordância entre produtos do mesmo sensor.

## Arquivos e caminhos

- Projeto: `/home/s299259068/Área de Trabalho/Projetos/2026/sbsr_lidar_2027`.
- HD: `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027`.
  Atenção à grafia **sbbr** da pasta existente.
- Dados científicos: `<HD>/experimento/etapa12/v0.3.0/20261026T034837Z_83581b7eec`.
- Vetores: `files/corredor_verde/` e
  `files/quadricula_folha_mdt_mds_2020/`.
- Configuração física: `configs/terreno_congelado_etapa04.yaml`.
- Desenho ativo: `configs/amostra_pycrown_exploratoria_v0_3_0.yaml` e
  `configs/protocolo_congelado_pycrown_v0_3_0.json`.
- Ambientes: `.venv-cientifico/` e `.venv-pycrown/`; compilador/cache em
  `.tools/tectonic/`. Não reinstalar sem evidência de uma dependência alterada.
- Evidências da etapa13: `relatorios/etapa13/ultima_execucao.json`.
- Revisão/artigo: `docs/reproducao_etapa15.md`,
  `docs/matriz_editorial_etapa15.csv` e `docs/achados_etapa15.csv`.

## Comando seguro para conferir uma nova sessão

Na raiz do projeto:

```bash
.venv-cientifico/bin/python scripts/diagnosticar_retomada_etapa16.py --tests
```

O comando cria um novo diretório datado em `relatorios/etapa16/`, com JSON de
diagnóstico, comandos/subprocessos e log dos testes dirigidos. Ele não altera
estado, dados, artigo ou caches de produção. O estado desta entrega foi
registrado separadamente após a conferência. Para somente a checagem, omitir
`--tests`; `--output` aceita uma pasta nova em `relatorios/etapa16` ou `/tmp`.

O diagnóstico autentica os pacotes12–15, consulta HD/recursos, verifica os
ambientes, o CRS horizontal pelo driver real, fontes de tabelas e PDF, e procura
parciais em namespaces ativos delimitados. Não é uma auditoria integral de
todos os LAZ e não inicia processamento municipal. A disponibilidade de RAM e
disco é uma fotografia do momento; conferir novamente antes de processamento.

## Particularidades que não devem ser “corrigidas” apagando dados

Os `.prj` legados contêm uma definição TOWGS84 que faz o PyProj representar
o conjunto como BoundCRS. `to_epsg()` direto pode retornar None. O sistema
projetado nativo e o driver GeoPandas/GDAL confirmam EPSG31983; não foi aplicada
transformação. A checagem considera os dois e rejeita um datum incompatível.

A etapa15 corrigiu cache com saída ausente. A correção operacional muda o
digest/chaves futuras; o código anterior está preservado no snapshot indicado
pelo manifesto. Não forçar cache antigo ou apagar diretórios para esconder
divergências. Uma reexecução científica futura deve ter identidade própria.

Existem interrupções históricas preservadas; a execução fonte e sua retomada
posterior estão concluídas. Os ensaios descartados de equilíbrio de colunas
também não são o PDF corrente. A versão corrente preserva todas as figuras.

## Próximo passo concreto

Fechar as pendências editoriais/autorais: conferir a equivalência ao modelo
integral aceito, completar o endereço institucional solicitado no modelo e
obter revisão/aprovação do autor. Nome, afiliação e e-mail já foram fornecidos
e estão no PDF; não pedir novamente nem inventar o endereço faltante.

A ausência de referência externa permanece limite do estudo exploratório,
não uma tarefa pendente a preencher artificialmente. Não executar novo lote,
recalcular o experimento, modificar método ou submeter/publicar o artigo sem
um pedido específico. Não existe uma etapa17 planejada neste pacote.
