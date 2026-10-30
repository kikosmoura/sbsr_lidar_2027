# Registro de decisões metodológicas

Iniciado em 25/10/2026, etapa 01, protocolo 0.1.0. As decisões abaixo fixam o
piloto exploratório. São rastreáveis, revisáveis com versão e não constituem
pré-registro retroativo. Valores propostos não são resultados medidos.

| ID | Decisão | Justificativa/evidência | Situação |
|---|---|---|---|
| D01 | Estudo retrospectivo de 2020 nos perímetros disponíveis de 2026 | Datas do LiDAR e da camada; sem desenho causal | Fixada |
| D02 | Chaves `cd_identi0`/`cd_identif` | Releitura: 114 IDs únicos; `cd_corredo` nulo no existente | Fixada |
| D03 | Butantã CO_BT_01_E como piloto técnico | Polygon único e três pares do núcleo presentes | Fixada; não é amostra municipal |
| D04 | 3312-431 como caso adverso separado | Tipologia polinizador/água e ausência local de retornos na auditoria | Fixada; não agregar como réplica equivalente |
| D05 | Medir no polígono oficial P; halo principal de 10 m | Buffer altera muito a área; contexto é necessário às vizinhanças | Fixada; falta o par 3313-324 |
| D06 | Incluir classes 3/4/5 como candidatas e auditar classe 1 | Classe 3 inclui alturas arbóreas nas amostras | Fixada; máscara depende de validação |
| D07 | Normalizar H em ponto flutuante com MDT validado | Classe 8 tem semântica contextual; `user_data` é altura inteira auxiliar | Fixada; interpolador depende do QC |
| D08 | Não aplicar outra correção geoidal sem evidência | Cabeçalhos e metadados declaram Imbituba/MAPGEO2015 | Fixada; consistência não é acurácia externa |
| D09 | Raster 1 m, H mínimo 3 m e unidade 50 m | Cenário inicial operacional do piloto | Provisória; sensibilidade pré-definida |
| D10 | Suporte comum O/A≥0,95 e área U≥25 m² | Comparabilidade e limite explícito de observação desconhecida | Mínimos operacionais; não garantem precisão |
| D11 | Altura exige área de copa≥10 m² e N de retornos≥50 | Evitar quantis baseados em suporte mínimo indefinido | Mínimos operacionais a avaliar no piloto |
| D12 | I6=P95 e I7=IQR de H dos retornos vegetais | Estimandos claros, mesma população e teste de densidade | Fixada para a versão; CHM é alternativa com outro nome |
| D13 | I4=N manchas por hectare observado, conectividade 8 | Fragmentação não pode ser contagem sem área | Fixada; testar conectividade 4 e sensibilidade de escala |
| D14 | I2/I3 apenas com eixo revisado; seção a cada 1 m, limiar 10% | Polígonos não contêm eixo; largura e censura importam | Proposta operacional; grade é alternativa |
| D15 | A/B/C e ablação A/A+3D no mesmo domínio | Evitar confundir máscara, suporte e informação adicional | Fixada |
| D16 | C é vetor; ranking condicionado a sinais/pesos exploratórios | Não há direção ecológica universal de I7 nem meta de altura | Fixada; V+/V− e pesos declarados no protocolo |
| D17 | Sem copa observada é estrato separado; H permanece indefinido | Evitar imputar H=0 e duplicar penalidade de cobertura | Fixada |
| D18 | Empates por posto médio; top-k operacional por ID e sensibilidade de empate | Reprodutibilidade sem esconder igualdade dos escores | Fixada; não interpretar Jaccard quando k<5 |
| D19 | Sem p-valores municipais/CI por reamostrar pixels do piloto | Um corredor não fornece réplicas municipais independentes | Fixada |
| D20 | Referência manual/externa real é dependência, não produto inventável | Não existem rótulos ou acurácia externa verificados | Pendente nas etapas de validação |
| D21 | I9/I10, biomassa e função ecológica fora do núcleo | Oclusão, ausência de referência e definição operacional incerta | Fixada |
| D22 | 8–12 corredores e 100–200 unidades são planejamento | Variância, autocorrelação e independência ainda não medidas | A revisar antes da amostra científica |
| D23 | Redação/submissão posteriores às evidências | Normas confirmadas; prazo não substitui qualidade | Fixada |
| D24 | Encerrar esta rodada na etapa 01 | Instrução de COMECE_AQUI e avanço uma etapa por vez | Fixada; próxima etapa 02 |

## Pendências com efeito científico

- Par 3313-324 para halo de 10 m; 3313-362 somente para cenário de 20 m.
- Ambiente persistente preparado na etapa 02; medição do consumo do piloto
  científico continua pendente. O teste pequeno não estima seu pico de RAM.
- QC do terreno e escolha TIN/IDW/raio a partir de suporte e resíduos, não rankings.
- Rótulos reais, separação de ajuste/teste e revisão do eixo/máscara.
- Alvo externo e referência pertinente a 2020 para qualquer alegação de melhora.
- Alcance de dependência e tamanho efetivo da futura amostra científica.

Essas pendências não impedem concluir a etapa documental 01. Impedem considerar
o piloto executado/validado ou o artigo empiricamente concluído.

## Regra de alteração

Cada alteração deve registrar data, versão anterior/nova, motivo, evidência,
impacto em estimandos/universo e produtos a recalcular. Preservar resultados
anteriores e distinguir escolha exploratória informada pelo piloto de escolha
congelada antes da amostra científica. Não editar o histórico da auditoria para
fazê-lo concordar com uma decisão posterior.

## Atualização da etapa 02 — 25/10/2026

Por solicitação explícita do usuário, a etapa 02 foi implementada após a conclusão
documental da etapa 01, sem alterar parâmetros do protocolo 0.1.0.

| ID | Decisão de infraestrutura | Evidência / alcance |
|---|---|---|
| D25 | Ambiente Python `.venv-cientifico/` separado do `venv/` | Dependências instaladas e congeladas; downloader e testes preservados |
| D26 | PDAL/GDAL CLI existentes, sem bindings Python PDAL | PDAL 2.3.0 e GDAL 3.4.1 verificados; drivers necessários presentes |
| D27 | Registrar GDAL próprios dos wheels | Rasterio 3.10.3/Pyogrio 3.12.4; interoperabilidade LAZ/GTiff sintética passou, sem certificar algoritmos futuros |
| D28 | YAML único validado e caminhos relativos ao arquivo | Proteção de insumos, orçamento e rejeição de duplicatas/tipos inválidos testados |
| D29 | Cache por conteúdo/configuração/código/ambiente, manifestos atômicos e histórico | Reutilização real demonstrada; corrupção, mudanças, interrupção e bloqueios testados |
| D30 | Não concluir automaticamente etapas científicas por um smoke | Estado operacional preserva `piloto_executado=false`; conclusão desta etapa revisada separadamente |
| D31 | Doctor não faz prova de escrita no HD | Acesso avaliado pelo SO; sandbox inicialmente negou, diagnóstico repetido nas permissões reais passou |
| D32 | Próxima etapa é 03, domínio/insumos | Folhas de contexto continuam ausentes; não houve download nem processamento científico nesta etapa |

Os 8 GiB de RAM e reservas de 10 GiB no HD/0,5 GiB no disco local são limites
operacionais de configuração, não medições nem metas científicas. 39 testes
científicos de infraestrutura e 25 do downloader passaram. O smoke leu 1.024
pontos do MDS 3313-333, além de seu cabeçalho, e usou apenas quatro pontos
sintéticos para o intercâmbio nativo. Não produziu DTM/H/máscara do corredor.

## Atualização da etapa 03 — 25/10/2026

Etapa acionada explicitamente pelo usuário. Parâmetros científicos e estimandos
do protocolo 0.1.0 preservados; as definições abaixo documentam o preparo/QC.

| ID | Decisão de domínio/insumos | Evidência / alcance |
|---|---|---|
| D33 | Medição principal = geometria oficial; contexto = buffer de 10 m | Geometria original preservada em GPKG; grade derivada confirmou 3313-333/361/363 + 3313-324; áreas 65.807,713 e 99.600,193 m² |
| D34 | Caso adverso = CO_SE_06 ∩ 3312-431, contexto limitado à folha | Medição de 13.144,745 m²; 793,220 m² do buffer solicitado omitidos e registrados; não representa o corredor inteiro nem réplica equivalente |
| D35 | Completar somente o par 3313-324, fora das pastas originais | Endpoints verificados por resposta binária; ZIP/LAZ com CRC/tamanho, origem e hashes; downloader original e seu histórico preservados; 3313-362 não baixada |
| D36 | Ler integralmente os dez LAZ selecionados em blocos de 500 mil | Contagens lidas/cabeçalhos/classes coincidiram; cabeçalhos, VLRs e atributos registrados por arquivo; não generalizar classes ao município |
| D37 | Mapear ocupação XY na grade de 1 m e borda interna de 2 m | Centros de células; estados retorno/apenas excluídos/sem retorno/NoData; excluir withheld, retornos inválidos e classes 7/18, preservando classe 3; isso não valida terreno/copa |
| D38 | Densidade desta etapa conta registros sem deduplicação | Há pontos fora das folhas nominais e possível multiplicidade entre arquivos; MDT/MDS não são independentes; definir política de sobreposição antes das estatísticas científicas |

As pendências históricas D05/D32 sobre 3313-324 foram resolvidas nesta etapa.
3313-362 permanece condicional ao cenário de 20 m. Suporte altimétrico, terreno,
H, rótulos reais, máscara, eixo e inferência continuam pendentes de suas etapas.
Principal MDS: 3/65.817 células de medição sem retorno; adverso: 5.219/13.142.
Esses números não distinguem água, oclusão e ausência de árvores. Não imputar
zero de altura/copa a essas células.

61 testes científicos, 25 testes do downloader com 2 subtestes e 28 verificações
dos produtos passaram. Cache real verificado nos dois casos; hashes dos insumos
reconferidos após a leitura. Artefatos e comandos estão em
`docs/dominio_insumos_etapa03.md`. A etapa 03 está concluída; o experimento
científico completo não está executado/validado. Próxima etapa 04, ainda não iniciada.

## Atualização da etapa 04 — 25/10/2026

Etapa solicitada explicitamente pelo usuário. Geração de terreno/H no piloto,
mantendo os domínios e raios do protocolo 0.1.0; sem iniciar a etapa 05.

| ID | Decisão de terreno/altura | Evidência / alcance |
|---|---|---|
| D39 | Confirmar unidades/referência por cabeçalho antes de interpolar | Dez cabeçalhos (cinco MDT e cinco MDS) com EPSG:31983, GeoKeys XY/Z=9001 e Imbituba/MAPGEO2015; offsets próprios decodificados; sem nova correção geoidal |
| D40 | Propriedade espacial pela folha nominal, desempate por código; agrupar MDT por XY | Evita multiplicidade das faixas exportadas sobrepostas; uma coluna XY múltipla agregada por mediana no principal; não remove duplicatas MDS dentro da mesma folha |
| D41 | TIN e IDW sem extrapolar e com critérios geométricos explícitos | Envoltória, distâncias aos vértices, aresta≤2r, circunraio≤r; IDW até oito vizinhos, mínimo três, potência 2 e distribuição angular; dados conhecidos exatos podem ser copiados |
| D42 | Escolher método por RMSE no suporte comum reservado, preservando raio principal de 5 m | Blocos de 10 m e pontos reservados com semente 2027; no principal TIN=0,1096 m, IDW=0,1239 m em 349 consultas comuns dos blocos; fração pequena limita generalização |
| D43 | Fixar TIN/5 m como referência exploratória desta entrega nos dois casos | Configuração derivada congelada; principal selecionado por QC e adverso fixado pelo principal; comparação 3/5/10 m preservada, sem escolher raio pelo ranking |
| D44 | H=Z absoluto−DTM contínuo(X,Y), float64; preservar classe/Z e null | Parquet por ponto ligado ao índice do LAZ; user_data somente conferência; origem e máscaras de grade mantidas; nenhuma dupla normalização ou truncamento de H |
| D45 | Preservar e sinalizar vazios, negativos/extremos e limitações de água/pontes | Em 5 m: 569/5.339 células de medição sem DTM; 11/3 alertas H<−1 m no contexto; 0/2 dentro da medição; sem referência para atribuir causa ou rotular água/pontes |
| D46 | Comparar contexto e limitar alegação de qualidade | Halo trouxe saldo de 591 células válidas no principal e 313 no adverso; reservas MDT e coincidências MDT/MDS são consistência/interpolação, nunca acurácia absoluta independente |

Os detalhes operacionais (tolerância XY de 0,001 m, conflito Z de 0,10 m,
limites de consulta/memória, flags −1/80 m e regras IDW/TIN) foram registrados
antes da execução nos parâmetros e código. São decisões de QC exploratórias,
não limiares ecológicos ou alterações nos estimandos A/B/C. A referência
`configs/terreno_congelado_etapa04.yaml` foi fixada após os resultados, sem
alegação de pré-registro.

76 testes científicos e 25 do downloader com 2 subtestes passaram; 21 verificações
dos produtos passaram, incluindo fórmula H integral, amostra de origem e cache
nos dois casos. Relatórios, mapas, perfis e comandos em
`docs/terreno_altura_etapa04.md`. A etapa 04 está concluída; a baixa fração válida
do adverso permanece explícita, assim como os alertas a revisar na etapa 05.
Referência independente, máscara e inferência continuam pendentes. O experimento
científico completo permanece não concluído.

## Atualização da etapa 05 — 25/10/2026

Preparação solicitada pelo usuário, sem produzir rótulos em nome de pessoas.
Preparação e rotulagem são estados distintos, conforme o roteiro desta etapa.

| ID | Decisão de referência/anotação | Evidência / alcance |
|---|---|---|
| D47 | Seleção intencional de 20 janelas de 20 m, 12 principal/8 adverso | Classes LAS, faixas de H, suporte, borda e densidade são proxies de seleção; probabilidades marginais desconhecidas, sem pesos municipais |
| D48 | Exigir área útil nas janelas regulares; preservar exceções de QA | Revisão do primeiro mapa revelou janelas restritas a franjas do contexto; antes de rótulos humanos, fixou-se contexto≥100 m² e medição≥50 m² (25%/12,5% da janela); não são limites ecológicos |
| D49 | Incluir obrigatoriamente as cinco janelas com H<−1 m como QA | Todos os 11/3 pontos de alerta principal/adverso ficam disponíveis para inspeção; QA conserva o grupo de origem e não vira teste/treino automaticamente |
| D50 | Reservar grupos conexos das interseções de corredores | Principal unitário para treino futuro; adverso e outros 13 corredores conectados para teste; 99 sem atribuição; nenhuma ampliação de downloads/processamento para esses outros corredores |
| D51 | IDs espaciais estáveis, recortes reais e origem por índice | LAZ preserva dimensões originais; RGB é imagem de pontos, não ortofoto; Parquet/perfis ligados à etapa 04; sem origem/classe humana presumida |
| D52 | Separar primeira passagem de interpretação e QA | Projeto inicial sem H, classe LAS, quadro administrativo ou ranking carregados; projeto de QA separado; cegagem depende de protocolo e histórico de exposição |
| D53 | Criar 100 tarefas pendentes e reservar 25% das janelas para dupla anotação | Quatro finalidades por janela para A e B em cinco janelas; slots não são intérpretes inventados; consenso/adjudicação posteriores preservam originais |
| D54 | Distinguir independência de algoritmo/sensor e compatibilidade temporal | Nenhuma imagem externa local encontrada nos insumos pesquisados; ano 2020 da nuvem não comprova época da colorização RGB; campo atual e H derivado não são verdade independente de 2020 |
| D55 | Validar campos, fonte, geometria, assinatura e divisão sem calcular acurácia fictícia | Incerto não é verdade; previsões e identidades automáticas rejeitadas; revisões completas de vegetação/lacunas mapeiam o contexto, com incerteza explícita |
| D56 | Preservar trabalho humano e limitar o avanço científico | Cópias editáveis fora dos hashes do cache, materiais/planos versionados; preparação concluída com zero rótulos; próxima etapa só pode ser baseline exploratória enquanto faltar referência válida |

O ajuste geométrico D48 decorreu de QA do quadro amostral, antes de anotações,
treinamento supervisionado ou rankings. Versões preliminares foram preservadas.
Não constitui seleção confirmatória nem pré-registro retroativo. Os parâmetros
de terreno, domínio científico e estimandos A/B/C permaneceram os mesmos.

O adverso já havia sido inspecionado em QC, portanto sua reserva diz respeito
ao ajuste supervisionado futuro, sem alegar teste municipal intocado. A
amostra científica futura precisa de novos blocos e referências adequadas.
Procedimentos de dupla anotação/adjudicação, fontes e comandos constam de
`docs/guia_anotacao_etapa05.md` e `docs/referencia_anotacao_etapa05.md`.

## Atualização da etapa 06 — 25/10/2026

Etapa acionada pelo usuário. A referência foi relida: zero anotações humanas
concluídas, 100 tarefas pendentes. A implementação, portanto, é exploratória
por regras, com qualidade semântica explicitamente pendente.

| ID | Decisão de máscara/qualidade | Evidência / alcance |
|---|---|---|
| D57 | Manter regras explícitas; não treinar nem fabricar acurácia | Referência atual continua vazia; matriz de erro, precisão/recall/F1/IoU null; fontes/anotações preservadas |
| D58 | Baseline classes 3/4/5, H válido≥2/3/5 m e ≥1 registro por célula | Classe 3 inclui H compatível com copas; terreno/edificação não promovidos por altura ou cor; mínimo de dois registros apenas diagnóstico de densidade |
| D59 | Mesmo V entre versões/alturas; separar 0 de NoData/incerto | V exige observação elegível, terreno válido no centro e algum H válido; refino 2 continua observado e não sai do denominador; 0 é ausência detectada pela regra, não confirmada |
| D60 | Geometria local limitada à janela e explicitamente parametrizada | XYZ com H≥2 m, voxels 0,1 m para atributos, raio XY 1,5 m, até 32 vizinhos e mínimo seis; contagens baseline não são reduzidas; PCA não é verdade de classe |
| D61 | Refino experimental transforma conflitos em incerto | Candidato único isolado, conflito planar/classe 6, estrutura delgada, classe vegetal sem H e possível omissão da classe 1; sem promoção automática de classe 1; RGB/NIR auxiliares sem limiar universal |
| D62 | Reconstruir manchas com contexto e recortar exatamente em P | Conectividade 8 com união de fragmentos polygonizados em 4; IDs mantidos entre contexto/medição; área externa inteira não é atribuída por toque; manchas não são árvores individuais |
| D63 | Auditar possíveis erros sem denominá-los confirmados | Em H≥3 m, 791/23 células de medição com classe 1 alta e sem candidato baseline; 300 células QA pendentes por caso; ausência de flag planar não prova ausência de telhados |
| D64 | Escolher provisoriamente baseline_h3 nos dois casos | Cenário original do protocolo, preserva candidatos pequenos/classe 3; refino ainda sem qualidade validada, logo não substitui baseline como se fosse mais acurado; nenhum ranking/C consultado |
| D65 | Concluir implementação exploratória e preservar pendência de validação | Domínio observado exato de 65.233,110/6.076,513 m² principal/adverso; falta de observação/terreno não vira ausência; próxima etapa 07 somente quando acionada |

As áreas baseline em P para 2/3/5 m foram 38.983,948/38.528,344/37.157,461 m²
no principal e 852,911/623,595/157,485 m² no adverso. São áreas candidatas
condicionadas às regras e suporte, não cobertura arbórea validada. O refino
experimental de 3 m deixa 1.335/27 células incertas na medição. Não se infere
déficit ecológico, prioridade de intervenção ou vantagem científica do 3D.

103 testes científicos, 25 testes do downloader com dois subtestes e 33
verificações dos produtos passaram. Manchas que cruzam borda, estabilidade
de área, classe 3, terreno/edificação, conexões diagonais e NoData foram
verificados; cache real funcionou nos dois casos. Relatórios e comandos em
`docs/mascara_copa_etapa06.md`. Rotulagem/adjudicação humana, referência externa
e validação da separação árvore/arbusto/estrutura continuam pendentes.

## Etapa 07 — unidades multiescala e eixos, 25/10/2026

| ID | Decisão | Evidência / alcance |
|---|---|---|
| D66 | Grade de 25/50/100 m ancorada em (0,0), com interseção exata e fragmentos separados | Conservação de P/O; IDs por corredor/parte/escala/célula/fragmento; 192/67/27 unidades principal e 59/25/10 adverso; resíduos preservados |
| D67 | Avaliar eixo por Voronoi de borda de 2 m, por parte, sem escolher rota por copa | Grafo conserva ramos/junções; contração numérica de vértices até 10⁻⁵ m; nenhuma conexão entre partes distantes |
| D68 | Uma passagem de poda terminal com comprimento≤25 m e ≤2,5×raio na junção | Bissetrizes de cantos preservadas em camada própria; fator 1,6 deixava braços oblíquos no adverso; 35/4 ramos podados principal/adverso; escolha por geometria, sem escores |
| D69 | Aceitar automaticamente somente parte com caminho aberto único, sem anéis, L≥25 m e L/largura mediana≥3 | Principal conserva 31 ramos e 15 junções: grade, B indisponível; adverso tem eixo de 634,319959 m; QC computacional/mapas, sem validação humana independente |
| D70 | Segmentar somente eixo geometricamente aceito, preservando sobras e comprimento real | Adverso: 26/13/7 segmentos de 25/50/100 m, sobras de 9,319959/34,319959/34,319959 m; regiões por Voronoi das estações, toda largura, sem corte por folha |
| D71 | Seções a cada 1 m exigem 95% de largura observada; estados desconhecidos quebram lacunas | 635 estações adverso: 597 desconhecidas, 8 presentes e 30 em lacuna candidata; nenhum segmento elegível para B; não converter falta de suporte em ausência de copa |
| D72 | Detectar sequências no ramo antes de cortar unidades e conservar IDs/censura/vizinhos | Quatro lacunas candidatas de 1/1/2/26 m, todas com censura por suporte em algum extremo; lacuna 82–108 m conserva ID ao atravessar corte de 100 m |
| D73 | Comparar escalas/famílias por área e suporte observado em comum | 451/382 linhas de correspondência principal/adverso; nenhuma comparação de Jaccard entre IDs incompatíveis; 18 unidades de grade cruzam folhas no principal |
| D74 | Prosseguir futuramente com A/A+3D em grade, mantendo B indisponível neste piloto | Principal sem rota única aceita; adverso com eixo, mas suporte longitudinal insuficiente; máscara baseline_h3 congelada e não validada; etapa 08 não iniciada |

A inspeção dos mapas confirma que o principal contém alargamentos/ramificações
que não devem ser resolvidos por uma linha arbitrária. Junções são diagnóstico
geométrico, não conectividade funcional. Não houve sobreposição com outro
corredor nos domínios selecionados; o cadastro municipal completo não foi
redefinido nem dissolvido. Os dois casos continuam separados.

116 testes científicos, 25 testes do downloader com dois subtestes e 29
verificações dos produtos reais passaram. Código, áreas, observação, IDs,
comprimentos, interseções entre escalas, cache e entradas foram conferidos.
Relatório e comandos: `docs/segmentacao_multiescala_etapa07.md`. Este resultado
conclui a implementação da etapa, não a validação da copa ou do experimento inteiro.

## Etapa 08 — indicadores físicos e suporte, 25/10/2026

| ID | Decisão | Evidência / alcance |
|---|---|---|
| D75 | Usar H, máscara baseline_h3 e unidades congelados, com hash e vínculo ancestral | Produtos 04/06/07 preservados; entradas incompatíveis são recusadas; saídas por nova execução no HD, sem rankings |
| D76 | I1=T/O com O/A, área desconhecida e limites T/A…(T+A−O)/A | Mesmo V comum; áreas exatas; suspeita semântica continua em O; limites não são acurácia nem intervalo de confiança |
| D77 | I4=N/(O/10.000), IDs contextuais de manchas com área positiva | Conectividade 8/resolução 1 m congeladas; 87/37 IDs únicos; maior mancha é somente U∩mancha; contatos sem área não contam |
| D78 | I5/I6/I7 sobre retornos vegetais H válido≥3 m classes 3/4/5, no V/copa | Média/P95/IQR exatos, interpolação linear; não CHM, altura por árvore ou média por área; limite de seis milhões de valores entre grupos |
| D79 | Conservar contagens por família/escala com posse única em fronteiras | Maior área no pixel semiaberto, empate por ID; 1.395.109/98.688 registros MDS em P e 774.284/2.621 retornos vegetais principal/adverso |
| D80 | Separar ausência detectada, NoData, falta de terreno e altura insuficiente | Cobertura pode ser zero com O>0/T=0; H/P95/IQR permanecem null; T≥10 m² e 50 retornos para altura; elegibilidade A exige A≥25 m²/O/A≥0,95 |
| D81 | Manter I2/I3 indisponíveis onde faltam eixo ou suporte e preservar diagnósticos/censuras | Nenhuma unidade real elegível B; comprimentos, IDs, posições e flags de censura/corte conservados mesmo em unidades excluídas; não substituir lacuna por área sem copa |
| D82 | Comparação futura em grade e suporte pareado, sem misturar famílias | Escala 50 m: 59/3 elegíveis A e 58/2 elegíveis A+3D principal/adverso; uma unidade principal adicional sem copa detectada é estrato separado, sem altura fictícia |
| D83 | Manter I8/I9/I10 fora do núcleo e registrar limites do estimando | Sem complexidade para completar lista; retornos ponderados pela aquisição/oclusão; nenhuma inferência de biomassa, volume ou conectividade funcional |
| D84 | Concluir implementação/execução exploratória com validação pendente | 426 linhas/114 colunas, GeoParquet/CSV/dicionário, 134 testes científicos, 25 do downloader e 44 verificações reais; etapa 09 não iniciada |

As áreas e razões de cobertura agregadas foram conservadas entre escalas:
principal O=65.233,110/T=38.528,344 m² (T/O=59,06% com O/P=99,13%);
adverso O=6.076,513/T=623,595 m² (T/O=10,26% com O/P=46,23%). Não são
coberturas validadas do polígono inteiro nem estimativas municipais.

Na grade de 50 m, o P95 dos retornos nas unidades elegíveis variou de
7,20–23,62 m no principal e 10,85–11,47 m nas duas unidades do adverso.
Esses descritores não demonstram vantagem do 3D ou prioridade ecológica.
Quantis e contagens foram reavaliados diretamente na fonte em 14 unidades;
demais áreas/manchas/suportes/censuras foram verificados em todas as linhas.
Documentação e reprodução: `docs/indicadores_estruturais_etapa08.md`.

## Etapa 09 — comparação descritiva 2D/3D, 25/10/2026

| ID | Decisão | Evidência / alcance |
|---|---|---|
| D85 | Fixar coortes por elegibilidade e mesma origem 04/06/07/08, separando caso/família/escala | Grade 50 m: 58/2 unidades pareadas principal/adverso; razões de exclusão e áreas preservadas; adicionais de A não entram apenas em um método |
| D86 | Normalizar por R=(posto_médio−0,5)/n, com constantes em 0,5 | Mesmo n entre variantes; empates numéricos em 12 casas somente nos escores; indicadores brutos preservados; nenhuma diferenciação inventada em variável constante |
| D87 | Executar A/A+3D em grade sem renomear ablação como C | Fórmulas A/B/C implementadas/testadas, porém B/C indisponíveis por eixo/suporte longitudinal; sem lacuna artificial por área |
| D88 | Manter pesos 0/0,25/0,5/0,75, V+/V− e ablação I6 fixos | I5 auxiliar, não peso duplicado de I6; duplicar I6 reproduz I6 isolado; peso zero reproduz A; nenhum vencedor escolhido por discordância |
| D89 | Estrato sem copa detectada comum e superior, com H/escore null | No principal/50 m, lista condicional n=58 e lista conjunta n=59 reportadas separadamente; ausência não é dupla penalização por altura falsa |
| D90 | Top 10/20/30% com ceil(q·n), ID operacional e inclusão completa dos empates | Spearman sem p-valores, null para n<3/constante; Jaccard null com k<5; principal/50 m: rho=0,8734, J=0,50 e inclusivo=0,5625 |
| D91 | Quantificar H1 por pares de cobertura≤0,05 e razão de O≤2 | Principal/50 m: 76 pares/50 unidades únicas, mediana da diferença absoluta de P95=2,7304 m; pares compartilham unidades e não são réplicas independentes |
| D92 | Não executar previsão ou permutação sem referência/desenho suficiente | Zero alvo independente, um grupo de corredores por caso; células geométricas de 200 m não certificam permutabilidade; nenhum ganho de acurácia/p-valor |
| D93 | Reportar dependência de pesos/sinais e redundância, sem atribuir benefício ecológico | Principal/50 m: rho(I5,I6)=0,9297 e rho(I6,I7)=0,8908; V−/w0,5 resulta rho=0,9795 com A; adverso tem A constante e n insuficiente |
| D94 | Concluir comparação exploratória e preservar validação pendente | Tabelas, escores, mapas, 154 testes científicos, 25 do downloader e 49 verificações reais; máscara não validada e etapa 10 não iniciada |

No principal/50 m, oito das 12 unidades dos conjuntos superiores são comuns,
quatro saem e quatro entram. O deslocamento absoluto médio é 6,7586 postos.
A lista inclusiva no corte de A+3D tem 13 unidades. Lista conjunta com ausência
detectada tem outro universo/quota e é descrita separadamente (J=0,4118).
São contrastes numéricos sob escolhas explícitas, não métodos vencedores.

O caso adverso é insuficiente para conclusão substantiva: na grade de 50 m
há duas unidades, A empatado e nenhum par H1 admissível. A ausência de mudança
entre postos empatados não demonstra equivalência científica na população.
Referência humana, máscara e alvo externo continuam pendentes. Relatório:
`docs/comparacao_2d_3d_etapa09.md`.

## Etapa 10 — sensibilidade e auditoria de validação, 25/10/2026

| ID | Decisão | Evidência / alcance |
|---|---|---|
| D95 | Preservar o cenário 1 m/H≥3 m/halo10/TIN5/conectividade8 e suas fontes | Replay de máscara/observação idêntico e de indicadores/rankings contra 06/08/09; original principal/50 m rho A/A+3D=0,8733955, J=0,50 |
| D96 | Executar 30 cenários por caso, sem fatorial completo | Resolução, altura, contexto, interpolação, componentes, refino/limite superior, seis retenções acopladas e seis somente H, primeiros retornos e duas interações; grades 25/50/100 m em todos |
| D97 | Separar contexto de expansão de P | Halo0/10/20 conserva P; P.buffer5/10 muda população/IDs e não entra nas frequências físicas; adverso continua recortado à folha 3312-431 |
| D98 | Extrair uma vez o ROI máximo limitado e obter somente o par faltante 3313-362 | Propriedade por folha nominal, chunk, QC/datum, vértices e caches H reutilizados; buffers sucessivos incluídos nos arcos do ROI; um trabalhador e RSS principal 3.584 GiB <8 GiB |
| D99 | Recalcular ambos os lados em V comum e IDs elegíveis comuns | Critérios de 95% de observação/25 m² de unidade/10 m² de copa/50 registros preservados; linhas/pontos isolados não criam superfície; componentes do contexto conservam identidade |
| D100 | Congelar a regra de propriedade de pontos na grade canônica de 1 m | Mesma convenção de borda em 0,5/1/2 m; áreas poligonais exatas e quantis diretamente dos retornos; verificação XY independente em unidades reais |
| D101 | Frequências somente em ensembles de V e coorte fixos | Global de 28 cenários, por eixo e dez receitas distintas separados; sem controles duplicados votando; frequências operacionais/inclusivas e amplitudes empíricas não são probabilidades/IC |
| D102 | Preservar perdas de suporte e coortes globais pequenas/vazias | Principal: 5/1/0 unidades globais elegíveis em 25/50/100 m; adverso: 0/0/0. IDW/50 m conserva apenas 17 unidades nativas no principal, contra 58 no cenário original |
| D103 | Comparar escalas por transferência de percentis e pegadas no suporte espacial W | Correlação ponderada por área e Jaccard de área; nenhum Jaccard de IDs de grades diferentes; A+3D 25→100 m: J de área=0,13714 |
| D104 | Subamostrar registros por hash da identidade e sementes 2027/28/29 | Retenções 1/2 e 1/4 aninhadas por semente e invariantes a chunks; modos acoplado/H congelado separados; primeiros retornos mudam estimando, sem simular pulso/linha de voo |
| D105 | Quantificar densidade sem inferência causal ou volume fictício | H-only 1/4/s2027/principal50: mediana abs. ΔP95=0,04585 m, máximo=2,32024 m; primeiros retornos: mediana ΔP95=+0,27011 m; I9/volume proxy não definido |
| D106 | Testar agregação fina→grossa sem impor equivalência | 0,5→2 m: diferenças de contagem/copa/validade principal=0/108/111 células e adverso=1/5/135; borda do contexto pode alterar população admitida; sem média dos P95 finos |
| D107 | Explicar mudança por decomposição aritmética, pesos e empates | I4 domina a contribuição média absoluta nos eixos resolução/retenção acoplada; dez receitas/50 m: quatro unidades sempre no topo, 15 ocasionalmente, 39 nunca, amplitude máxima de 33 postos; sem importância causal ou vencedor escolhido |
| D108 | Auditar máscara, terreno, lacunas e rankings como objetos distintos | Zero rótulos humanos/alvo independente; terreno só QC interno MDT de 04; um grupo de corredor/caso, sem IC, bootstrap de pixels ou p-valores; anotações de teste intactas |
| D109 | Não fabricar grafos/lacunas ou B/C para testar distâncias | 0/2/5 m não aplicados por falta de métrica operacional e suporte longitudinal; lacunas censuradas permanecem desconhecidas; A+3D continua ablação |
| D110 | Concluir execução exploratória, mantendo validação empírica incompleta por dependência | 60 cenários, cache comprovado nos dois casos, 162 testes científicos/25 downloader/2 subtestes e verificações reais; originais preservados, máscara não validada, etapa 11 não iniciada |

Os resultados e limites estão em `docs/sensibilidade_validacao_etapa10.md`,
com protocolo em `docs/metodologia_sensibilidade_etapa10.json` e produtos
rastreáveis no manifesto da etapa. Correlação alta entre rankings não garante
permanência do conjunto superior: com halo20/principal50, rho=0,999954,
J operacional=0,846154 e inclusivo=0,923077. Critérios de suporte e receitas
não foram selecionados para maximizar discordância ou vantagem do 3D.

## Etapa 11 — avaliação crítica e continuação condicionada, 25/10/2026

| ID | Decisão | Evidência / alcance |
|---|---|---|
| D111 | Reconstruir a avaliação das fontes selecionadas, não de resumos narrativos | Manifestos 01–10, 15 execuções científicas, 1.177 registros de fonte conferidos; parâmetros, comandos, tempos, picos RSS e bytes em tabelas; arquivos mutáveis de anotação preservados |
| D112 | Classificar a continuação como dependente de referência complementar | Piloto técnico executável; interpretação descritiva condicional; amostra para artigo não demonstrada. Separação árvores/estruturas sem precisão/recall/IoU medidos, zero rótulos concluídos e nenhum alvo independente |
| D113 | Aceitar terreno somente no suporte e com QC interno explícito | TIN5: MAE nos pontos reservados válidos principal/adverso=0,02492/0,05538 m; nos blocos, cobertura válida=32,00%/28,09%. Isso não mede acurácia absoluta externa nem resolve vazios/água/pontes |
| D114 | Manter A/A+3D em grade como núcleo da proposta | Eixo principal ramificado, adverso sem suporte longitudinal; B/C e lacunas exigem outra validação. I4 sensível a componentes/resolução, I6/I7 ponderados por registros; não inferir volume, conectividade funcional ou utilidade |
| D115 | Congelar proposta pós-piloto v0.2.0, mantendo o piloto v0.1.0 | YAML de planejamento, snapshot JSON com vetores/configuração/IDs e protocolo humano; congelamento anterior a novos rankings, sem pré-registro retroativo. Configuração ativa do piloto não foi substituída |
| D116 | Restringir o universo proposto e preservar exclusões | PROPOSTO/CORREDOR VERDE com ≥15 unidades geométricas potenciais de50m/área≥25m²; grupos legados e suas cadeias de proximidade excluídos. Das114 feições,22 candidatos/15 blocos potenciais a1000m; tipos polinizador/escuro não recebem meta arbórea universal |
| D117 | Separar novos papéis por bloco e usar seleção alheia ao resultado3D | Ordem por hash(semente2027,ID) em voltas por quadrantes geográficos; um candidato por bloco. Dez propostos: oito avaliação/meta120 unidades e dois desenvolvimento/meta30; suporte real ainda desconhecido, sem poder calculado |
| D118 | Pré-especificar coorte conjunta de avaliação para normalizar os escores | R por postos na mesma coorte pareada dos oito corredores; desenvolvimento excluído. Normalização difere explicitamente do piloto por caso: com15 unidades locais, top20% tem k=3 e Jaccard local seria suprimido. Não transportar normalizadores ou alegar calibração municipal |
| D119 | Exigir referência real e separação de ajuste/avaliação | Vinte janelas/100 tarefas anteriores pendentes; propor40 janelas novas, oito desenvolvimento/32 avaliação,25% de dupla anotação. Referência do próprio LiDAR não é independente do sensor; adverso já inspecionado não é teste municipal intocado |
| D120 | Tratar distância de bloco como precaução, não alcance inferido | Agrupamentos200/500/1000m por distância entre polígonos e fechamento transitivo; variograma descritivo e SD do piloto não estimam variância entre corredores/independência. Padrão descritivo, sem IC/p-valores/bootstraps de pixels; seis grupos é guarda insuficiente para provar poder |
| D121 | Separar medições observadas de envelopes heurísticos de custo | Pipeline principal/adverso=107,85/36,07s; etapa10=334,70/61,05s. Para dez propostos: modelo por área0,32–1,22h base e0,69–2,99h sensibilidade, fatores3 e hipóteses explícitos. Modelo por registros null enquanto faltam cabeçalhos; sem previsão fictícia de downloads/tempo humano |
| D122 | Planejar folhas e recursos sem adquirir/processar novos dados | Dez propostos exigem58 folhas/116 produtos,14 arquivos faltantes; só cabeçalhos dos existentes. Um trabalhador,8GiB, limites por janela e20GiB externos livres além dos derivados estimados9,58GiB e arquivos novos. Sem lote municipal |
| D123 | Registrar ajuste limitado necessário no driver da etapa12 | IDs novos explícitos, plano de folhas/halos, QC/retomada, propriedade em bordas e união de componentes entre janelas antes de I4; validar primeiro novo caso de desenvolvimento. Driver atual do piloto não é apresentado como executor da amostra |
| D124 | Distinguir invalidação científica de miss operacional de cache | Métodos/dados alterados invalidam descendentes conforme inventário; adicionar avaliação/CLI muda digest global, mas não torna falsos os produtos históricos com hashes conferidos. Versões/namespaces preservados, sem recomputação de nuvens nesta etapa |
| D125 | Concluir a avaliação mantendo condições de execução pendentes | Relatório, critérios, oito falhas/dependências com resolução/cache, protocolo, proposta/custo/mapa;168 testes científicos,25 downloader/2 subtestes e auditoria independente. Etapa12 recebe amostra_cientifica com execução condicionada a referência/QC/driver/recursos; não foi iniciada |

Decisão e evidências completas: `docs/relatorio_piloto.md`. Desenho congelado:
`docs/protocolo_amostra_v0_2_0.md` e
`configs/protocolo_congelado_amostra_v0_2_0.json`. Custos observados e estimados:
`docs/plano_custo_etapa11.md`. Metas/contagens geométricas não são amostra
executada, qualidade medida ou cálculo de poder. Alterações futuras não podem
selecionar cenário/peso que favoreça o 3D após observar os rankings de avaliação.


## Etapa 12 — nova rota exploratória autorizada, 26/10/2026

| ID | Decisão | Motivo e limite |
|---|---|---|
| D126 | Criar v0.3.0 sem referência externa por solicitação expressa | Executar estimativas e estabilidade; gate confirmatório v0.2 permanece pendente |
| D127 | Reutilizar dez corredores/blocos da proposta v0.2 | Dois desenvolvimento/oito avaliação; sem seleção por vantagem do 3D |
| D128 | Halo 20 m e somente oito pares adicionais | Comporta raios de detecção/copa; medição continua em P original |
| D129 | PyCrown por commit e ambiente isolado | Rotinas originais de detecção/Dalponte/CIRC; IO atual, GPL preservada, sem alegar pipeline legado completo |
| D130 | CHM de máximo H das classes345 sem preenchimento/suavização | Suporte, NoData e contaminação LAS explícitos; float32 no algoritmo, float64 nas alturas |
| D131 | Janelas de normalização e mosaico integral por corredor | Um dono de retorno e segmentação antes de recortar; fronteiras de janela não definem copas |
| D132 | Separar sementes CHM de retorno de maior Z absoluto | Estimandos/proveniência explícitos; sem chamar posição de topo verdadeiro |
| D133 | I4 mantém densidade de manchas | Densidade de sementes é coluna adicional; copas não equivalem a árvores verificadas |
| D134 | Congelar 12 cenários e usar suporte vetorial comum | Resolução/limiar/raios/algoritmo/densidade; raio3 em resolução2 corresponde a4 m; sem otimizar rankings |
| D135 | Hash de ID para até15 elegíveis por corredor | Preservar exclusões e eventuais faltas; grupos não certificados independentes; sem p/IC |
| D136 | QA interno de MDT e costuras em até3 janelas por hash | Mesmo sensor não substitui acurácia absoluta ou validação da máscara |
| D137 | Concluir somente o braço exploratório após auditoria e retomada | Preservar v0.1/v0.2, labels pendentes e gate externo; produtos concretos no HD |


## Etapa13 — apresentação da amostra exploratória v0.3.0

| ID | Decisão | Evidência / limite |
|---|---|---|
| D138 | Usar execução PyCrown v0.3.0 como fonte imutável | Amostra exploratória real, sem reprocessar LAZ ou satisfazer gate confirmatório |
| D139 | A/A+3D substitui A/B/C nas figuras desta amostra | B/C sem eixo revalidado; não renomear ablação como C |
| D140 | Cada número central tem receita e SHA-256 | Filtros/coorte/escala/versão/execução e agregações no JSON de evidências |
| D141 | Quatro figuras principais e três tabelas em tamanho final |86/178mm, fonte>=7pt, legendas9pt; PDF/SVG/PNG600dpi; provas não são manuscrito |
| D142 | Exemplos balanceados por categoria com primeiro hash | Mantida/sai/entra/fora; pós-resultados, ilustrativos; sem selecionar maior discordância |
| D143 | Mostrar perdas de suporte e amostra abaixo da meta |114/120 na avaliação;30 desenvolvimento; sensibilidade usa78–114 elegíveis por par |
| D144 | Não produzir acurácia, IC ou significância fictícios | Grupos não certificados independentes, sem alvo externo; afirmações classificadas |
| D145 | Concluir após auditoria, provas visuais e regeneração | Fontes experimentais preservadas; snapshots dos documentos operacionais mutáveis; próxima etapa14 somente quando acionada |


## Etapa 14 — manuscrito exploratório e autoria informada, 26/10/2026

| ID | Decisão | Evidência / limite |
|---|---|---|
| D146 | Redigir sobre PyCrown v0.3.0 e evidências reais da etapa13 | Dez corredores, 114 avaliação/30 desenvolvimento; sem reprocessar nuvens nem liberar o gate confirmatório v0.2 |
| D147 | Vincular cada resultado a macros e matriz de evidências | 126 valores, 24 parâmetros, 14 trechos e cinco elementos; SHA-256, filtros e receitas; controles de pesos/duplicação sem vantagem presumida |
| D148 | Usar somente autoria fornecida pelo responsável | Carlos Henrique de Moura Silva, Serpro - Serviço Federal de Processamento de Dados, carlos-henrique.silva@serpro.gov.br; endereço não inventado |
| D149 | Declarar adaptação local e divergência dos modelos | ODT com Carta no XML; LaTeX público/PDF fornecido A4; ZIP público404, sbsr.sty integral não obtido; fontes/margens preservadas, confirmação editorial pendente |
| D150 | Verificar referências nos registros e nas fontes primárias | Seis referências; Crossref/DataCite preservados; autoria do artigo e do software PyCrown diferenciada; exemplos dos modelos excluídos |
| D151 | Compilar e conferir quatro páginas completas | Resumo135/abstract126 palavras; Times New Roman incorporada; inspeção visual de quatro páginas e auditoria automática; 210 testes passam |
| D152 | Concluir a redação como rascunho, sem iniciar revisão final/submissão | Autoria informada, revisão humana e conferência editorial pendentes; sem alegar acurácia, eficácia, representatividade municipal ou prioridade real |
