# Etapa 03 — Domínio, complementos e QC dos insumos

Concluída em 25/10/2026, protocolo 0.1.0. Esta etapa preparou e auditou os
insumos; a análise científica do piloto continua pendente. Etapa 04 não iniciada.

## Domínios e arquivos

A releitura dos shapefiles confirmou EPSG:31983 e seleção única pelo identificador
completo `cd_identi0`. As geometrias foram preservadas, sem reparo ou simplificação.

| Caso | Área oficial (m²) | Área de medição (m²) | Contexto de processamento (m²) | Folhas |
|---|---:|---:|---:|---|
| CO_BT_01_E, principal | 65.807,713 | 65.807,713 | 99.600,193 | 3313-324, 3313-333, 3313-361, 3313-363 |
| CO_SE_06, adverso | 90.388,141 | 13.144,745 | 26.282,180 | 3312-431 |

No principal, medição = polígono oficial P; contexto = P.buffer(10 m). As três
folhas do núcleo e a adicional do halo coincidiram com a previsão. A folha
3313-362, necessária ao cenário de 20 m, não foi baixada.

No adverso, a medição é **CO_SE_06 ∩ 3312-431**, e o contexto é o buffer de 10 m
dessa interseção, limitado à mesma folha. Ficam fora **793,220 m²** do buffer
solicitado. Essa restrição está nos metadados e não representa o corredor inteiro
nem um halo completo. O caso não constitui réplica do principal.

Faltavam somente MDT/MDS 3313-324. Ambos foram baixados reutilizando as funções
do downloader original, que permaneceu intacto. Antes de cada transferência,
um GET em streaming verificou o endpoint: HTTP 200, Content-Type
`application/x-zip-compressed` e assinatura ZIP. O servidor ignorou Range e a
sondagem foi encerrada após os quatro bytes iniciais. Os downloads completos
passaram pela validação ZIP do downloader; a extração validou tamanho/CRC e
assinatura LAS, rejeitando caminhos inseguros e links.

| Complemento | ZIP (bytes) | LAZ extraído (bytes) |
|---|---:|---:|
| MDT 3313-324 | 3.716.730 | 3.716.554 |
| MDS 3313-324 | 47.204.497 | 47.240.431 |

Os quatro arquivos ficaram em
`<dados>/experimento/insumos_complementares/{MDT,MDS}_2020/`. Os seis LAZ do
núcleo e os dois adversos foram lidos de suas pastas originais. Cada par ZIP/LAZ
foi considerado uma única nuvem: somente o LAZ alimentou a auditoria.

## Evidências e produtos

Execuções de referência na versão final:

- Principal: `20261025T155909Z_4c11e50f3f` — [QC legível](../relatorios/execucoes/20261025T155909Z_4c11e50f3f/qc_insumos.md), [QC completo](../relatorios/execucoes/20261025T155909Z_4c11e50f3f/qc_insumos.json).
- Adverso: `20261025T155936Z_8551123d84` — [QC legível](../relatorios/execucoes/20261025T155936Z_8551123d84/qc_insumos.md), [QC completo](../relatorios/execucoes/20261025T155936Z_8551123d84/qc_insumos.json).
- Aquisição inicial: `20261025T155722Z_6bad8dd504`. Seu `manifesto_insumos.json`
  no HD contém URLs efetivamente verificadas, tamanhos, CRCs e hashes dos ZIPs.
  A execução final reutilizou esses LAZ; não fez outros downloads.
- [Plano inicial principal](../relatorios/etapa03/plano_main.json),
  [plano adverso](../relatorios/etapa03/plano_adversarial.json),
  [verificações dos produtos](../relatorios/etapa03/verificacoes.json),
  [doctor](../relatorios/etapa03/doctor.json).
- Mapas para inspeção: [principal](../relatorios/etapa03/suporte_main.png) e
  [adverso](../relatorios/etapa03/suporte_adversarial.png). São visões gerais;
  consultar os GeoTIFFs para contagem e inspeção das células individuais.

Produtos no HD, em `<dados>/experimento/etapa03/<caso>/<run_id>/`:

- `dominios.gpkg`: camadas `corredor_oficial`, `medicao`, `contexto`, `quadriculas`.
- `indice_nuvens.gpkg`: envelopes dos cabeçalhos e atributos por nuvem; não é
  uma declaração de cobertura interna.
- `manifesto_insumos.json` e `contagem_classes.csv`: procedência e contagens
  integrais, com escopo explícito de arquivo.
- `mascara_medicao.tif`: 1 = medição, 0 = somente contexto, 255 = exterior/NoData.
- Para MDT e MDS: `*_contagem_retornos.tif` (duas bandas: todos/após exclusões),
  `*_densidade_retornos.tif` (registros após QC por m²), `*_suporte_xy.tif`.

Os rasters compartilham grade de 1 m, origem global (0,0) e EPSG:31983. A
extensão varia entre os dois casos, mantendo alinhamento entre grades. As
máscaras usam centros de células; suas áreas diferem das áreas vetoriais.
No suporte: 1 = retorno após QC; 2 = apenas retornos excluídos; 3 = sem retorno;
255 = fora do contexto. Contagens usam NoData uint32=4294967295 e densidade usa
-9999; zero interno não foi confundido com NoData externo.

## Resultados observados

Leitura integral por blocos de 500 mil registros, sequencialmente, nos dez LAZ
selecionados. As contagens lidas coincidiram com os cabeçalhos; classes somaram
as mesmas contagens; coordenadas ficaram finitas e dentro dos limites declarados.
Foram registrados dimensões, retornos/flags, escalas/offsets, CRS e VLRs.
Todos declaram Imbituba/MAPGEO2015; isso não valida acurácia altimétrica externa.

| Caso | Registros MDT, arquivos integrais | Registros MDS, arquivos integrais |
|---|---:|---:|
| Principal | 2.497.568 | 25.341.000 |
| Adverso | 739.317 | 4.723.732 |

Todos os MDT selecionados contêm somente classe 8. Os MDS contêm classes
1/2/3/4/5/6/8. Não houve flags withheld, synthetic, key_point ou retorno inválido
nesses arquivos; overlap=0 nos MDS. A ausência da flag overlap não prova ausência
de pontos repetidos. Classe 3 permanece incluída. MDT não contém RGB/NIR;
esses atributos existem no MDS, sem comprovação de refletância calibrada.

O mapa utiliza coordenadas XY de retornos finitos, excluindo withheld, retornos
inválidos e classes 7/18. Não aplica filtro de altura ou seleção arbórea.

| Caso/produto | Células de medição | Com retorno após QC | Sem retorno | Ocupação XY |
|---|---:|---:|---:|---:|
| Principal MDT | 65.817 | 56.525 | 9.292 | 85,8821% |
| Principal MDS | 65.817 | 65.814 | 3 | 99,9954% |
| Adverso MDT | 13.142 | 6.198 | 6.944 | 47,1618% |
| Adverso MDS | 13.142 | 7.923 | 5.219 | 60,2876% |

Nenhuma célula apresentou apenas retornos excluídos. Os relatórios também
separam contexto, faixa interna de borda de 2 m e interior da medição.

Há registros fora dos polígonos nominais das folhas: principal MDT=185.666,
MDS=1.641.436; adverso MDT=46.281, MDS=342.601. Esses totais se referem aos
arquivos integrais. Não foram descartados silenciosamente; no mapa entram
somente os que intersectam o contexto. **As densidades contam registros, sem
deduplicação entre folhas.** MDT/MDS tampouco são observações independentes.
Antes de calcular estatísticas sensíveis à multiplicidade, deve-se definir e
testar a política de sobreposição/deduplicação.

Ocupação MDT não é validade de um terreno interpolado. Célula sem retorno não
comprova ausência de árvores ou água. O suporte do adverso é especialmente
incompleto. A etapa 04 deverá preservar essas distinções e avaliar distância
ao suporte, triangulação/interpolação e artefatos de borda, sem preencher tudo
automaticamente. Não foram produzidos DTM interpolado, H, máscara arbórea,
segmentação ou indicadores.

Na versão final, a execução principal levou 11,06 s e registrou pico de RSS do
processo de 365,69 MiB; o adverso, 4,50 s e 341,30 MiB. O primeiro processamento
principal com aquisição levou 24,38 s. São medições desses processos, com caches
do sistema e escopos distintos; não estimam custo municipal nem custo de TIN/H.

## Reprodução

Na raiz do projeto, com o HD montado:

```bash
.venv-cientifico/bin/sbsr-lidar --config configs/piloto.yaml plan-inputs --case main
.venv-cientifico/bin/sbsr-lidar --config configs/piloto.yaml prepare-inputs --case main --download-missing
.venv-cientifico/bin/sbsr-lidar --config configs/piloto.yaml prepare-inputs --case adversarial
.venv-cientifico/bin/sbsr-lidar --config configs/piloto.yaml doctor
.venv-cientifico/bin/python -m pytest -q
.venv-cientifico/bin/python -m pytest -q tests/test_baixar_lidar_geosampa.py
.venv-cientifico/bin/python scripts/verificar_etapa03.py
```

`plan-inputs` só lê vetores/disponibilidade; não acessa a rede nem cria pastas.
`--download-missing` autoriza apenas o plano derivado, limitado a dois arquivos
novos por caso. Códigos divergentes do YAML provocam erro, exigindo revisão.
Os complementos e downloads parciais são reaproveitados. Retomar usa os mesmos
comandos; `--no-cache` força nova auditoria completa em diretório próprio.
Não há retomada no ponto intermediário de leitura de um LAZ: uma auditoria
interrompida recomeça esse processamento; o cache só reutiliza produtos concluídos.

O cache inclui conteúdo dos insumos, configuração, código e ambiente, verificando
os hashes dos produtos. Foi demonstrado nos dois casos reais. Cada tentativa
tem novo manifesto; diretórios anteriores são preservados. Manifestos anteriores
à introdução do campo opcional `stage` continuam válidos como etapa 02.

Para refazer uma prévia, use o caminho `report` retornado pela CLI:

```bash
.venv-cientifico/bin/python scripts/visualizar_suporte_etapa03.py CAMINHO/qc_insumos.json --output relatorios/etapa03/nova_previa.png
```

O verificador lê as referências `execucao_*_final.json` desta entrega e os logs
de testes; não executa novamente os testes. Uma nova entrega deve atualizar
essas referências. Nesta entrega passaram **61 testes científicos, 25 testes
do downloader com 2 subtestes e 28 verificações dos produtos reais**. O único
aviso de teste é de depreciação em Rasterio/Affine. Hashes do downloader, de
seus testes e de `requirements.txt` coincidem com os da etapa anterior.
O doctor final passou e reconheceu os complementos; seus dois avisos restantes
referem-se somente ao par 3313-362 da sensibilidade de 20 m.

Sem mudança nos estimandos ou parâmetros científicos do protocolo 0.1.0.
As definições de QC/recorte desta etapa estão nas decisões D33–D38 e no YAML.
Próximo passo: etapa 04, terreno e altura, somente quando acionada.
