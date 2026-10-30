# Arquitetura mínima implementada

Versão de infraestrutura 0.1.0, etapa 02. Esta é a base de execução do projeto,
não a implementação dos módulos científicos das etapas 03–15.

| Módulo | Responsabilidade real |
|---|---|
| `config.py` | YAML seguro, rejeição de chaves duplicadas/desconhecidas, tipos/limites, caminhos e orçamento de piloto |
| `environment.py` | Versões Python, comandos nativos com timeout, estágios PDAL e identidade do código |
| `doctor.py` | Pré-verificação sem escrita nos insumos/produtos |
| `storage.py` | SHA-256 em blocos, JSON atômico e cache validado por conteúdo |
| `runtime.py` | Manifesto/log por execução, bloqueio de escritores e histórico operacional |
| `schemas.py` | Contratos Pydantic de manifesto e estado, exportados em `docs/schemas/` |
| `smoke.py` | Interoperabilidade sintética e leitura limitada de cabeçalho/pontos reais |
| `cli.py` | Somente comandos implementados: doctor, smoke e config-schema |

## Caminhos e configuração

`configs/piloto.yaml` concentra raízes, insumos, IDs, folhas, parâmetros, recursos
e ferramentas. Caminhos relativos são resolvidos em relação ao YAML, não ao
diretório corrente. Alterar o YAML é a forma de transportar o projeto.

Código/configurações e logs pequenos permanecem no projeto. `output_root`
aponta para `<dados>/experimento/` no HD. O modelo rejeita saída na raiz dos
originais ou dentro de MDS_2020/MDT_2020, execução fora do projeto, sobreposição
dos diretórios de produtos/registros e estado em `files/`.

Recursos iniciais: 1 trabalhador, bloco de 500.000 pontos, orçamento de RAM de
8 GiB, reserva de disco externo de 10 GiB e local de 0,5 GiB, máximo de seis
folhas distintas no plano do piloto e leitura smoke de 1.024 pontos. São limites
operacionais conservadores; não constituem medição de consumo da futura etapa 04.
Configurações além desses limites são rejeitadas ou precisam de mudança explícita.

## Execuções, cache e retomada

Cada smoke cria `relatorios/execucoes/<UTC_uuid>/` com manifesto, log e produtos
pequenos. A identidade do cache considera configuração resolvida, versão do
protocolo/arquivo, SHA-256 das entradas, SHA-256 do código e versões do ambiente.
O cálculo dos hashes usa blocos, não carrega arquivos inteiros em RAM.

O cache contém produtos concluídos e seus hashes. Arquivo ausente, truncado ou
alterado invalida a reutilização, mesmo que seu tamanho tenha sido preservado.
Uma execução reaproveitada tem novo manifesto e aponta para a execução de origem.
Não sobrescreve o histórico. Alterar código, entrada, parâmetros ou ambiente
gera identidade diferente.

Interrupção/falha registra status e contexto, quando a persistência ainda é
possível. A repetição do comando reutiliza somente produtos completos/íntegros;
trabalho interrompido sem produtos verificados é refeito. Esta etapa não promete
retomada de ponto de um algoritmo científico que ainda não existe.

JSON é serializado sem NaN, gravado em temporário no mesmo diretório, fsync e
renomeado com `os.replace`. Uma falha antes da troca preserva o arquivo anterior.
Bloqueios POSIX evitam escritores concorrentes no estado e no smoke; arquivo
`.lock` pode permanecer no disco sem representar processo ainda ativo.

`docs/estado_projeto.json` preserva campos e decisões anteriores. A função de
registro de execução não marca etapas científicas como concluídas. Finalizar a
etapa 02 depende da auditoria das entregas, não apenas de um smoke bem sucedido.
O contrato de manifesto desta versão impõe `scientific_pilot_executed=false`;
etapas que realmente processem o piloto precisam evoluir esse contrato de forma
explícita e versionada.

## Verificações e limitações

Esquemas: `config.schema.json`, `run_manifest.schema.json` e
`project_state.schema.json`, em `docs/schemas/`. Manifestos/estado são validados
também durante a escrita; estado permite extensão para não perder campos
científicos de outras etapas.

Testes cobrem configuração insegura/inválida, mudança de diretório corrente,
limite de piloto, escrita atômica em disco cheio, NaN, identidade e corrupção do
cache, bloqueios, interrupção/histórico, estado preservado, limite de leitura,
doctor sem criação de produtos, montagem ausente e intercâmbio nativo sintético.
Esses testes não validam classificação de árvores ou exatidão altimétrica.

Referências técnicas consultadas: [Laspy](https://laspy.readthedocs.io/en/latest/basic.html),
[Rasterio](https://rasterio.readthedocs.io/en/stable/installation.html),
[Pydantic](https://docs.pydantic.dev/latest/concepts/models/) e ajuda local
`pdal info --help` / `pdal --options writers.gdal` para a versão instalada.
