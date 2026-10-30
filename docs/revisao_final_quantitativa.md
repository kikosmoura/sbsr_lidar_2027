# Revisão do par máximo e da conclusão quantitativa

Os três pontos solicitados foram examinados sem alterar os pares, escores,
coortes ou cenários principais. O extremo continua no conjunto de 16 pares.
A investigação específica dele e a exclusão diagnóstica são pós-resultados.

## Par com diferença máxima de P95

Corredor **CO_PR_02**. IDs completos:

- Unidade 1: `CO_PR_02_P002_G50_X6359_Y148144_F01`.
- Unidade 2: `CO_PR_02_P002_G50_X6370_Y148143_F01`.

Os centroides estão a 547,07 m; mesmo corredor não significa
mesma vizinhança imediata. A diferença de cobertura é
1,207 pontos percentuais; a diferença de
R(I4)=0,052632; razão de áreas observadas
1,5882. Satisfazem os limites principais de
0,05; 0,10; e 2, respectivamente. Não são equivalência estatística/ecológica.

| Evidência | Unidade 1 | Unidade 2 |
|---|---:|---:|
| P95 (m) | 29,567346 | 8,655607 |
| IQR (m) | 19,058497 | 3,616441 |
| Retornos selecionados | 1110 | 310 |
| Área observada (m²) | 330,777459 | 208,26994 |
| Fração observada | 1 | 1 |
| Cobertura I1 | 0,185053 | 0,197123 |
| Manchas/ha I4 | 120,927224 | 144,043831 |
| Área com flag de incerteza (m²) | 5 | 2 |
| Retornos selecionados em pixels incertos | 0 | 0 |
| Manchas censuradas por contexto | 2 | 0 |
| Manchas censuradas por suporte | 2 | 0 |
| Registros ≥P95 | 56 | 16 |
| Células de 1 m com registros ≥P95 | 10 | 6 |

Percentis lineares recalculados a partir dos retornos normalizados, com a
mesma observação, máscara e propriedade de unidade em bordas. Diferença
**20,91173960 m**, arredondada 20,91 m. As contagens 1110/310 e
P95/IQR coincidem com a coorte congelada dentro de 1e−9 m. Registros de origem
(folha/índice) são únicos; H=Zabsoluto−TIN coincide exatamente, sem dupla
normalização. As classes candidatas são {'3': 525, '4': 62, '5': 523} na unidade 1
e {'3': 310} na 2; isso não valida a classificação do produtor.

Na unidade alta, 56 registros em 10 células de 1 m estão em/acima do P95. Há um
agrupamento alto nos perfis, além de retornos inferiores; o percentil não
decorre de um único registro máximo. O padrão espacial não foi identificado
como copa verdadeira por referência externa. Padrões lineares nos retornos
também não autorizam, por inspeção do próprio LiDAR, reclassificação segura.

### Reprodução localizada do terreno

Foram reconstituídas somente as duas janelas pertinentes a partir dos blocos
MDT já decodificados, sem nova decodificação LAZ, processamento PyCrown ou
escrita nos caches originais:

| Janela de 200 m | Vértices MDT | Retornos verificados | Maior diferença de terreno (m) | Maior distância ao MDT (m) |
|---|---:|---:|---:|---:|
| 1589/37036 | 24580 | 1110 | 0,000000000 | 0,890 |
| 1592/37035 | 45365 | 310 | 0,000000000 | 0,395 |

O terreno foi reproduzido exatamente nos 1420 retornos selecionados. Isso é
controle interno da interpolação e da fórmula, não acurácia absoluta.

### Flags, bordas e recortes diagnósticos

Ambas as unidades têm observação integral. Existem 5 m²/2 m² com flag de classe 1
alta na unidade, mas **nenhum dos retornos selecionados** cai nesses pixels.
Excluí-los, portanto, não altera os percentis. Essa tela só detecta a condição
específica de classe 1 alta e não certifica ausência de outros erros de classe.

A unidade alta intersecta duas manchas que tocam o limite do contexto e
suporte inválido em algum ponto. A censura é atributo da mancha no contexto,
não prova de que os próprios retornos selecionados careçam de terreno. Todas
as alturas selecionadas têm status válido. `contribuicao_manchas.csv` permite
ver os componentes que sustentam cada percentil.

No interior da unidade, a 1 m da borda, permaneceram 302 e
144 registros, com P95 = 29,660 m e
8,686 m. Esse recorte não é nova máscara nem estimativa
de acurácia; apenas mostra que o contraste alto/baixo não se restringe à
atribuição exata dos pontos sobre a fronteira.

O diagnóstico espacial e as distribuições estão em
`diagnostico_par_maximo.pdf/.svg/.png`; os retornos completos das unidades
estão em dois Parquet e os polígonos em `unidades_par_maximo.gpkg`.

### Influência do extremo nas medianas

| Conjunto | Mediana original (m) | Sem apenas o par máximo (m) | Pares originais/remanescentes |
|---|---:|---:|---:|
| Sem reutilização de IDs | 2,798 | 2,396 | 16/15 |
| Pareamento principal | 2,396 | 2,296 | 25/24 |

O máximo influencia a magnitude, mas não cria sozinho a diferença mediana.
Ambos os recortes continuam descritivos e dependentes; não são testes de
significância ou justificativa para selecionar somente pares favoráveis.
As estatísticas principais dos 16/25 pares foram preservadas.

## Por que medir estabilidade das listas superiores

Spearman resume a ordenação inteira; a permanência no conjunto definido por
um corte é outro estimando. Deslocamentos próximos ao corte podem substituir
unidades sem reduzir muito a correlação global. O experimento investiga a
robustez da identificação de unidades sob escolhas de processamento,
não o acerto de uma prioridade ecológica externa.

Na coorte fixa de 68 IDs, cada lista superior tem 14 unidades. Na retenção MDS 25%,
rho=0,956010, mas apenas 10 unidades são compartilhadas:
**4 saem e 4 entram**, substituição de 28,57% por lista.
J=0,555556 é interseção/união=10/18; não significa 44,44% de unidades
substituídas. A fração substituída é 4/14=28,57%. As listas foram reconstruídas
pelos IDs/ranks, e não inferidas apenas de Jaccard. Todos os 11 cenários
substituem de 1 a 4 unidades por lista.

Isso delimita a força de uma conclusão baseada somente em rho: a concordância
global pode ser elevada enquanto a identificação de quais unidades pertencem
ao conjunto selecionado permanece sensível. Em um desenho que seleciona
unidades por um corte, é necessário relatar a permanência e os critérios desse
corte para avaliar robustez. Aqui, o corte de 20% e os sinais dos escores
continuam escolhas experimentais, sem equivalência a prioridades reais.

`permanencia_selecoes.csv` e `membros_selecoes.json` contêm as onze comparações,
interseções, perdas, entradas e IDs. O universo fixo não representa os 46 IDs
que não permaneceram elegíveis, nem implica geometria observada global fixa.

## Manuscrito

A discussão inclui a conferência do máximo e o exemplo rho alto/listas
distintas. A conclusão destaca 25 pares controlados, 16 pares sem reutilização,
medianas 2,40/2,80 m, coorte fixa 68, faixas rho/J e substituição de 1–4 em 14 IDs.
Semântica, acurácia externa, amostra intencional e análise pós-resultados
continuam limites explícitos. A revisão não aprova ou submete o artigo.

## Reprodução

Os cálculos e fontes estão registrados na execução desta revisão. Para
conferir a entrega e testar as regras de seleção:

```bash
.venv-cientifico/bin/python scripts/verificar_revisao_final_quantitativa.py
.venv-cientifico/bin/python -m pytest tests/cientifico/test_pair_review.py -q
```
