# PyCrown preservado e adaptador da etapa 12

Fonte original: https://github.com/manaakiwhenua/pycrown
Commit: `3d8db4e03d82d5846ff68fc5fa9c18803d823464`.
Autor indicado na fonte: Jan Zörner / Manaaki Whenua — Landcare Research.
Licença original: GNU GPLv3, íntegra em `pycrown_upstream/LICENSE`.
Hashes dos arquivos preservados: `pycrown_upstream/UPSTREAM.json`.

`scripts/pycrown_worker.py` extrai por AST os métodos originais de detecção e
conversão de coordenadas de pixel e chama os módulos Numba originais, sem
modificar seus arquivos. O adaptador conserva a indicação GPLv3. O ambiente
isolado está fixado em `relatorios/etapa12/requirements_pycrown.lock.txt`.

O projeto fornece IO atual, suporte/NoData, normalização contínua de H e
exportação. A posição de centroide de platô pode ser ajustada a um pixel que
pertence ao próprio máximo; ambas as posições e a alteração ficam registradas.
O raio nominal é convertido ao próximo número inteiro de pixels. O padding
zero de uma célula permite processar bordas; não preenche lacunas dos produtos.

Não são executados o filtro CHM legado, a pilha antiga de GDAL/Laspy1/Pandas
ou o método original de correção de topo por DSM. O retorno de maior elevação
absoluta em cada segmento é exportado como estimando separado e rastreável.
Nenhum produto desta adaptação é rotulado como referência ou árvore validada.
