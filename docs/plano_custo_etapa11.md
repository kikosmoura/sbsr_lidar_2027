# Plano de custo da continuação — etapa 11

**Observado e estimado são campos diferentes.** A calibração usa somente dois casos heterogêneos do piloto. Não é previsão validada nem intervalo de confiança. Tempos humanos de referência/qualidade, aquisição de dados, setup e downloads permanecem sem estimativa por falta de medição.

|Caso|Registros declarados/decodificados na primeira passagem integral|Contexto (m²)|Pipeline03/04/06–09 observado (s)|30 cenários 10 observados (s)|Pico RSS observado (MiB)|
|---|---:|---:|---:|---:|
|main|27838568|99600.19|107.85|334.70|3669.8|
|adversarial|5463049|26282.18|36.07|61.05|1086.8|

A preparação de referência 05 é compartilhada (24,2748 s observados no pacote de 20 janelas), não foi multiplicada como se fossem dois processos independentes. As contagens de trabalho somam registros MDT e MDS, que podem coincidir: não são observações científicas independentes. A tabela de execuções reconstrói todos os tempos e bytes selecionados; pico RSS não é soma entre etapas. Tempo reportado exclui pré-hash/download/trabalho humano; somar medições é um orçamento de computação, não duração total de agenda.

|Corredores planejados|Folhas únicas|Arquivos faltantes|Pipeline por área: econômico/orçamento (h)|Sensibilidade adicional: econômico/orçamento (h)|Derivados com fator de disco (GiB)|
|---|---:|---:|---:|---:|---:|
|8|51|14|0.27 / 1.04|0.59 / 2.54|8.14|
|10|58|14|0.32 / 1.22|0.69 / 2.99|9.58|
|12|71|14|0.44 / 1.67|0.94 / 4.08|13.06|

Modelo por área: somar áreas P.buffer(10 m) dos candidatos; multiplicar pelo menor/maior tempo por m² dos dois pilotos, aplicando fator 3 ao cenário de orçamento. O mesmo princípio vale para bytes por m², com fator 3 de disco. Supõe densidade, IO e complexidade comparáveis, o que não foi demonstrado. As estimativas podem falhar; o fator 3 não é limite estatístico nem garantia. A memória não é extrapolada linearmente para o município.

O modelo alternativo por registros usa contagens de cabeçalhos e taxas por milhão de registros declarados da leitura integral. Diferencia leitura única por arquivo de visitas repetidas por corredor; agendamento de leitura única é cenário, não otimização implementada. Quando faltam cabeçalhos, essa estimativa fica null; o modelo por área é mantido como hipótese explícita, sem inventar tamanho/densidade dos arquivos ausentes.

Para os dez propostos: 58 folhas e 116 produtos; 14 precisam download e 0 precisam apenas extração. A previsão de 12 inclui reservas e não amplia automaticamente o escopo. Nenhum foi adquirido nesta etapa. O plano exato por folha/produto está em `/home/s299259068/Área de Trabalho/Projetos/2026/sbsr_lidar_2027/relatorios/etapa11/20261026T002006Z_7afdd4426f/arquivos_planejados.csv`; códigos ausentes e ZIPs existentes são separados.

Snapshot: 0.608 GiB lógicos em 1357 arquivos derivados, incluindo desenvolvimento/cache; 1647.8 GiB externos livres e 15.3 GiB locais. Isto é tamanho lógico atual, não volume de observações independentes nem previsão. Não apagar históricos para esconder uso de disco.

Orçamento: um trabalhador, 8 GiB por processo, limites de 1 milhão MDT/5 milhões ROI/seis folhas por janela, reservar 20 GiB externos **além** do orçamento de derivados e de eventuais ZIP+LAZ adicionais. Os bytes de downloads faltantes são desconhecidos; incorporar tamanhos reais antes de executar. Produtos grandes no HD externo, metadados/código no projeto. Dois trabalhadores só após ensaio e soma de picos/IO/caches, não pela contagem de CPUs.

Retomada futura: manifesto por caso/janela, hashes de entradas/configuração/ambiente/código, checkpoint completo antes de cache hit, arquivos atômicos, estado de falha e nenhum overwrite de originais. O piloto comprovou cache; o novo driver de amostra ainda precisa provar a retomada com suas bordas/componentes. Rodar primeiro um caso de desenvolvimento dentro dos limites, comparar consumo com o envelope e atualizar orçamento antes dos restantes. Não repetir os 30 cenários em todos os casos por conveniência se custo/QC impedir; registrar redução de escopo predefinida em nova versão.

Adicionar módulo/CLI nesta etapa muda o digest global e pode provocar cache miss operacional em comandos antigos; isso não invalida retroativamente os arquivos científicos com hashes conferidos. Alterar MDT/datum/H invalida04→06→07→08→09→10 afetados; máscara invalida06 e descendentes; eixo altera somente seus produtos07 e indicadores/comparações longitudinais; pesos/normalizador alteram09/10 sobre tabela. Blocos/seleção alteram agregação/inferência da nova amostra, não os H antigos. Manter todos os namespaces/versões e recalcular só por motivo documentado.
