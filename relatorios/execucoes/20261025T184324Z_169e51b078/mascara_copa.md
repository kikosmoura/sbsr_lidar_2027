# Máscara candidata — CO_BT_01_E / main

Execução `20261025T184324Z_169e51b078`; análise provisória: `baseline_h3`; referência humana pendente.

|Versão|Área candidata em P, interseção exata (m²)|Células incertas em P (centro)|Manchas que têm área em P|
|---|---:|---:|---:|
|baseline_h2|38983.948|0|82|
|refinada_h2|38438.845|1461|82|
|baseline_h3|38528.344|0|87|
|refinada_h3|37985.639|1335|85|
|baseline_h5|37157.461|0|100|
|refinada_h5|36614.146|1150|91|

## Limites

- Unvalidated candidate mask; no supervised fitting or classification accuracy claimed.
- Same observation domain for all heights/versions; uncertainty remains in denominator, never converted to known no-tree.
- No dilation, closing, minimum-area deletion or forced promotion of class 1 was applied to crown masks.
- Counts are MDS records; repeated within-file observations may affect density; PCA alone uses 0.1 m voxel thinning.
- RGB/NIR auxiliary indices uncalibrated, photographic epoch unknown; no universal spectral threshold.
- Planar/thin/isolated flags are uncertain hypotheses, not confirmed roofs/posts/shrubs.
- Patches reconstructed with context before exact vector clipping; components can contain several trees and are censored at support/context limits.
- Raster center-cell areas and exact polygon intersections differ; use reported area definition consistently.
- Baseline of 3 m remains a provisional protocol choice; no ranking or advantage of C was evaluated.
- No longitudinal segmentation, ecological priority or scientific indicator comparison was performed.

## Produtos

- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/observabilidade.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/dominio_valido.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/mascara_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/contagem_suporte.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/geometria_auxiliar.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/espectral_auxiliar.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/retornos_auxiliares.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/contagem_candidatos_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/incerteza_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_baseline_h2_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_baseline_h2_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/estados_baseline_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/manchas_baseline_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_refinada_h2_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_refinada_h2_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/estados_refinada_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/manchas_refinada_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/contagem_candidatos_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/incerteza_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_baseline_h3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_baseline_h3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/estados_baseline_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/manchas_baseline_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_refinada_h3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_refinada_h3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/estados_refinada_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/manchas_refinada_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/contagem_candidatos_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/incerteza_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_baseline_h5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_baseline_h5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/estados_baseline_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/manchas_baseline_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_refinada_h5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/copa_refinada_h5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/estados_refinada_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/manchas_refinada_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/mascaras_manchas.gpkg`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/main/20261025T184324Z_169e51b078/auditoria_classes.csv`
