# Revisão de interpretação ecológica, distribuição dos pares e medição

A revisão mantém todos os escores, os mesmos 16 pares e a coorte fixa do
complemento17. Os arquivos anteriores foram preservados. É uma revisão
exploratória de interpretação e apresentação, não validação externa.

## Pontuação e significado dos indicadores

I6=P95(H) descreve a cauda superior das alturas dos retornos selecionados;
I7=IQR(H), sua dispersão interquartil. Não são indicadores calibrados de
biodiversidade, qualidade de habitat, biomassa ou necessidade de intervenção.
Os sinais 1−R(I6) e 1−R(I7) fazem alturas/dispersões menores aumentar o escore por
construção. Essa orientação fica explicitamente identificada como configuração
experimental de ordenação. Não será defendida como relação ecológica universal.
O símbolo Vexp substitui V+ apenas no manuscrito; o identificador histórico
Vplus e os resultados numéricos permanecem os mesmos. A comparação vertical
dos pares independe dessa pontuação.

## Distribuição dos mesmos 16 pares

Diferenças absolutas em metros, quantis lineares, sem reutilização de IDs.

| Descritor | Mínimo | Q1 | Mediana | Q3 | Máximo |
|---|---:|---:|---:|---:|---:|
| P95 | 0.04 | 1.29 | 2.80 | 6.15 | 20.91 |
| IQR | 0.03 | 0.94 | 1.75 | 3.28 | 15.44 |

A distribuição tem diferenças quase nulas e uma cauda de valores elevados.
A complementaridade descritiva é heterogênea; não se afirma que toda unidade
semelhante em 2D difere substancialmente em 3D. A mediana de P95 = 2.80 m
não resume sozinha essa assimetria. Os IDs e os valores individuais estão em
`pares16_preservados.csv`; não houve seleção pelos maiores contrastes.

## Metadados do levantamento 2020

Foram examinados os XML oficiais MDT/MDS e o [atestado técnico vinculado a
eles](https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/intranet/api/records/892c862e-f564-4b1c-a3d0-9d28052e5d58/attachments/voo2020_ATESTADO-T%C3%89CNICO_PMSP.pdf). O documento declara PEC-PCD Classe A e menciona
46 pontos para controle da qualidade dos produtos, mas não fornece
as coordenadas desses pontos, resíduos individuais ou RMSE altimétrico.
Portanto, os documentos consultados não permitem estimar numericamente a
acurácia absoluta ou relativa dos percentis usados no estudo. Isso não afirma
que outros relatórios do produtor inexistam: a busca pública não os obteve.

O [contrato 33/2022](https://www.prefeitura.sp.gov.br/cidade/upload/contrato_33_2022_-_fototerra_transparncia_1660825403.pdf)
remete ao Termo de Referência; o PDF consultado não contém uma tabela de
resíduos. A notícia/tutorial de 2017 e a precisão nominal de equipamento não
foram transferidas ao levantamento 2020. Resolução espacial 0,50 m, densidade e
quantização LAS 0,001 m também não são medidas de erro vertical.

Há divergências de descrição entre fontes: o XML MDT menciona 10 pontos/m²,
enquanto o atestado descreve densidade 4 pulsos/m² após filtragem de terreno.
A linhagem do XML MDS descreve uma subtração MDS−MDT, enquanto a auditoria dos
LAZ demonstrou Z absoluto. Essas descrições não substituem o exame dos dados
reais nem fundamentam uma precisão numérica fictícia. Originais não alterados.

## Checagens internas TIN5 já existentes

Somente oito corredores de avaliação; três janelas por corredor selecionadas
por hash na execução original. Não houve nova normalização ou retenção de
pontos. Os resíduos são contra MDT reservado do mesmo sensor, com TIN5 fixo.

| Retenção | Janelas com RMSE / testadas | RMSE mediano por janela (m) | RMSE mínimo–máximo (m) | Registros com suporte válido |
|---|---:|---:|---:|---:|
| Pontos | 24/24 | 0.080 | 0.027–0.115 | 98.79% |
| Blocos | 22/24 | 0.222 | 0.026–0.574 | 27.32% |

Cada janela pesa igualmente no resumo dos RMSE. A cobertura válida é razão
entre registros válidos e avaliados, incluindo janelas com zero suporte.
Não atribuir RMSE zero às duas janelas sem resíduos válidos em blocos. As
contagens representam registros dependentes, não réplicas independentes.
Os detalhes estão em `qc_tin5_por_janela.csv` e
`qc_tin5_metricas_indisponiveis.csv`.

Esse controle quantifica consistência de interpolação nas parcelas com
suporte. Não mede erro absoluto de Z, erro da copa, omissão de retornos sob
vegetação ou a totalidade da incerteza em H. A cobertura baixa dos blocos
também impede transferir o RMSE às áreas sem suporte ou tratá-lo como limite
máximo de erro. Não comparar 2,80 m a esse RMSE para declarar significância.

## Componentes de incerteza e condição para uma conclusão mais forte

Se eH = eZ − eTIN, a variância do erro normalizado depende das variâncias de cada
parcela e de −2Cov(eZ,eTIN). MDT e MDS compartilham observações; independência
e cancelamento de erros não foram demonstrados. Um deslocamento constante em
H altera P95 mas não IQR; se compartilhado pelas duas unidades, cancela na
diferença de P95. Erros espacialmente variáveis, de classificação/segmentação
e de seleção de retornos não têm esse cancelamento garantido. Não dividir um
RMSE por raiz do número de retornos correlacionados.

| Componente | Evidência disponível | O que continua desconhecido |
|---|---|---|
| Georreferenciamento vertical | Datum nos LAZ e declaração do produtor | Viés, resíduos de pontos independentes, erros por faixa/tipo de superfície |
| Interpolação de terreno | Retenções TIN5 do mesmo sensor | Erro absoluto e comportamento sob copa/sem suporte |
| Seleção de retornos e máscara | QC e sensibilidades internas | Omissão/comissão, fusão/divisão e erro de classificação contra referência |
| P95/IQR e diferenças entre unidades | Distribuições observadas e pareamento | Propagação do erro correlacionado e incerteza total dos percentis |

Uma conclusão de diferenças superiores ao erro total requer relatório de
controle do levantamento 2020 com coordenadas e resíduos, separação dos pontos
de ajuste/checagem, datum/unidades e avaliação por superfície/faixa; além de
referência/modelo de erro apropriado para a seleção de vegetação. A existência
de controle de terreno, isoladamente, não valida copas. A revisão conserva
essa condição como limitação explícita.

## Reprodução

```bash
.venv-cientifico/bin/python scripts/revisar_interpretacao_artigo.py --analyze
.venv-cientifico/bin/python scripts/revisar_interpretacao_artigo.py --verify
.venv-cientifico/bin/python -m pytest tests/cientifico/test_measurement_review.py -q
```

Fontes, estatísticas e código têm SHA-256. O artigo revisado está em
`artigo/revisao_interpretacao_v0_3_2/`; os resultados e o manifesto estão
apontados por `relatorios/revisao_interpretacao/ultima_execucao.json`.
