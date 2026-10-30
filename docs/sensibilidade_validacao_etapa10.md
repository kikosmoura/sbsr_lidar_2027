# Etapa 10 — sensibilidade e auditoria da validação

Foram executados **30 cenários em cada um dos dois casos do piloto**. O cenário principal foi reproduzido, com máscara/observabilidade idênticas e indicadores/ranqueamento conferidos contra as etapas 06/08/09. Os dados originais e os produtos anteriores foram preservados. A execução é retrospectiva e exploratória; **a validação empírica da máscara, das lacunas e das prioridades continua pendente de referência real**.

## Escopo, execução e produtos

Parâmetros principais: célula de 1 m, classes LAS 3/4/5, H≥3 m, TIN com raio de suporte de 5 m, halo de 10 m, conectividade 8. As grades de 25/50/100 m são avaliadas em todos os cenários. Não houve lote municipal, nova correção geoidal, treinamento supervisionado ou ampliação da área científica.

O recorte principal usa cinco folhas: 3313-324/333/361/362/363; somente o par MDT/MDS 3313-362 foi adquirido nesta etapa em `experimento/insumos_complementares`. O adverso permanece restrito a CO_SE_06∩3312-431. Todos os produtos grandes ficam no HD externo configurado, em `experimento/etapa10/`.

|Caso|Registros no ROI máximo|Vértices MDT máximos|Tempo observado (s)|Pico RSS (MiB)|
|---|---:|---:|---:|---:|
|Principal|2529904|297765|334.70|3669.8|
|Adverso|390263|80117|61.05|1086.8|

Um trabalhador, limite configurado de 8 GiB de RAM e reserva de disco. Tempo de aquisição, testes, figuras e desenvolvimento não está incluído nos tempos científicos acima. As reexecuções finais comprovaram cache pelos hashes de todas as entradas/produtos. Tentativas de desenvolvimento, inclusive interrupções, permanecem nos manifestos históricos e não são fontes dos resultados selecionados.

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sensitivity --case main --plan-only
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sensitivity --case main
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sensitivity --case adversarial
.venv-cientifico/bin/python scripts/verificar_etapa10.py
.venv-cientifico/bin/python scripts/resumir_sensibilidade_etapa10.py
```

Código: `src/sbsr_lidar/sensitivity_{scenarios,data,analysis,run}.py`. Protocolo integral: `docs/metodologia_sensibilidade_etapa10.json`. Entradas/execuções/cache: `relatorios/etapa10/{plano_cenarios,plano_adverso,execucao_main,execucao_adversarial,cache_main,cache_adversarial}.json`. O agregado `docs/manifesto_etapa10.json` registra os caminhos exatos e hashes dos artefatos.

Cada execução gera `cenarios_custo`, `dominios_areas`, `indicadores_nativos`, `comparacoes_suporte_comum`, `mudancas_indicadores`, `transicoes_elegibilidade`, `coorte_estrita`, `estabilidade_fisica`, `estabilidade_receitas`, `suportes_por_eixo`, `ablacao_por_cenario`, `comparacoes_entre_escalas`, `transferencia_espacial`, `sensibilidade_densidade` e `indicadores_suporte_global`, em Parquet e CSV. GeoParquet preserva a geometria onde pertinente. Cada cenário tem rasters nativos de observabilidade/copa e contagens, manchas de contexto e indicadores.

Os mapas de estabilidade ficam em `relatorios/etapa10/sensibilidade_main.png` e `sensibilidade_adversarial.png`. `desacordos_{main,adversarial}_50m.parquet` associa os deslocamentos e contribuições dos indicadores à geometria original. Os arquivos são inspecionáveis no QGIS, em EPSG:31983.

## Desenho de sensibilidade e regras de comparação

Foram alterados, um eixo de cada vez: resolução 0,5/2 m; altura 2/5 m; halo 0/20 m; raios TIN 3/10 m; IDW com raio 5 m; conectividade 4; máscara refinada experimental e limite superior com células incertas. Duas interações foram fixadas: 0,5 m+H≥2 m e 2 m+H≥5 m. A máscara refinada é reaproveitada de 06, sem novo ajuste ou rótulo. O limite superior é uma hipótese de inclusão, não uma classificação melhor demonstrada.

A redução para 1/2 e 1/4 dos registros usa sementes 2027/2028/2029 e identidade `(folha, índice do registro na origem)`. Os subconjuntos são reproduzíveis sob reordenação e mudança de chunk; 1/4 é subconjunto de 1/2 com a mesma semente. O modo acoplado altera ocupação/máscara/H. O modo somente alturas conserva máscara e V completos e altera os retornos usados nos descritores. Primeiros retornos são um cenário distinto de estimando; não foram reconstruídos identificadores de pulso nem simuladas novas linhas de voo.

**Halo não expande a medição.** Os dois cenários P.buffer(5/10 m) mudam a população e têm IDs próprios. São apresentados em tabela separada de áreas, sem entrar nas frequências de robustez de P. No adverso, medição expandida e contexto continuam recortados à folha nominal; a área de contexto omitida está registrada. O ROI máximo inclui os pequenos arcos que diferem entre buffers sucessivos e um buffer único da soma.

Para cada comparação, as duas medições foram recalculadas em V₀∩Vₛ, com os mesmos IDs elegíveis por caso/escala. Componentes recebem IDs no contexto antes do recorte: fragmentar uma mancha no suporte comum não cria novas árvores/manchas independentes. Linhas/pontos isolados produzidos pelas interseções não são superfície observada. A atribuição dos pontos às unidades usa a regra canônica do pixel semiaberto de 1 m em todas as resoluções.

Áreas são interseções poligonais exatas. Não se imputou H para ausência de copa ou falta de suporte. Permanecem os mínimos de 25 m² de unidade, 95% de observação, 10 m² de copa e 50 registros vegetais. As tabelas compactas omitem algumas áreas auxiliares de QC; os códigos de observabilidade e contagens permanecem nos rasters e o diagnóstico detalhado de 08 foi preservado. Estado sem copa detectada não comprova ausência real de árvores.

Além dos pares, há uma interseção V e uma coorte elegível fixa para os 28 cenários sobre P, e ensembles separados para cada eixo. O mesmo denominador sustenta todos os votos de cada ensemble; universos diferentes não foram misturados. As dez receitas de escore sobre o suporte congelado excluem controles duplicados e pesos zero repetidos. Frequências com desempate por ID e com inclusão de todos os empates são disponibilizadas separadamente. **Min/max são amplitudes empíricas entre cenários, não intervalos de confiança; frequência não é probabilidade de intervenção.**

## Resultados de suporte, ranking e densidade

|Cenário nativo, grade 50 m|Principal elegível A+3D|Adverso elegível A+3D|
|---|---:|---:|
|primary|58|2|
|res_0.5|50|1|
|res_2|58|2|
|height_2|58|3|
|height_5|58|1|
|halo_0|53|0|
|halo_20|58|2|
|radius_3|46|2|
|radius_10|60|2|
|idw_5|17|1|
|refined|58|2|
|thin_coupled_0.5_s2027|57|1|
|thin_coupled_0.25_s2027|44|0|
|thin_height_only_0.25_s2027|55|1|
|first_returns|58|2|

A diferença de contagens acima é um resultado de suporte/seleção, não um ganho de acurácia. Listas nativas de tamanhos diferentes não são comparadas como se tivessem o mesmo universo.

|Cenário vs. principal em suporte comum, 50 m (principal)|n pareado|Spearman A+3D|Jaccard top 20%|Deslocamento absoluto médio|
|---|---:|---:|---:|---:|
|res_0.5|50|0.9792|1.0000|2.32|
|res_2|58|0.9824|0.8462|2.34|
|height_2|58|0.9901|0.7143|1.59|
|height_5|58|0.9847|0.8462|2.12|
|halo_0|53|0.9965|0.8333|0.81|
|halo_20|58|1.0000|0.8462|0.03|
|radius_3|46|0.9985|1.0000|0.41|
|radius_10|58|0.9998|1.0000|0.10|
|idw_5|17|0.9883|—|0.47|
|connectivity_4|58|0.9890|0.8462|1.64|
|refined|58|0.9983|1.0000|0.62|
|thin_coupled_0.25_s2027|44|0.9720|0.8000|1.80|
|thin_height_only_0.25_s2027|55|0.9991|1.0000|0.42|
|first_returns|58|0.9896|0.8462|1.60|

**Principal:** V comum global=53807.472 m², diante de 65233.110 m² observados no cenário principal. Unidades elegíveis em todos os 28 cenários: 25 m: 5, 50 m: 1, 100 m: 0.
Nas dez receitas, em 50 m, n=58: 4 unidades sempre no top operacional, 15 em parte das receitas e 39 nunca; maior amplitude de posto médio=33.0. Empates e lista pequena podem dominar esses valores; consultar a versão inclusiva.

**Adverso:** V comum global=4302.239 m², diante de 6076.513 m² observados no cenário principal. Unidades elegíveis em todos os 28 cenários: 25 m: 0, 50 m: 0, 100 m: 0.
Nas dez receitas, em 50 m, n=2: 1 unidades sempre no top operacional, 0 em parte das receitas e 1 nunca; maior amplitude de posto médio=0.5. Empates e lista pequena podem dominar esses valores; consultar a versão inclusiva.

A coorte global pode ficar vazia: isso é mantido como limite, sem relaxar os 95% de observação nem excluir cenários para obter estabilidade. As frequências por eixo e por receita têm denominadores próprios e não substituem uma certificação global. O adverso tem somente duas unidades no cenário principal de 50 m, A constante e nenhum suporte para Spearman/Jaccard robustos; sua aparente permanência no topo não demonstra equivalência ou prioridade ecológica.

No principal/50 m, a redução a 1/4 com máscara fixa (semente 2027, n=55) teve mediana da diferença absoluta de P95 de 0,04585 m, mas máximo de 2,32024 m. Portanto a mediana pequena não protege todas as unidades. Primeiros retornos (n=58) elevaram o P95 em mediana 0,27011 m, mudando o estimando. A decomposição do escore mostra contribuição média absoluta de I4 de 0,03280 no eixo resolução e 0,02253 na redução acoplada, superiores às contribuições verticais nesses eixos. Trata-se de composição aritmética, sem explicação causal.

As posições relativas por pares foram altas no principal, mas o corte superior pode mudar com empates: halo 20 m teve rho=0,999954, Jaccard operacional=0,846154 e inclusivo=0,923077. A escala também altera a pegada espacial: A+3D 25→100 m teve Jaccard de área=0,13714 no suporte W. Não há estabilidade universal entre escolhas/escala. As receitas de escore produziram amplitude máxima de 33 postos, apesar de somente quatro unidades sempre integrarem o top operacional das dez receitas.

As tabelas `sensibilidade_densidade` distinguem associação descritiva entre densidade e altura de diferenças pareadas após retenção dos registros. P95/IQR são estatísticas ponderadas por retornos, sujeitas à aquisição e ao número de registros. A comparação com máscara congelada isola parte desse efeito; o modo acoplado mistura mudanças de suporte, cobertura e fragmentação. Não existe I9/volume proxy neste piloto, e nenhum efeito causal de densidade sobre a vegetação foi inferido.

Contribuições de I1/I4/I6/I7 fecham aritmeticamente a mudança do escore com pesos fixos; não são importância causal. Os escores, sinais de IQR e pesos da etapa 09 foram conservados. A comparação A/A+3D também está registrada por cenário: sem alvo independente, estabilidade ou alteração de postos não demonstra melhoria. Casos com coorte pequena/variável constante, orientação alternativa que aproxima A e perda de suporte impedem uma conclusão universal de ganho pelo 3D.

## Escalas e agregação

Os percentis de prioridade nativos são transferidos como constantes por polígono para a interseção espacial exata W das partições elegíveis e do P observado. A correlação é ponderada por área; o Jaccard usa áreas de pegadas superiores em W. Não se compara igualdade de IDs/geometrias de grades incompatíveis. Os percentis são relativos às coortes nativas, não modelos calibrados transportados para outra escala.

|Principal, A+3D|Área W (m²)|Fração do P observado|Correlação de percentis ponderada por área|Jaccard de área top20%|
|---|---:|---:|---:|---:|
|25→50 m|58794.83|0.9013|0.7211|0.3902|
|25→100 m|60648.41|0.9297|0.4918|0.1371|
|50→100 m|62359.85|0.9560|0.7242|0.1702|

|Agregação 0,5→2 m vs. nativo 2 m|Células com contagem diferente|Células com copa diferente|Células com observabilidade diferente|
|---|---:|---:|---:|
|Principal|0|108|111|
|Adverso|1|5|135|

A regra testada soma contagens finas e agrega copa/validade com any. A população de pontos admitida na borda do contexto também depende da célula nativa e pode gerar diferença de contagem; a validade do terreno é reavaliada no centro nativo. Não se assumiu equivalência entre resoluções. P95 das unidades foi calculado diretamente dos retornos; não é média dos P95 de células finas.

## Validação e limites de interpretação

|Objeto|Evidência disponível|Pendência|
|---|---|---|
|Máscara de copa|Consistência de classes/H, cenários e estados incertos|Zero anotações humanas concluídas; ortofoto datada/campo e referência independente ausentes|
|Terreno|QC interno por pontos/blocos MDT reservados, etapa 04|Mesmo produtor/sensor; não mede acurácia altimétrica absoluta independente|
|Lacunas|Seções/censuras congeladas e limitações geométricas da etapa 07|Referência real e suporte longitudinal suficiente; B/C indisponíveis|
|Rankings|Concordância numérica, coortes e frequências auditáveis|Alvo independente de prioridade/utilidade; nenhuma melhoria de acurácia demonstrada|

As distâncias horizontais 0/2/5 m de grafos/lacunas não foram aplicadas: não existe métrica de grafo operacional neste piloto, B/C não estão disponíveis e conectar lacunas desconhecidas/censuradas criaria uma medida sem fundamento. Os limiares de seção permanecem diagnósticos da etapa 07; não foram usados para fabricar observação ou validação.

Incerteza de referência (rótulos ausentes), classificação (baseline/refino/limite superior), interpolação (TIN/IDW/raio/halo), amostragem (densidade/retornos) e parâmetros (resolução/altura/componentes/escore) são reportadas separadamente. Expansão de P é mudança de domínio. Nenhuma família representa sozinha toda a incerteza científica.

Há um grupo de corredor por caso, sem grupos independentes suficientes para intervalos inferenciais. Não houve bootstrap de pixels, p-valores, permutação de blocos presumidamente independentes ou ajuste sobre anotações de teste. Min/max de sementes são amplitudes empíricas. Os dois casos não foram agrupados como réplicas intercambiáveis.

**Verificações:** 162 testes científicos (oito novos), 25 testes do downloader e dois subtestes; sete avisos anteriores de depreciação Rasterio/Affine. Conferência real dos hashes/fontes, reprodução do cenário principal, conservação de áreas, NoData/elegibilidade, máscaras nativas, H por reagrupamento XY independente, dez receitas, geometrias/áreas transferidas, decomposição do escore e cache. Resultado completo em `relatorios/etapa10/verificacoes.json`.

A etapa 10 conclui a implementação e execução da sensibilidade e a auditoria das dependências de validação. **A validação empírica permanece incompleta por dependência**, sem máscara validada, acurácia externa ou conclusão municipal. A etapa 11 não foi implementada; depende de nova solicitação.
