# Máscara candidata — CO_SE_06 / adversarial

Execução `20261025T184450Z_36a402772a`; análise provisória: `baseline_h3`; referência humana pendente.

|Versão|Área candidata em P, interseção exata (m²)|Células incertas em P (centro)|Manchas que têm área em P|
|---|---:|---:|---:|
|baseline_h2|852.911|0|16|
|refinada_h2|849.911|87|16|
|baseline_h3|623.595|0|37|
|refinada_h3|620.783|27|35|
|baseline_h5|157.485|0|7|
|refinada_h5|156.485|12|7|

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

- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/observabilidade.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/dominio_valido.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/mascara_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/contagem_suporte.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/geometria_auxiliar.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/espectral_auxiliar.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/retornos_auxiliares.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/contagem_candidatos_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/incerteza_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_baseline_h2_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_baseline_h2_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/estados_baseline_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/manchas_baseline_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_refinada_h2_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_refinada_h2_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/estados_refinada_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/manchas_refinada_h2.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/contagem_candidatos_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/incerteza_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_baseline_h3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_baseline_h3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/estados_baseline_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/manchas_baseline_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_refinada_h3_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_refinada_h3_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/estados_refinada_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/manchas_refinada_h3.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/contagem_candidatos_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/incerteza_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_baseline_h5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_baseline_h5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/estados_baseline_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/manchas_baseline_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_refinada_h5_contexto.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/copa_refinada_h5_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/estados_refinada_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/manchas_refinada_h5.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/mascaras_manchas.gpkg`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa06/adversarial/20261025T184450Z_36a402772a/auditoria_classes.csv`
