# Etapa 12 — execução exploratória com PyCrown, v0.3.0

Implementação e execução em 26/10/2026, sob autorização expressa do usuário
para prosseguir sem referência externa. O gate da amostra confirmatória v0.2.0
continua pendente. Este braço mede estrutura estimada e estabilidade interna;
não mede acurácia de vegetação, árvores verdadeiras ou melhora do diagnóstico.

## Execução observada

- Execução: `20261026T034837Z_83581b7eec`.
- Dez corredores previamente selecionados: dois de desenvolvimento e oito de
  avaliação, em dez blocos provisórios de proximidade. Número de grupos
  independentes certificados: **não estabelecido**.
- 114 unidades de avaliação e
  30 de desenvolvimento selecionadas,
  meta máxima 120/30. Seleção por hash(seed=2027, ID) entre elegíveis de 50 m,
  sem usar escores ou discordância. Todas as 3121 unidades físicas
  de 25/50/100 m, inclusive exclusões, permanecem na tabela.
- 59 pares de folhas (118 arquivos) no plano de contexto de 20 m; 16 arquivos
  faltantes adquiridos em insumos_complementares. Não houve lote municipal.
- 118 fontes distintas com 345,062,484 registros declarados;
  118 visitas às fontes com 345,062,484 registros decodificados. Nesta
  seleção não houve compartilhamento de folha entre corredores. CRC dos ZIPs
  e contagem integral conferidos; contagens MDT/MDS não são réplicas independentes.
- 12 cenários por corredor, 120 segmentações; 110 pares de sensibilidade com
  interseção vetorial do suporte observado e IDs primários fixos. Unidades que
  perdem elegibilidade são informadas, sem substituir por outras favoráveis.
- Tempo da fase monitorada: 30.89 min, excluindo
  instalação, downloads prévios e hashing inicial das entradas; pico amostrado
  de RAM do processo e filhos: 1.651 GiB, orçamento
  8.0 GiB. Um trabalhador, amostragem de recursos a 1 s.
- 518 verificações de produtos aprovadas; retomada demonstrada
  nos dez casos por checkpoints, sem decodificar novamente as nuvens.

| Corredor | Papel | Área observada | Segmentos que intersectam P | Sementes em P | Manchas em P | Elegíveis 50 m | Selecionadas |
|---|---|---:|---:|---:|---:|---:|---:|
| CO_BT_05 | evaluation | 88.59% | 445 | 404 | 196 | 13 | 13 |
| CO_CL_01 | evaluation | 94.28% | 316 | 261 | 129 | 26 | 15 |
| CO_CT_01 | evaluation | 99.22% | 635 | 589 | 226 | 45 | 15 |
| CO_CT_05 | evaluation | 91.59% | 344 | 256 | 186 | 49 | 15 |
| CO_IP_05 | evaluation | 81.51% | 1749 | 1484 | 676 | 85 | 15 |
| CO_MG_02 | evaluation | 84.52% | 258 | 232 | 157 | 11 | 11 |
| CO_PA_02 | development | 90.80% | 672 | 654 | 432 | 19 | 15 |
| CO_PJ_03 | evaluation | 96.35% | 362 | 280 | 197 | 56 | 15 |
| CO_PR_02 | evaluation | 99.77% | 259 | 173 | 135 | 49 | 15 |
| CO_PR_03 | development | 99.84% | 148 | 65 | 67 | 28 | 15 |

Sementes dentro de P e segmentos que intersectam P são estimandos diferentes:
uma copa pode cruzar o limite com sua semente fora do corredor. As contagens
acima não são inventário de árvores. Áreas observadas e limites não foram
expandidos pelo halo; ele serve somente ao processamento.
O suporte observado variou de 81.51% a
99.84%; as unidades selecionadas descrevem somente
a parcela elegível, não permitem extrapolar alturas ou árvores às áreas NoData.
Os onze critérios da etapa 11 foram reavaliados em
`relatorios/etapa12/reavaliacao_criterios.csv`; o gate de referência não foi
declarado satisfeito. MDT e MDS podem compartilhar retornos; sua soma não
representa observações independentes.

**A meta de 120 unidades de avaliação não foi atingida:** faltaram 6
unidades. CO_BT_05 ofereceu 13 elegíveis e CO_MG_02 ofereceu 11, frente às 15
previstas por corredor. As seis faltantes não foram repostas por outros casos
ou por unidades abaixo dos critérios. A execução exploratória dos dez casos
foi concluída; a insuficiência amostral permanece registrada.

## Produtos para abrir no QGIS

Raiz consolidada: `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa12/v0.3.0/20261026T034837Z_83581b7eec`.

- `produtos_pycrown.gpkg`: pacote consolidado para QGIS, com copas no contexto
  e recortadas ao corredor, sementes CHM, ápices de retornos PointZ e unidades.
- `indicadores_multiescala.parquet`: unidades 25/50/100 m, I1/I4/I5/I6/I7,
  suporte, retornos, exclusões e densidade separada de sementes estimadas.
- `todas_unidades_50m.parquet` e `coorte_selecionada.parquet`: universo e amostra.
- `escores_rankings.parquet`, `concordancia_ablacao.parquet`,
  `pares_cobertura_semelhante.parquet` e `membros_top.parquet`: A/A+3D e controles.
- `sensibilidade_cenarios.parquet`: suporte, IoU da união de copas e estabilidade
  de ranks entre cenários. IoU aqui é concordância entre algoritmos, não acurácia.
- `sensibilidade_rankings_agrupada.parquet`: os 22 pares cenário/papel,
  normalizados sobre os mesmos IDs elegíveis remanescentes da coorte congelada,
  após intersectar o suporte dentro de cada corredor; sem substituir exclusões.
- `result.json` aponta para a raiz de cada corredor. Em cada raiz:
  `primary/copas_topos.gpkg` contém copas estimadas, sementes CHM e manchas;
  `primary/topos_estimados.parquet` contém também XYZ/H e identidade do retorno
  de maior elevação absoluta no segmento. `primary/labels.tif` preserva -1 sem
  suporte, 0 observado sem segmento e rótulos positivos.
- `rasters_r1_f1/` contém CHM/terreno/suporte/contagens; `qc.json` referencia a
  auditoria interna e fontes. Todos os derivados grandes estão no HD externo.
- Figuras revisáveis: `relatorios/etapa12/figuras/`. Janelas ilustrativas seguem
  a primeira unidade por hash, não a melhor aparência de segmentação.

## Comparação descritiva A × A+3D

| Coorte | n | Spearman | k top20% | Jaccard exato |
|---|---:|---:|---:|---:|
| sample_development | 30 | 0.7655 | 6 | 0.5000 |
| sample_evaluation | 114 | 0.6682 | 23 | 0.3529 |

Os métodos usam os mesmos IDs, máscara e denominadores dentro da comparação.
I4 continua contando manchas conectadas; não foi redefinido como número de
copas. I6/I7 são P95/IQR dos retornos candidatos dentro das copas estimadas,
com quantis exatos lineares. A normalização é descritiva na própria coorte;
não há treinamento preditivo. Peso zero, sinal oposto do IQR, I6 isolado e I6
duplicado foram preservados como controles. B/C longitudinais estão
indisponíveis porque eixos desta nova amostra não foram revalidados.

Na sensibilidade agrupada da avaliação, permaneceram entre
78 e 114
das 114 unidades primárias, conforme o cenário. No conjunto remanescente de
cada par, Spearman variou de 0.9313 a
0.9949, e Jaccard top20% de
0.5000 a 0.9167.
Essas faixas descrevem universos condicionais diferentes; não demonstram
estabilidade para todas as 114 unidades sob todos os cenários ao mesmo tempo.

## Método e limites

Protocolo: `docs/protocolo_pycrown_v0_3_0.md` e
`configs/protocolo_congelado_pycrown_v0_3_0.json`. PyCrown original GPLv3,
commit 3d8db4e03d82d5846ff68fc5fa9c18803d823464, preservado e conferido por hash.
O adaptador executa detecção original e os backends Numba originais em
`.venv-pycrown`, separado do ambiente científico. Não executa a pilha de IO
legada nem a correção original baseada em DSM. O retorno de maior Z é um
produto adicional explicitamente distinto da semente CHM.

H contínuo = Z absoluto − TIN de raio 5 m, sem correção geoidal adicional.
Classes 3/4/5, CHM de máximos sem suavização ou preenchimento; crescimento
PyCrown estritamente H>limiar. Janelas de 200 m normalizam os pontos, com 10 m
de terreno ao redor; o CHM é mosaificado por corredor antes de segmentar.
Um dono nominal de folha e de janela evita duplicação de borda. Em 2 m, o
raio de detecção nominal 3 m é arredondado para 4 m, explicitamente registrado.
Não existe fronteira subpixel exata de copa nesta análise em raster.

O QC interno inclui todos os registros comprimidos, headers, unidades/datum,
unicidade de IDs, fórmula H, NoData e conservação de áreas. Em até três janelas
por corredor, escolhidas por hash, faz retenção de pontos/blocos MDT e checa
costuras. Isso avalia interpolação do mesmo sensor, não acurácia altimétrica
absoluta. A comparação com user_data é somente consistência interna.

Sem referência independente não se estima omissão/comissão, erro posicional,
erro de contorno ou número real de árvores. A classificação LAS pode confundir
vegetação e estruturas; a tela de incerteza desta rota identifica classe 1 alta
e suporte, sem executar os filtros geométricos completos do piloto anterior.
Segmentação pode dividir uma copa ou juntar várias. Parâmetros alteram
detecção e áreas. Corredores estreitos e bordas têm censura registrada.
Na prévia CO_IP_05 há feições lineares altas segmentadas no contexto; sem
rótulo independente sua natureza arbórea não está confirmada. A inspeção
visual deste produto não substitui validação semântica.
Geometrias de 2026 são confrontadas a LiDAR de 2020; o estudo é retrospectivo.
Não se declara causalidade, prioridade normativa, biomassa, conectividade
funcional, significância ou inferência para toda São Paulo.

## Reprodução e retomada

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sample-pycrown --plan-only
.venv-cientifico/bin/python scripts/executar_pycrown_etapa12.py
.venv-cientifico/bin/python scripts/exportar_pycrown_etapa12.py
.venv-cientifico/bin/python scripts/verificar_etapa12.py
.venv-cientifico/bin/python scripts/consolidar_sensibilidade_pycrown_etapa12.py
.venv-cientifico/bin/python scripts/visualizar_pycrown_etapa12.py
```

Para um caso de desenvolvimento, adicionar `--case CO_PR_03`. Complementos
faltantes exigem `--download-missing`; o plano é limitado aos dez casos.
O wrapper grava um JSON por execução e preserva `relatorios/etapa12/execucao.json`
como primeira execução base. Auditoria, exportação e figuras leem esse ponteiro;
novas retomadas ficam em `ultima_execucao.json` e nos manifestos, sem substituir
o custo observado da execução base por um tempo de cache.
Reexecutar o mesmo comando confere hashes e reutiliza fontes, janelas e casos.
Cache inclui entradas, geometria, parâmetros, código e versões do ambiente;
fontes de extração/normalização e análise têm identidades separadas.

Ambiente isolado: criar com `python3.10 -m venv .venv-pycrown` e instalar usando
`.venv-pycrown/bin/python -m pip install -r relatorios/etapa12/requirements_pycrown.lock.txt`.
As fontes originais e LICENSE estão em `third_party/pycrown_upstream`.

Verificações: 183 testes científicos (15 novos PyCrown) e 25
testes do downloader com seus subtestes; relatórios em `relatorios/etapa12`.
A calibração preliminar foi preservada em `calibracao_CO_PR_03.json`; após
conferência, a consolidação passou a traduzir explicitamente os papéis em
português para os identificadores internos. Nenhuma escolha de peso, cobertura
ou raio foi ajustada para favorecer os resultados de avaliação.

Os manifestos preservam também duas interrupções controladas: correção de
campos auxiliares de elegibilidade/contagem e inclusão da geometria nominal
da grade na identidade do cache. A execução final usa o código corrigido em
todos os casos; não mistura produtos dessas tentativas com a amostra final.

Próximo passo: etapa 13, quando solicitada, pode preparar o pacote de artigo
exploratório a partir destas evidências, sem declarar validação externa.
