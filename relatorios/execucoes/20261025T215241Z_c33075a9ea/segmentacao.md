# Unidades multiescala — CO_SE_06

Execução `20261025T215241Z_c33075a9ea`; máscara congelada `baseline_h3` não validada.

|Escala (m)|Grade|Segmentos|Segmentos com suporte longitudinal suficiente|
|---|---:|---:|---:|
|25|59|26|0|
|50|25|13|0|
|100|10|7|0|

## Critérios e limitações

- Exploratory units; frozen candidate crown mask remains unvalidated; no new human labels or accuracy.
- Branched/broad/closed/short parts fail single-chain policy and remain grid; no arbitrary route chosen.
- One terminal pruning pass only: length<=25m and <=2.5*join_radius; removed lines retained with reason.
- Accepted axes have geometric QC, not cadastral/functional route validation or independent human review.
- Full-width sections require >=95% observation; unknown stations never become crown gaps.
- Gaps are sequences on the whole branch before segment cuts; endpoints/unknown support censor gaps.
- Station-point Voronoi gives disjoint whole-width regions; segment spatial boundaries are discretized by station centers.
- Influence-region endpoint caps remain in area; they do not extend measured axis length.
- No linking of disconnected parts; junction-rich parts rejected for longitudinal comparison; grid includes them.
- Intercorridor overlaps preserved and reported; domains are not pooled as independent replicates.
- Cross-scale comparisons require intersection weights/common spatial support, not Jaccard of incompatible unit IDs.
- No ecological gap interpretation, structural indicator scores, ranking, or municipal expansion performed.
