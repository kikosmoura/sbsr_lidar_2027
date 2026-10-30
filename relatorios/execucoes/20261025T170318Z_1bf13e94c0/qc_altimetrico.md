# QC altimétrico — adversarial / CO_SE_06

Execução `20261025T170318Z_1bf13e94c0`; método tin; raio principal 5.0 m.
Vértices MDT: 49139; tempo: 6.63 s; pico RSS: 443.99 MiB.

|Cenário|Células de medição|DTM válido|NoData|
|---|---:|---:|---:|
|tin_r3|13142|6886|6256|
|idw_r3|13142|6492|6650|
|tin_r5|13142|7803|5339|
|idw_r5|13142|7015|6127|
|tin_r10|13142|9495|3647|
|idw_r10|13142|7475|5667|

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

- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/vertices_terreno.parquet`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validacao_reservada.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_tin_r3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_tin_r3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validade_tin_r3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_idw_r3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_idw_r3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validade_idw_r3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/contagem_mdt_r3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_tin_r5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_tin_r5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validade_tin_r5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_idw_r5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_idw_r5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validade_idw_r5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/contagem_mdt_r5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/distancia_mdt_mais_proximo.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/triangulos_qc.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_tin_r10_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_tin_r10_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validade_tin_r10.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_idw_r10_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_idw_r10_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/validade_idw_r10.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/contagem_mdt_r10.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dtm_sem_contexto_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/efeito_contexto_dtm.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/perfis_cartesianos.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/alturas_pontos.parquet`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/contagens_altura.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/pontos_alerta_amostra.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa04/adversarial/20261025T170318Z_1bf13e94c0/dominios.gpkg`
