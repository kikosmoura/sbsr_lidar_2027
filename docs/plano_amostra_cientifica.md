# Plano inicial da amostra científica

Versão 0.1.0 — 25/10/2026. **Planejamento, ainda sem seleção nem execução.**
Depende do piloto e deve originar protocolo congelado antes da análise final.

## População e unidades

População de referência: perímetros da camada municipal disponível em 2026,
com vegetação observada pelo LiDAR de 2020. São 114 feições, não 114 corredores
necessariamente contínuos, nem unidades ecologicamente equivalentes.

Unidade de medição: segmento ou célula recortada elegível, na escala fixada.
Unidade de seleção/agrupamento: corredor ou trecho espacialmente delimitado;
unidade de independência: bloco espacial que reúna corredores/trechos sobrepostos
ou próximos segundo alcance estimado de dependência. Ponto LiDAR, retorno,
célula de raster e par de unidades que compartilha observação não são réplicas
independentes para a hipótese municipal.

Perguntas: H1, variação vertical condicional ao 2D; H2, mudança/estabilidade de
prioridades controlando construção do índice; H3 só com alvo externo apropriado.

## Desenho proposto após o piloto

1. Consolidar quadro amostral com `cd_identi0`/`cd_identif`, geometria/partes,
   categoria, localização, área, suporte LiDAR e disponibilidade de eixo.
2. Documentar o efeito das exclusões de cobertura, suporte, área e topologia.
   Corredores escuros/polinizadores não devem receber meta arbórea universal.
3. Tratar o único existente como estudo de caso; não construir teste balanceado
   existente/proposto a partir dele. Seus vários segmentos não multiplicam o
   número de corredores existentes independentes.
4. Usar estratos parcimoniosos de paisagem/cobertura/localização e selecionar
   corredores/trechos com semente fixa e critérios reproduzíveis. Informação
   inicial de cobertura pode apoiar estratos sem escolher casos pela vantagem
   esperada de C. Congelar a seleção antes de olhar rankings finais.
5. Começar o planejamento com **8–12 corredores/trechos e 100–200 unidades**,
   ajustando pelos recursos e variância do piloto. Isso não é cálculo de poder,
   garantia de independência ou amostra probabilística já realizada.
6. Estimar autocorrelação e sobreposições para formar blocos. Corredores que
   compartilham área/vegetação devem permanecer no mesmo grupo de treino/teste.
   A quantidade efetiva de blocos pode ser menor que a de corredores selecionados.
7. Dimensionar capacidade inferencial em função do número efetivo de blocos,
   efeito de interesse e precisão desejada. Com poucos blocos, restringir a
   descritivo/estabilidade e não emitir p-valores nominais por pseudorreplicação.

Não fazer produto cartesiano de todos os estratos com apenas 8–12 seleções.
Se a amostra for intencional, limitar conclusões a ela e contextos comparáveis;
não reportar estimativa municipal ponderada como se houvesse probabilidades
conhecidas. Se for probabilística, registrar quadro, probabilidades, pesos,
substituições e não resposta antes do processamento final.

## Referência, treinamento e teste

Separar três amostras: desenvolvimento do método no piloto; referência de teste
não usada no ajuste; amostra científica para avaliar H1/H2 no domínio declarado.
Quando couber modelo supervisionado, ajustar transformações e hiperparâmetros
somente no treino e avaliar em blocos retidos. Validar categorias raras sem
misturar treinamento e referência.

Para referência manual, permitir incerto e dupla anotação de uma fração. Se
desacordos A/C forem superamostrados, registrar probabilidades/pesos ou limitar
a estimativa a esse estrato; não transferir sua frequência à população.

H3 demanda alvo e referência independentes pertinentes a 2020, com finalidade
que não seja uma soma das alturas de C. A disponibilidade e suficiência desses
dados ainda não foram demonstradas. Sem eles, H3 permanece não testada, sem
impedir estudo bem delimitado de H1/H2 quando a qualidade da máscara for avaliada.

## Congelamento antes da execução científica

Após a etapa 11, versionar e registrar: seleção/domínio; máscara e referência;
unidades/eixos; estimandos; exclusões e suportes; sinais e pesos; cenário principal;
sensibilidade; estratos/blocos; hipóteses, métricas e regras de interpretação.
Registrar quais escolhas foram informadas pelo piloto. Não denominar o plano
atual como pré-registro confirmatório já concluído.

Comparações pareadas usam universo comum. Reportar perdas e resultados no
domínio mais amplo separadamente. Congelar normalização e evitar vazamento de
treino/teste se houver alvo preditivo. Sem alvo, escores são cenários exploratórios
e não escores normativos municipais.

## Escala e conclusão

O lote das 924 folhas é opcional; dados disponíveis não tornam a escala municipal
necessária. Executá-lo só no modo acionado da etapa 12, depois de medir custo,
espaço, I/O e falhas do piloto. Completar halos com plano de faltantes próprio.

Resultado mínimo defensável: diferenças ou equivalências quantificadas entre
representações, qualidade da máscara e do terreno documentada, robustez e
limites espaciais. Se amostra, suporte ou referência forem insuficientes, reduzir
o alcance da conclusão; não chamar mapas do piloto de evidência municipal.
