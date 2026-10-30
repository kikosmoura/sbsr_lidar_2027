# QC dos insumos — adversarial / CO_SE_06

Execução: `20261025T155810Z_f162172cca`. EPSG:31983; célula de 1.0 m.

Área oficial: 90388.141 m²; medição: 13144.745 m²; contexto: 26282.180 m².
Folhas: 3312-431.

|Produto|Registros lidos (arquivos integrais)|Células de medição|Com retorno após QC|Sem retorno|Somente excluídos|
|---|---:|---:|---:|---:|---:|
|MDT|739317|13142|6198|6944|0|
|MDS|4723732|13142|7923|5219|0|

## Interpretação e limites

- Contagens de classes/retornos são integrais por arquivo selecionado; não representam o acervo municipal.
- Densidade conta registros, sem deduplicar pulsos/pontos entre folhas. MDT e MDS não são observações independentes.
- Suporte XY é ocupação por retornos, não validade de terreno nem cobertura arbórea. Célula sem retorno não é ausência de árvores.
- Exclusão QC: withheld, retorno inválido (número <1 ou maior que total), classes [7, 18]. Classe 3 permanece incluída.
- Rasterização por centro de célula; área rasterizada difere da área vetorial. Zero dentro do contexto significa nenhum registro; exterior é NoData.
- Borda de medição: faixa interna de 2.0 m. Não confundir borda de polígono com erro de costura entre folhas.
- RGB/NIR são atributos de intensidade/cor, sem comprovação de refletância calibrada. Não há validação altimétrica externa nesta etapa.
- Nenhum DTM interpolado, altura normalizada, máscara arbórea ou indicador científico foi produzido.
- Caso adverso restrito à interseção corredor/folha; halo truncado na borda nominal, com 793.220 m² de contexto solicitado fora do domínio. Não representa o corredor completo.

## Artefatos

- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/dominios.gpkg`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/indice_nuvens.gpkg`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/contagem_classes.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/manifesto_insumos.json`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/mascara_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/MDT_contagem_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/MDT_densidade_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/MDT_suporte_xy.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/MDS_contagem_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/MDS_densidade_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/adversarial/20261025T155810Z_f162172cca/MDS_suporte_xy.tif`
