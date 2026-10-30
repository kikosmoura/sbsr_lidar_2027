# Ambiente científico — etapa 02

Implementado em 25/10/2026. O ambiente científico é **`.venv-cientifico/`**,
separado de `venv/`, que continua atendendo o downloader. Nenhum pacote do Python
do sistema/QGIS foi instalado, removido ou atualizado nesta etapa.

## Estratégia e versões nativas

Python 3.10.12 em ambiente virtual, bibliotecas Python de `pyproject.toml` e
executáveis nativos já disponíveis, chamados em subprocessos:

- `/usr/bin/pdal`: **2.3.0**, pacote do sistema `2.3.0+ds-2ubuntu4`.
- `/usr/bin/gdalinfo`: **3.4.1**, pacote `3.4.1+dfsg-1build4`.
- Rasterio **1.4.4** usa seu GDAL **3.10.3**; Pyogrio **0.13.0** usa GDAL **3.12.4**.
- Laspy **2.7.0** com lazrs **0.8.2**; dois backends LAZ detectados.

As versões completas Python estão em `requirements-scientific.lock`; dados do
sistema em `ambiente_nativo.json`. O isolamento foi testado por importação e
intercâmbio de arquivos LAZ/GeoTIFF, não por supor equivalência entre bibliotecas
nativas diferentes. A capacidade de ler esses formatos não certifica todos os
drivers, algoritmos ou futuras etapas do projeto.

Não são necessários bindings Python `pdal` ou `osgeo.gdal` para esta etapa:
PDAL/GDAL CLI e Rasterio fazem o teste de infraestrutura. Uma futura necessidade
de bindings deve ser instalada e validada explicitamente, não presumida.

## Reprodução

Na raiz do projeto, com Python 3.10 e os executáveis nativos compatíveis:

```bash
python3 -m venv .venv-cientifico
.venv-cientifico/bin/python -m pip install -r requirements-scientific.lock
.venv-cientifico/bin/python -m pip install --no-deps -e .
.venv-cientifico/bin/python -m pip check
```

O lock congela dependências Python efetivamente instaladas, sem caminho absoluto
da instalação editável. Não instala PDAL/GDAL nativos nem congela sistema
operacional, compiladores ou backend temporário de construção. Para obter os
executáveis em outra máquina, usar uma distribuição compatível/Conda/Mamba e
reexecutar `doctor`/`smoke`; não afirmar reprodução bit a bit em outro ambiente.
Conda/Mamba não foram necessários nem encontrados neste computador.

Para desenvolver com limites de dependências em vez do lock, o comando usado
na primeira instalação foi:

```bash
.venv-cientifico/bin/python -m pip install -e '.[test]'
```

## Comandos implementados

```bash
# Da raiz do projeto; sem gravação de produtos ou leitura de pontos.
.venv-cientifico/bin/python -m sbsr_lidar doctor

# Mesmo diagnóstico, salvando explicitamente o relatório no projeto.
.venv-cientifico/bin/python -m sbsr_lidar doctor \
  --report relatorios/etapa02/doctor.json

# Configuração explícita: a opção global vem ANTES do subcomando.
.venv-cientifico/bin/python -m sbsr_lidar --config configs/piloto.yaml doctor

# Leitura limitada real e teste de interoperabilidade com dados sintéticos.
.venv-cientifico/bin/python -m sbsr_lidar smoke

# Executar novamente: reaproveita produtos íntegros se a identidade não mudou.
.venv-cientifico/bin/python -m sbsr_lidar smoke

# Ignorar cache para diagnóstico dirigido, sem apagar resultados anteriores.
.venv-cientifico/bin/python -m sbsr_lidar smoke --no-cache

# Contrato completo da configuração.
.venv-cientifico/bin/python -m sbsr_lidar config-schema
```

O entry point `.venv-cientifico/bin/sbsr-lidar` é equivalente a `python -m
sbsr_lidar`. Códigos de saída: 0=diagnóstico/teste passou; 1=doctor detectou
erro de ambiente; 2=configuração/ferramenta/IO impediu execução; 130=interrupção.
Avisos de folhas de contexto ausentes não significam que o halo está pronto.

## O que é verificado

`doctor` lê configuração e vetores, consulta versões/estágios PDAL, importações,
backend LAZ, CRS métrico, ID do piloto, existência dos insumos, montagem, espaço
e acesso segundo o sistema operacional. Não baixa dados, não gera diretórios
de produtos nem faz prova de escrita no HD. Matplotlib é conferido por metadados
de instalação sem inicializar backend/cache gráfico.

Dentro do sandbox do agente, `os.access` no HD externo indicou escrita negada;
o relatório inicial conservou esse erro. O diagnóstico foi repetido com as
permissões reais da máquina, passando sem erros. Portanto, a verificação se
refere ao contexto de execução: restrições de sandbox/ACL podem exigir acesso
apropriado em uma próxima etapa. Nenhuma restrição foi ocultada no código.

`smoke` abre o MDS da primeira folha de núcleo configurada, lê o cabeçalho e
**no máximo `resources.smoke_points`**, atualmente 1.024 pontos. A amostra é do
início do arquivo, não representativa. PDAL `info --summary` confere o cabeçalho
real sem solicitar estatísticas de todos os pontos. Para identificar a entrada
no cache, é feito SHA-256 completo em blocos de bytes; isso não decodifica nem
calcula métricas de toda a nuvem.

O teste sintético gera quatro pontos LAZ e um GeoTIFF de 2×2 células no diretório
da execução. Valida LAZ por blocos, PDAL→GeoTIFF, leitura Rasterio/GDAL CLI e
distinção entre altura zero e NoData. Tais arquivos são testes identificados
como sintéticos, não produtos do corredor.

## Testes

```bash
.venv-cientifico/bin/python -m pytest tests/cientifico -q
venv/bin/python -m unittest discover -s tests -v
```

Os testes do downloader usam servidor HTTP local; o sandbox precisa permitir
socket local. Testes científicos de integração precisam de PDAL/GDAL CLI e
indicam skip explicitamente se ausentes. Nesta máquina eles foram executados.

Foi observado `PendingDeprecationWarning` de Rasterio/Affine sobre multiplicação
de matrizes, sem falha no teste. Não foi suprimido nem confundido com erro de
resultado. O `doctor` não mede o pico de RAM do piloto; o smoke registra apenas
RSS ao final e duração do trecho pequeno, explicitamente rotulados.

## Pendências das próximas etapas

O par 3313-324, para contexto de 10 m, e 3313-362, para a sensibilidade de 20 m,
continuam ausentes. Não foram baixados nesta etapa. Terreno, normalização,
máscara, segmentação e indicadores científicos ainda não foram implementados.
