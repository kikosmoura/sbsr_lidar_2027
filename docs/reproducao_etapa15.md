# Reprodução dirigida e portabilidade — etapa 15

Na raiz deste projeto:

```bash
.venv-cientifico/bin/python scripts/revisar_etapa15.py
.venv-cientifico/bin/python scripts/preparar_revisao_etapa15.py --compile-only
.venv-cientifico/bin/python -m pytest tests/cientifico -q
```

O primeiro comando autentica os três pacotes históricos, recalcula valores,
escores, pareamentos e sensibilidades e reproduz uma janela e o PyCrown de um
corredor de desenvolvimento em diretório temporário. Requer o HD externo
montado, os blocos derivados preservados, a configuração original e
`.venv-pycrown` coincidente com seu lock. Não adquire dados nem escreve no HD.
Os recortes `--science-only` e `--reproduction-only` executam somente a parte
correspondente. Os JSONs de resultado ficam em `relatorios/etapa15/`.

O segundo comando compila somente a cópia revisada já existente, atualiza sua
matriz de afirmações e audita o PDF, sem reler nuvens. Usa Tectonic e seu cache
local. Foi verificada também a compilação isolada do pacote original em outro
diretório temporário da mesma máquina, sem leitura do HD, com texto extraído
idêntico. A data/metadados do PDF não foram confundidos com divergência de
conteúdo. Depois de editar/recompilar, a inspeção visual e o manifesto finais
precisam ser renovados; uma auditoria automática não aprova o artigo pelo autor.

As saídas que comprovam as verificações são:

- `auditoria_cientifica.json`: 81 métricas de origem, 126 valores/24 parâmetros
  do artigo, 32 ablações, 22 sensibilidades e 538 pares H1.
- `registro_reproducao.json`: janela de27.534 registros, TIN5, arrays PyCrown
  exatos, retomada e invalidação de cache, ambientes, semente e tolerâncias.
- `reproducao_documento.json`: compilação a partir dos editáveis em diretório
  temporário, com igualdade de texto extraído.
- `auditoria_editorial.json`, `auditoria_referencias.json` e
  `revisao_visual.json`: PDF e metadados efetivamente conferidos.
- `testes_cientificos.txt`: teste de regressão do cache e suíte científica.

Tolerâncias absolutas: 10^-12 para escores/ranks/concordâncias; 10^-8 para
agregações numéricas do índice; 10^-9 m para H/terreno da janela; 10^-7 m²
para suporte pareado; 10^-6 m² para sobreposição de unidades. Inteiros,
identidades, rótulos, sementes, flags, status e padrões NoData são exatos.
Arrays NPZ são comparados depois de decodificados e possuem hashes semânticos
de tipo/forma/bytes. Compressão ou carimbo de arquivo não é critério de
equivalência científica.

Não se repetiram o município, todos os doze cenários desde LAZ ou a leitura
integral das345.062.484 declarações de registros. O controle dirigido parte
de blocos decodificados e CHM preservados, autenticados contra seus selos; os
demais resultados usados no artigo foram conferidos contra manifestos e
tabelas originais. A revisão não é validação externa ou inspeção de campo.

## Código e caminhos

O código anterior de `src/sbsr_lidar/crown_data.py` está em
`relatorios/etapa15/entradas_etapa12/crown_data.py`. Seu SHA coincide com o
manifesto original12. A alteração atual corrige somente a detecção de cache
incompleto. Ela muda o digest global e as identidades de cache futuras;
adicionar uma auditoria não converte automaticamente os resultados antigos
em resultados produzidos pelo código atual. A reprodução numérica e os
snapshots tornam essa distinção explícita.

Os scripts localizam a raiz pelo próprio arquivo. Os arquivos de configuração
usam caminhos relativos para a maior parte do projeto, mas `data_root`,
`mount_root` e `output_root` dependem do ponto de montagem do HD. Manifestos
históricos também registram caminhos absolutos como proveniência. Em outra
máquina, conservar os manifestos originais e fazer um mapeamento explícito
de caminhos para a nova execução, com nova configuração/identidade; não editar
hashes históricos para fingir equivalência. Não foi testada uma segunda
máquina nem declarada uma imagem de ambiente universal.

Para compilar apenas o artigo em outra máquina, as entradas necessárias são
os editáveis, figuras e tabelas no pacote, Tectonic/XeLaTeX e Times New Roman
obtida legalmente. O cache e a fonte proprietária não integram o ZIP. Uma
instalação nova do compilador pode exigir pacotes LaTeX pela rede. Não é
necessário ter os LAZ para essa compilação. Instruções no README da revisão.
