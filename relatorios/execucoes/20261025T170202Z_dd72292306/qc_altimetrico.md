# QC altimétrico — main / CO_BT_01_E

Execução `20261025T170202Z_dd72292306`; método tin; raio principal 5.0 m.
Vértices MDT: 251439; tempo: 37.25 s; pico RSS: 695.33 MiB.

|Cenário|Células de medição|DTM válido|NoData|
|---|---:|---:|---:|
|tin_r3|65817|62939|2878|
|idw_r3|65817|58772|7045|
|tin_r5|65817|65248|569|
|idw_r5|65817|59487|6330|
|tin_r10|65817|65804|13|
|idw_r10|65817|59562|6255|

## Limites

- Validação interna de interpolação/consistência entre produtos relacionados; não acurácia absoluta independente.
- MDT classe original preservada; nenhuma correção geoidal ou remapeamento de classe aplicado.
- H usa a superfície contínua TIN/IDW nos XY, em float64; GeoTIFF é avaliação float32 nos centros da grade, sem segunda normalização.
- Propriedade por folha nominal elimina halos de exportação sobrepostos; duplicatas de registros MDS dentro da mesma folha permanecem.
- Z e classificação originais preservados; H ausente é null/NoData e alturas negativas/extremas não são truncadas.
- Água e pontes não receberam rótulos manuais; flags LAS 9/17 são apenas pistas de classe, não validação da ausência dessas feições.
- IDW limitado a oito vizinhos e mínimo configurado, ao raio, à envoltória/triângulo suportado e à distribuição angular local.
- TIN/árvore construídos em memória somente com MDT da janela; limite de vértices explícito, sem promessa de streaming de triangulação.
- Amostra de alertas contém os primeiros 1000 alertas; não é amostra representativa. Perfis são cartesianos de inspeção.
- Não foram produzidos rótulos, máscara arbórea, segmentação ou indicadores das etapas posteriores.

## Produtos

- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/vertices_terreno.parquet`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validacao_reservada.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_tin_r3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_tin_r3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validade_tin_r3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_idw_r3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_idw_r3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validade_idw_r3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/contagem_mdt_r3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_tin_r5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_tin_r5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validade_tin_r5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_idw_r5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_idw_r5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validade_idw_r5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/contagem_mdt_r5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/distancia_mdt_mais_proximo.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/triangulos_qc.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_tin_r10_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_tin_r10_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validade_tin_r10.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_idw_r10_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_idw_r10_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/validade_idw_r10.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/contagem_mdt_r10.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dtm_sem_contexto_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/efeito_contexto_dtm.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/perfis_cartesianos.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/alturas_pontos.parquet`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/contagens_altura.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/pontos_alerta_amostra.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/main/20261025T170202Z_dd72292306/dominios.gpkg`
