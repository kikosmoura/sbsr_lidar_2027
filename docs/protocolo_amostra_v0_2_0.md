# Protocolo pós-piloto da amostra — versão 0.2.0

**Congelado condicionalmente antes da nova análise; informado pelo piloto, sem pré-registro retroativo. Execução desabilitada.** A fonte executável de planejamento é `configs/amostra_cientifica_v0_2_0.yaml`; o snapshot integral com vetores/configuração/IDs e condições de execução é `configs/protocolo_congelado_amostra_v0_2_0.json`. Alterar regra/seleção após resultados exige nova versão, justificativa e descendentes separados. O protocolo 0.1.0 e os resultados do piloto permanecem intactos.

## Universo, seleção e blocos

O cadastro tem 114 feições. O alvo desta proposta é PROPOSTO/CORREDOR VERDE, com pelo menos15 fragmentos geométricos de grade 50 m/área≥25 m², fora dos grupos legados de treino/teste e de suas cadeias de proximidade de 1000 m. Restaram 22 candidatos em 15 blocos potenciais. Corredores polinizadores/escuros/outros tipos, o único existente e todos os excluídos permanecem no quadro com razão; não recebem meta arbórea universal nem somem da auditoria.

O agrupamento usa distância mínima entre polígonos e fechamento transitivo sobre todas as 114 feições, inclusive tipos fora da análise. Blocos que contenham qualquer grupo legado reservado são excluídos. Um candidato por bloco, prioridade por SHA256(semente|ID), voltas entre quadrantes de centroide definidos por medianas dos candidatos. Não se usa H, cobertura derivada, desacordo ou ranking de C para escolher casos. São estratos de localização e capacidade geométrica; cobertura/densidade dos novos casos ainda são desconhecidas, não estratos fingidamente medidos. A seleção é intencional estratificada com ordem determinística, sem pesos municipais ou probabilidades de inclusão alegadas. A exclusão da grande cadeia central de proximidade pode favorecer áreas periféricas e limita a população representada.

Distância1000 m é uma precaução de planejamento, não alcance estimado de autocorrelação. Agrupamentos200/500/1000 m e variogramas descritivos do piloto foram registrados. Um único corredor irregular não certifica estacionariedade, platô ou independência. Pares de distâncias reutilizam unidades; não há p-valor nem poder calculado. Blocos de proximidade não viram automaticamente réplicas independentes.

|Distância (m)|Blocos totais|Corredores geometricamente candidatos|Blocos candidatos|
|---|---:|---:|---:|
|200|47|32|27|
|500|31|24|19|
|1000|21|22|15|

Na grade 50 principal (n=58), os desvios-padrão amostrais são I1=0.23688, P95=4.32485 m e IQR=2.19863 m. Esses valores descrevem unidades de um corredor; não estimam variância entre corredores. O variograma descritivo de P95 tem semivariância/variância≈0,8074 abaixo de 100 m e≈1,1031 em 800–1600 m, com pares dependentes e geometria irregular. Não foi certificado um alcance de independência. Assim, priorizam-se novos grupos e referência, em vez de multiplicar pixels do piloto para produzir n ou poder aparentes. A meta120 é operacional e balanceada por corredor; sua adequação inferencial permanece não demonstrada.

Proposta: dez corredores novos em dez blocos potenciais, oito para avaliação e dois para desenvolvimento. Meta de 15 unidades elegíveis de 50 m por corredor: 120 de avaliação e 30 de desenvolvimento. As 30 não entram nos normalizadores/resultados finais. Faixa inicial 8–12 corredores e 100–200 unidades não é cálculo de poder. O piloto principal tem 58 unidades pareadas, o adverso 2; essa heterogeneidade impede prometer retenção de 15 por novo caso.

|ID proposto|Papel|Estrato|Unidades geométricas potenciais|Meta de unidades após QC|
|---|---|---|---:|---:|
|CO_CT_05|avaliacao|EN|94|15|
|CO_IP_05|avaliacao|ES|194|15|
|CO_PJ_03|avaliacao|WN|85|15|
|CO_BT_05|avaliacao|WS|50|15|
|CO_CT_01|avaliacao|EN|54|15|
|CO_PR_02|avaliacao|WN|50|15|
|CO_CL_01|avaliacao|WS|37|15|
|CO_MG_02|avaliacao|EN|44|15|
|CO_PR_03|desenvolvimento|WN|31|15|
|CO_PA_02|desenvolvimento|WS|60|15|

IDs são proposta vetorial já materializada para revisão, não seleção científica executada. A etapa 12 revalida quadro/folhas/halos e mede cobertura/suporte real. Todas as unidades físicas são preservadas; os 15 IDs da coorte por corredor são sorteados por hash estável após QC e antes de rankings. Sem reposição e sem imputar altura. Insuficiência segue ordem de reservas predefinida e registro de não resposta, antes de consultar desfechos. Se não houver 100 unidades de avaliação/quantidade de blocos suficiente, registrar a insuficiência e revisar desenho/versão; não relaxar 95% de observação ou escolher por discordância.

A lista completa de 114 feições, exclusões, ordem/reservas e geometrias está em `relatorios/etapa11/<run_id>/{quadro_amostral,ordem_candidatos}.parquet`; blocos e folhas têm tabelas próprias. Geometria do corredor é o domínio P; janela computacional não amplia P nem vira unidade amostral. Sobreposições/proximidade conservam grupos; folhas são procedência, não réplicas.

## Métodos e comparações fixadas

Célula 1 m, EPSG 31983/origem 0, classes 3/4/5, H contínuo≥3 m, baseline_h3, TIN5, halo 10, conectividade 8, grade 50 m. Permanecem os mínimos de 25 m² de unidade, 95% observada, 10 m² de copa e 50 registros vegetais. Água/NoData/incerto não viram ausência nem altura zero. Componentes são formados no contexto e mantêm ID entre folhas/janelas. I1=T/O, I4=N_componentes*10000/O, I6=P95 e I7=P75−P25 dos mesmos retornos; I5 auxiliar e I9/volume excluído.

Núcleo A/A+3D, sem B/C fictícios. S_A=((1−R(I1))+R(I4))/2; V+=((1−R(I6))+(1−R(I7)))/2; S=(1−w)S_A+wV, w principal 0,5. R=(posto médio−0,5)/n; constantes 0,5. V− e pesos 0/0,25/0,5/0,75, I6 isolado e controle de duplicação permanecem fixos. Altura/dispersão maiores não são benefício ecológico universal. Ausência detectada fica em estrato comum, com H/escore ausentes, sem dupla penalização.

**Novo universo de normalização:** coorte pareada conjunta das unidades dos oito corredores de avaliação, com IDs de corredor/bloco preservados. Isto difere da normalização por caso do piloto e é explicitamente versionado para evitar cortes top 20% de apenas três unidades em cada lista local de 15. Rankings são relativos a essa amostra restrita, não calibrados para o município. Sumários por corredor permanecem; Jaccard local continua ausente se k<5. Nenhuma unidade de desenvolvimento entra no ajuste do normalizador de avaliação. Não transportar normalizadores entre populações sem declarar.

H1: diferenças físicas de altura/dispersão em cobertura semelhante, tolerância 0,05 e razão de O≤2, com pares/unidades/grupos explicitados. H2: mudança/estabilidade de ranks, top 10/20/30%, posições e controles. H3 permanece desabilitada. Spearman descritivo sem p; top com ceil(qn), empate por ID operacional e versão inclusiva; min 3 para Spearman, k≥5 para Jaccard. Escalas 25/100 m só comparadas por transferência espacial no suporte comum, nunca igualdade de IDs. Frequência não é probabilidade de necessidade real.

Sensibilidade gradual conforme etapa 10, sem fatorial integral nem eleger cenário pelo maior ganho de 3D. Coortes global/por eixo e perdas de suporte explícitas. Subamostragem 1/2 e 1/4 com sementes 2027/28/29 é de registros, não pulsos. Quantis grossos são recalculados dos retornos; agregação fina não equivale automaticamente ao produto nativo.

## Referência, condições de execução e execução permitida

Propor quatro janelas reais por novo corredor, total 40 (oito desenvolvimento, 32 avaliação), inicialmente selecionadas sem consultar escores. Dupla anotação de 25%, rótulo incerto e adjudicação documentada. Janelas diagnósticas dirigidas a classes raras, se adicionadas, ficam separadas da estimativa de qualidade geral, com amostragem/denominadores explícitos. Os 100 trabalhos anteriores continuam pendentes e intocados. Dados atuais de campo não representam 2020 automaticamente. Referência derivada do mesmo LiDAR pode auditar algoritmo, mas não é independente do sensor nem prova separação semântica externa.

O parecer de qualidade precisa medir erros reais e sua propagação às diferenças estudadas. Não se inventou um limiar de acurácia já justificado pelo piloto. Se a incerteza impedir a interpretação ou a máscara exigir ajuste, congelar a revisão no desenvolvimento e avaliar os blocos retidos; anotações de avaliação não ajustam regras. H3/utilidade depende de outro alvo independente e data/finalidade pertinentes. QC de MDT continua interno enquanto faltar referência externa.

Inferência padrão descritiva. Pelo menos seis grupos potenciais é apenas guarda operacional herdada; não certifica poder, precisão, permutabilidade ou validade de bootstrap. Para IC por corredor/bloco, justificar independência/desenho e quantidade efetiva antes; sem isso não calcular p-valores nem reamostrar pixels como réplicas. Não há inferência municipal probabilística.

Condições de execução atuais: referência/parecer de qualidade pendente; QC dos novos casos pendente; driver genérico e coorte agrupada não verificados; recalibração de recursos pendente. O quadro geométrico é suficiente para a proposta, não para aprovar ciência. A etapa 12 começa por referência/preflight/plano e só executa nuvens depois de evidências dos condições de execução e de sua ativação explícita pelo usuário. Disponibilidade de 924 folhas não habilita modo municipal.

A implementação futura deve limitar cada janela a seis folhas, 1 milhão de vértices MDT, 5 milhões de registros ROI e 8 GiB RAM, um trabalhador. Retenção/propriedade em bordas e união de componentes entre janelas são verificadas antes de I4; não cortar corredor em novos IDs por conveniência. Primeiro novo caso de desenvolvimento mede custo/QC/retomada; depois reavaliar orçamento. Mudança de interpolação/máscara invalida descendentes apropriados, conforme inventário de falhas.
