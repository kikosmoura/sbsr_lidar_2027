# QC dos insumos — main / CO_BT_01_E

Execução: `20261025T155909Z_4c11e50f3f`. EPSG:31983; célula de 1.0 m.

Área oficial: 65807.713 m²; medição: 65807.713 m²; contexto: 99600.193 m².
Folhas: 3313-324, 3313-333, 3313-361, 3313-363.

|Produto|Registros lidos (arquivos integrais)|Células de medição|Com retorno após QC|Sem retorno|Somente excluídos|
|---|---:|---:|---:|---:|---:|
|MDT|2497568|65817|56525|9292|0|
|MDS|25341000|65817|65814|3|0|

## Interpretação e limites

- Contagens de classes/retornos são integrais por arquivo selecionado; não representam o acervo municipal.
- Densidade conta registros, sem deduplicar pulsos/pontos entre folhas. MDT e MDS não são observações independentes.
- Suporte XY é ocupação por retornos, não validade de terreno nem cobertura arbórea. Célula sem retorno não é ausência de árvores.
- Exclusão QC: withheld, retorno inválido (número <1 ou maior que total), classes [7, 18]. Classe 3 permanece incluída.
- Rasterização por centro de célula; área rasterizada difere da área vetorial. Zero dentro do contexto significa nenhum registro; exterior é NoData.
- Borda de medição: faixa interna de 2.0 m. Não confundir borda de polígono com erro de costura entre folhas.
- RGB/NIR são atributos de intensidade/cor, sem comprovação de refletância calibrada. Não há validação altimétrica externa nesta etapa.
- Nenhum DTM interpolado, altura normalizada, máscara arbórea ou indicador científico foi produzido.

## Artefatos

- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/dominios.gpkg`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/indice_nuvens.gpkg`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/contagem_classes.csv`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/manifesto_insumos.json`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/mascara_medicao.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/MDT_contagem_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/MDT_densidade_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/MDT_suporte_xy.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/MDS_contagem_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/MDS_densidade_retornos.tif`
- `/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/experimento/etapa03/main/20261025T155909Z_4c11e50f3f/MDS_suporte_xy.tif`
