# Downloads LiDAR dos corredores verdes — GeoSampa 2020

O ambiente e os comandos do experimento científico estão documentados em
[docs/ambiente_cientifico.md](docs/ambiente_cientifico.md). Eles usam
`.venv-cientifico/`, separado do `venv/` utilizado abaixo pelo downloader.

O script `baixar_lidar_geosampa.py` lê os dois shapefiles do projeto, seleciona
as quadrículas que intersectam os polígonos de corredores verdes e baixa os
produtos **MDT e MDS de 2020**. Os downloads são ZIPs contendo nuvens de pontos
**LAZ**. Não é necessário automatizar cliques no navegador.

Com os arquivos fornecidos, os **114 polígonos** de corredores verdes
intersectam **924 quadrículas distintas**, incluindo **3312-431**. Selecionar
ambos os produtos gera **1.848 downloads**. O critério `intersects` inclui
contato nas bordas; cada quadrícula é baixada uma única vez por produto.
Os arquivos cobrem a folha inteira; o script não recorta as nuvens pelo corredor.

## Instalação

Requer Python 3.10 ou superior. Na pasta deste projeto:

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
```

O ambiente `venv` deste projeto já foi preparado durante a implementação.
Use esse Python para evitar conflitos com bibliotecas do sistema/QGIS.

## Execução

Conferir a seleção e gerar a lista de URLs **sem baixar os arquivos**:

```bash
venv/bin/python baixar_lidar_geosampa.py --listar
```

Baixar somente a quadrícula do exemplo, nos dois produtos:

```bash
venv/bin/python baixar_lidar_geosampa.py --quadricula 3312-431
```

Baixar **MDT e MDS de todas as quadrículas selecionadas**:

```bash
venv/bin/python baixar_lidar_geosampa.py
```

Baixar somente um produto ou limitar a quantidade de quadrículas:

```bash
venv/bin/python baixar_lidar_geosampa.py --tipo MDT
venv/bin/python baixar_lidar_geosampa.py --tipo MDS --limite 3
```

Os shapefiles de entrada são localizados a partir da pasta do script.
O destino padrão dos downloads e relatórios é o HD externo:
`/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027`.
O HD precisa estar montado; se estiver desconectado, o script para.
Os caminhos também podem ser informados explicitamente:

```bash
venv/bin/python baixar_lidar_geosampa.py \
  --aoi files/corredor_verde/corredor_verde.shp \
  --grade files/quadricula_folha_mdt_mds_2020/quadricula_folha_mdt_mds_2020.shp \
  --saida "/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027" \
  --tipo AMBOS
```

Mantenha os arquivos auxiliares de cada shapefile (`.shx`, `.dbf`, `.prj` etc.)
junto do `.shp`. O script reconhece `cd_quadric`, `cd_quadricula` e `qmdt_cod`;
para outro nome, informe `--campo-codigo NOME`. Camadas com CRS diferentes são
reprojetadas antes da interseção. CRS ausente causa erro, sem atribuição presumida.
Geometrias inválidas são reparadas antes da seleção.

## Arquivos produzidos

```text
/media/s299259068/TOSHIBA EXT/sbbr_lidar_2027/
├── quadriculas_selecionadas.gpkg  # seleção espacial para conferir no QGIS
├── quadriculas_selecionadas.csv   # atributos das folhas selecionadas
├── plano_download.csv            # quadrícula, produto, ano, URL e destino
├── resultado_downloads.csv       # histórico de tentativas por arquivo
├── MDT_2020/
│   └── 3312-431.zip
└── MDS_2020/
    └── 3312-431.zip
```

A seleção e o plano refletem os filtros da execução mais recente (`--quadricula`,
`--limite`, `--tipo`). O histórico de resultados é cumulativo. O GeoPackage usa o
CRS da grade e mantém a geometria completa de cada quadrícula.

Os downloads são sequenciais, gravados em blocos, com quatro tentativas por
arquivo. O script confere tamanho quando informado pelo servidor, integridade
CRC do ZIP e cabeçalho LAS/LAZ. Uma resposta HTML não é aceita como download.
Os ZIPs permanecem compactados: podem ser descompactados pelo gerenciador de
arquivos, e os `.laz` podem ser abertos no QGIS.

Para interromper, use `Ctrl+C`. Execute o mesmo comando para continuar: ZIPs
concluídos e válidos são reaproveitados; arquivos `.zip.part` são retomados se o
servidor aceitar `Range`, ou reiniciados se ele devolver o arquivo inteiro.
Arquivos com falha são registrados, e os demais continuam. Se faltar espaço ou
a cota de armazenamento for excedida, o script para imediatamente, preservando
os arquivos parciais. O programa retorna
código 1 se houver falhas e 130 se for interrompido. Não execute duas instâncias
simultâneas na mesma pasta de saída.

Ao continuar no HD externo, o script procura arquivos já baixados na pasta
antiga `downloads/geosampa_2020/` do projeto. ZIPs válidos são copiados para o
novo destino, sem novo download; parciais são copiados para tentar a retomada.
Os originais são preservados. Caso já estejam em outra pasta, informe
`--reaproveitar-de "/caminho/da/pasta/antiga"`, apontando para a pasta que contém
`MDT_2020/` e `MDS_2020/`. ZIPs já existentes e válidos no HD têm prioridade.

O volume total depende das folhas: na quadrícula 3312-431, o teste encontrou
3.948.016 bytes para MDT e 32.887.143 bytes para MDS. Esses tamanhos são apenas
do exemplo, não uma estimativa do conjunto completo.

## Fonte dos downloads

Links públicos confirmados em **24/10/2026**, usados pelo botão de download do
[novo GeoSampa](https://novogeosampa.prefeitura.sp.gov.br/):

- MDT 2020: camada **125**.
- MDS 2020: camada **719**.
- Rota: `/Download/File/{id}?key=cd_quadricula&value={codigo}`.

Exemplos: [MDT 3312-431](https://novogeosampa.prefeitura.sp.gov.br/Download/File/125?key=cd_quadricula&value=3312-431)
e [MDS 3312-431](https://novogeosampa.prefeitura.sp.gov.br/Download/File/719?key=cd_quadricula&value=3312-431).
Se a Prefeitura alterar os IDs/rotas, ajuste `PORTAL`, `LAYERS` e `download_url`
no início do script. A seleção espacial e o modo `--listar` funcionam offline.

## Experimento científico com PyCrown — etapa 12

A rota exploratória sem referência externa usa a amostra de dez corredores,
com protocolo separado v0.3.0. Código, parâmetros e instruções de reprodução
estão em [protocolo PyCrown](docs/protocolo_pycrown_v0_3_0.md) e
[relatório da etapa 12](docs/execucao_pycrown_etapa12.md).

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sample-pycrown --plan-only
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sample-pycrown
```

O mesmo comando retoma por checkpoints. Os derivados ficam no HD externo,
em `experimento/etapa12/`; o ambiente `.venv-pycrown` é separado. Topos e copas
são estimados, com suporte e sensibilidade registrados; não representam
contornos exatos ou árvores verificadas por referência independente.

O projeto [pyGeoSampa_LiDAR, de Abimael Cereda Junior](https://github.com/geografiadascoisas/pyGeoSampa_LiDAR/)
foi consultado como referência. Esta implementação usa seus shapefiles locais
e a rota pública do portal novo; o endpoint legado usado pelo projeto de 2024
retornou HTML durante a verificação.
