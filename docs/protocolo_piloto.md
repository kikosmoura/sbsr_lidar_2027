# Protocolo do piloto — estrutura arbórea 2D/3D

Versão **0.1.0**, definida em **25/10/2026**, etapa **01**.
Situação: **protocolo exploratório; piloto computacional ainda não executado**.
Alterações posteriores exigem registro em `decisoes_metodologicas.md` e nova
versão dos produtos afetados. Este documento não é pré-registro de resultados
nem protocolo confirmatório congelado da futura amostra científica.

## 1. Pergunta, população e limites

Pergunta: **quais informações de altura e distribuição vertical acrescentam à
cobertura/fragmentação 2D, e como essa inclusão altera a estabilidade de
prioridades estruturais relativas, mantendo máscara e unidades comuns?**

Objeto: vegetação representada pelo LiDAR de 2020 nos perímetros de corredores
da camada municipal disponível em 2026. O cadastro atual não descreve, por si,
implantação ou condição de manutenção em 2020.

O piloto testa métodos e qualidade em um corredor. Não estima valores municipais,
não compara estatisticamente existentes versus propostos e não demonstra efeitos
do planejamento, conectividade funcional ou viabilidade de plantio.

**Déficit operacional:** contraste relativo entre descritores estruturais sob
critérios explicitados. Não foi identificada meta municipal de cobertura/altura
que possa ser adotada como norma verificada. Os escores deste protocolo são
cenários exploratórios; não são diagnóstico de descumprimento de meta nem
recomendação automática de intervenção. Homogeneidade, baixa altura e água não
constituem, isoladamente, problemas ecológicos.

## 2. Hipóteses e estimandos

| ID | Hipótese/pergunta | Estimando ou evidência | Limite |
|---|---|---|---|
| H1 | Unidades de cobertura semelhante podem apresentar estrutura vertical distinta | Distribuição de diferenças de P95 e IQR entre pares com diferença de cobertura até 0,05; variabilidade residual de H condicionada ao 2D | Descritivo no piloto; não demonstra utilidade ecológica ou melhor classificação |
| H2 | Acrescentar 3D pode alterar prioridades e sua estabilidade além de simples reponderação | Spearman, deslocamentos de posição, Jaccard e frequência de prioridade; ablações e pesos comparáveis | Discordância, isoladamente, é consequência possível da construção do índice |
| H3, condicional | 3D melhora diagnóstico frente a alvo independente | Diferença de erro/desempenho A/B/C no mesmo alvo, amostra e blocos | Sem alvo externo verificado, **não será testada nem afirmada** |

H1: comparar unidades da mesma escala, elegíveis para altura, com área observada
entre metade e dobro da outra. Relatar quantidade de pares e unidades únicas;
pares que compartilham unidades não são réplicas independentes. Faixas de
cobertura de 0,10 podem apoiar gráficos, sem substituir a definição dos pares.
Modelos condicionais, se usados, são descritivos no piloto.

Resultados negativos admissíveis: pouca variação vertical além do 2D; rankings
equivalentes; alterações explicadas por pesos; C menos estável; diferenças menores
que a incerteza da máscara; ou inviabilidade de indicadores longitudinais.

## 3. Evidências de partida e inspeção desta etapa

A auditoria prévia está em `relatorios/diagnostico_2026-10-25/`. Seus números de
classes são de seis pares, não do município. A integridade integral de todo o
acervo ainda não foi demonstrada.

Nesta etapa, a releitura dos vetores confirmou 114 feições, EPSG:31983, 113
propostas e uma existente; `cd_identi0` completo e único. Foi reconfirmada a
presença dos LAZ do núcleo e do caso adverso, sem nova leitura de pontos.

| Papel | Identificador/folhas | Estado reconfirmado em 25/10/2026 |
|---|---|---|
| Principal | CO_BT_01_E, `cd_identif=128`; Polygon; 65.807,71 m² | Único EXISTENTE; `cd_corredo` e `tx_tipo_pr` nulos |
| Núcleo | 3313-333, 3313-361, 3313-363 | MDS e MDT presentes |
| Contexto de 10 m | Núcleo + 3313-324 | MDS/MDT 3313-324 ausentes na raiz original |
| Contexto de 20 m | Contexto de 10 m + 3313-362 | MDS/MDT 3313-362 ausentes na raiz original |
| Caso adverso | 3312-431, recorte de CO_SE_06 na folha | MDS/MDT presentes; corredor polinizador, não réplica do Butantã |

O atributo de extensão de 1.040 m é referência cadastral, não comprimento de eixo
já validado. Não atribuir tipo ao registro nulo do Butantã automaticamente.

## 4. Domínio, contexto e unidades

Definir **P** como polígono oficial original. O contexto principal é
**P.buffer(10 m)**, usado para interpolação e vizinhanças. As estatísticas finais
permanecem em P. Não unir corredor principal e caso adverso em um único ranking.

Para o caso adverso, usar P_adverso ∩ folha 3312-431 como domínio explícito;
excluir de inferências de comprimento completo qualquer ramo cortado pela
folha e sinalizar censura. Se um algoritmo exigir contexto não disponível,
identificar bordas sem suporte ou completar apenas as folhas necessárias.

Unidades primárias do piloto: **segmentos de 50 m**, se houver eixo revisável,
mais grade quadrada de 50 m recortada em P para alternativa/comparação A/A+3D.
Unidades de 25/100 m são sensibilidade. Uma célula de 50 m não equivale a um
segmento longitudinal de 50 m.

Preservar corredor, parte, ramo, unidade, posição inicial/final e comprimento
real. Não conectar partes separadas para obter comprimento desejado. Junções
devem ser unidades próprias ou excluídas da comparação longitudinal, com motivo.
Uma unidade pode atravessar várias folhas; folha não é unidade de inferência.

Grade raster: EPSG:31983, pixels principais de 1 m, bordas alinhadas a múltiplos
da resolução em X/Y (origem global de referência 0,0). O recorte de saída deve
ser ajustado a essa grade, e sua transformação completa registrada.

## 5. Parâmetros operacionais iniciais

Estes valores são escolhas de piloto, não limites ecológicos nem acurácias obtidas.

| Parâmetro | Principal | Sensibilidade planejada |
|---|---|---|
| Raster | 1 m | 0,5 e 2 m |
| Contexto | 10 m | 0 e 20 m, mantendo o mesmo domínio P |
| Unidade | 50 m | 25 e 100 m, com correspondência de suporte |
| Altura mínima candidata | 3 m | 2 e 5 m |
| Classes candidatas | 3/4/5 | Refinamento guiado por referência; auditar omissões em classe 1 |
| Conectividade de manchas | 8 vizinhos | 4 vizinhos |
| Estações longitudinais | 1 m | Comparação dirigida em 2 m |
| Cobertura mínima de seção para presença | 10% | Presença >0% e limiar de 25% |
| Distância máxima ao MDT | 5 m, provisória | 3 e 10 m; raio não autoriza extrapolar sem suporte |
| Leitura por bloco | 500.000 pontos | Ajustar por memória medida |
| Trabalhadores | 1 | Medir antes de usar 2 |
| Semente de amostragem | 2027 | Fixa e registrada; mudar semente é outra execução |

A escolha final de interpolador TIN/IDW será feita pelo QC da etapa 04, não pelo
ranking de C. Registrar no TIN distâncias/triângulos e proibir extrapolação
silenciosa; IDW precisa de raio e número de vizinhos explícitos. Um vizinho a
menos de 5 m, sozinho, não garante terreno correto em margem de água ou ponte.

Não usar Z como altura relativa; não aplicar nova correção geoidal sem evidência.
Classe 8 do MDT é tratada por procedência e QC. Originais permanecem inalterados.
`user_data` só é conferência de altura arredondada.

## 6. Observação, suporte e ausência de árvores

Para unidade U, seja A sua área; V o domínio observado com suporte de terreno
válido, comum aos métodos; O=área(U∩V); T=área de copa aceita em U∩V.
Registrar separadamente observação MDS e validade de terreno, para explicar a
perda decorrente da exigência de suporte comum.

Estados obrigatórios: `observado_com_vegetacao`, `observado_sem_vegetacao`,
`sem_observacao`, `sem_suporte_terreno` e `classificacao_incerta`. Água, ponte e
outras situações de interpretação são flags adicionais; não inferir água apenas
pela ausência de retornos.

Elegibilidade operacional para o ranking do piloto:

- área efetiva de U ≥ **25 m²**;
- O/A ≥ **0,95**, sem descartar silenciosamente os 5% restantes;
- para altura, T ≥ **10 m²** e pelo menos **50 retornos arbóreos válidos**;
- para B/C longitudinal, pelo menos 95% do comprimento amostrado da seção/ramo
  deve estar observável segundo regra equivalente e o eixo precisa ser válido.

São mínimos de execução do piloto, não garantias de acurácia. Registrar todas
as unidades inelegíveis; eventual revisão na etapa 11 precisa de nova versão.
Para comparar A/B/C, usar a interseção de elegibilidade e reportar a cobertura
perdida. Também apresentar os descritores A no domínio adicional, sem confundir
essa tabela com a comparação pareada.

Se a unidade observada não tem copa, I1 pode ser zero e N_manchas=0; I5/I6/I7
ficam ausentes com motivo `sem_vegetacao`. Se falta observação ou suporte, não
atribuir cobertura ou altura zero. Omissão por amostragem não está resolvida
apenas pela presença de algum retorno: qualidade da máscara permanece necessária.
Uma região explicitamente anotada como de classificação incerta deve ser
quantificada e submetida a sensibilidade de máscara; não removê-la do denominador
por conveniência nem apresentá-la como ausência confirmada. Ausência detectada
pela baseline continua condicionada à qualidade de classificação ainda a medir.

Cobertura principal: I1=T/O, acompanhada por O/A e limites geométricos
**T/A ≤ cobertura total ≤ (T+A−O)/A**. Esses limites tratam apenas área não
observada, não erros de classificação. Com O=0, I1 é indefinido.

## 7. Indicadores e estimandos fixados para o piloto

| Métrica | Definição operacional | Papel |
|---|---|---|
| I1 | T/O, mais fração observada e limites acima | Cobertura 2D principal |
| I4 | Número de manchas que intersectam a unidade por hectare observado: N/(O/10.000) | Fragmentação 2D principal, sensível a área/resolução |
| I4 auxiliares | Área das manchas e contribuição da maior mancha em T | Descrição; não adicionar peso duplicado automaticamente |
| I2 | Comprimento de estações-seções em lacuna / comprimento linear observável | Longitudinal, somente com eixo válido |
| I3_local | Maior trecho de lacuna interceptado pela unidade, em metros | Registrar cortes/censura; para escore usar I3_local/L_observável |
| I3_ramo | Comprimento completo da lacuna associada no ramo, quando conhecido | Auxiliar; pode superar o comprimento da unidade |
| I5 | Média de H dos retornos arbóreos válidos | Auxiliar, evitando redundância com I6 |
| I6 | P95 de H dos retornos arbóreos válidos | Altura 3D principal |
| I7 | P75(H)−P25(H), nos mesmos retornos de I6 | Dispersão vertical dos retornos, não volume/biomassa |

Quantis: interpolação linear, com método e versão registrados. I6/I7 descrevem
retornos ponderados pela aquisição; não são altura média por árvore ou por área
de copa. Comparar em sensibilidade a subamostragem espacial e estatísticas de
superfície por célula, com outros nomes (`H_superficie_P95`, por exemplo), sem
substituí-las silenciosamente por I6.

Manchas: reconstruir no contexto antes de recortar. Contar uma mancha por ID,
sem inflar N por dividir a mesma copa na fronteira de folhas. Se a mancha toca
o limite do contexto, sinalizar incompletude. Área de copa é a interseção com U,
nunca a área externa inteira de uma copa que apenas toca o corredor.

Seções: para estação s, calcular fração da largura observável coberta por copa.
No principal, presença se fração ≥0,10; na sensibilidade de limiar zero, presença
somente se fração >0. Estações sem suporte suficiente são desconhecidas, não
lacunas. Detectar sequências no ramo, integrar comprimentos efetivos e registrar
censura antes de atribuir I3_local/I3_ramo às unidades. Não interpolar lacunas
através de trechos desconhecidos ou multipartes desconectadas.

I8 é secundário opcional. I9/I10 ficam fora do núcleo desta versão. Árvores
individuais, volume real, biomassa e conectividade funcional não são entregas.

## 8. Comparações e escores exploratórios

Representações: **A=(I1,I4)**; **B=A+(I2,I3_local/L)**;
**C=B+(I6,I7)**. Na grade ou em eixos inválidos, comparar A/A+3D. A comparação
é de informação representada; o 2D também deriva de uma máscara LiDAR.

Apresentar primeiro valores físicos e correlações. Para rankings exploratórios,
fixar o universo elegível por domínio e escala. Definir R(x)=(posto_médio−0,5)/n,
com empates por posto médio. Variável constante recebe R=0,5, sem diferenciação
artificial. O normalizador não é transportado entre domínios sem nova declaração.

Definir D_cov=1−R(I1), D_frag=R(I4), D_gap=(R(I2)+R(I3_local/L))/2;
**S_A=(D_cov+D_frag)/2** e **S_B=(S_A+D_gap)/2**.

Não há direção ecológica comprovada para I7. Por isso, C é vetor de informação,
e seus rankings são cenários explicitamente condicionais:

- cenário V+: V+=(1−R(I6)+1−R(I7))/2, tratando baixa altura/baixa dispersão
  como maior contraste estrutural;
- cenário V−: V−=(1−R(I6)+R(I7))/2, invertendo somente a orientação de I7;
- **S_C(w)=(1−w)S_B+wV**, principal exploratório w=0,5 e V+;
- ablação A+3D: (1−w)S_A+wV; pesos w=0/0,25/0,5/0,75 e V− são sensibilidade.

V+ não afirma que dispersão maior seja melhor nem que copas homogêneas sejam
deficientes. Se a conclusão depender da orientação, a prioridade 3D é ambígua.
Testar I6 isolado como ablação de I7. Não escolher sinal/peso após observar a
discordância mais conveniente. Na fase científica, esses cenários deverão ser
confirmados ou substituídos antes da análise final, com justificativa.

Unidades sem copa detectada no domínio observado V formam um estrato separado: H permanece
indefinido; todos os métodos recebem a mesma classe exploratória de ausência de
cobertura, acima dos contrastes de unidades com copa, sem somar penalidade por
altura fictícia. Apresentar rankings condicionais entre unidades com copa e,
se necessário, uma lista conjunta por estratos, registrando empates e quotas.
Unidades com copa mas suporte de altura insuficiente não recebem essa classe.

Rankings top 10/20/30%: usar k=ceil(q·n), ordenação pelo escore e desempate apenas
operacional por ID estável. Reportar o tamanho do grupo empatado no corte e uma
sensibilidade incluindo todo o empate. Spearman usa postos médios. Não reportar
Jaccard de top-k como resultado substantivo quando k<5; nesses casos entregar
apenas descrição da lista pequena e do efeito dos empates.

Comparar comprimentos diferentes sobre suporte espacial comum; não fazer Jaccard
entre IDs de 25 m e de 100 m. Reportar frequência entre cenários como estabilidade
de decisão, não probabilidade de déficit real. Controle de dimensionalidade por
permutação/substitutas é condicionado a blocos permutáveis suficientes; no único
corredor é exploração, sem p-valor inferencial.

## 9. Validação e independência

| Objeto | Avaliação prevista | O que não demonstra |
|---|---|---|
| Máscara arbórea | Cerca de 20 janelas reais estratificadas; anotação independente da previsão, incerto permitido; separar ajuste/teste | Sem rótulos completos, não há precisão/recall medidos |
| Terreno/H | Perfis, suporte, resíduos e pontos/blocos MDT reservados | Produtos relacionados não validam acurácia absoluta |
| Lacunas | Revisão do eixo/seções e limites de sequências; distinção de água/NoData | Nem toda ausência de copa é inadequação ambiental |
| Prioridades | Ablações, estabilidade e intérpretes cegos aos escores | Concordância com as mesmas alturas não prova superioridade |

Rótulos humanos, ortofotos contemporâneas e referência altimétrica independente
permanecem pendentes/não verificados como disponíveis. Não criar rótulos de
"verdade" a partir da própria regra e depois calcular acurácia sobre eles.
Campo atual não representa automaticamente 2020. Nenhuma classificação
supervisionada será treinada sem amostra real e separação espacial.

Não haverá p-valores municipais ou intervalos inferenciais obtidos por tratar
pixels/pontos como réplicas. No piloto, relatar efeitos descritivos, erros
medidos sobre referência real e sensibilidade. A amostra independente futura
terá desenho próprio antes da comparação final.

## 10. Execução futura, conclusão e controle de mudanças

Ordem: ambiente → domínio/insumos → terreno/H → referência → máscara → unidades
→ indicadores → comparação → sensibilidade → avaliação do piloto.

Critérios de conclusão do piloto: entradas rastreáveis; suporte e NoData
documentados; máscara com avaliação real ou limitação impeditiva explicitada;
eixo revisado ou alternativa em grade; métricas verificáveis; bordas/contexto
avaliados; tempo/RAM/disco medidos; relatório de falhas; execução reproduzível.
Se algum critério científico falhar, rodar código não basta para declarar piloto
aprovado ou artigo pronto. Não alterar limiares para ocultar a falha.

A etapa 01 encerra este protocolo e os planos associados. **Não autoriza sua
execução nesta rodada nem inicia o lote municipal.** A próxima etapa acionável
é a 02, infraestrutura/ambiente, conforme a sequência solicitada pelo usuário.
