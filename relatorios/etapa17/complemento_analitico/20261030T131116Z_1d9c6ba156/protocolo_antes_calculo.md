# Complemento analítico autorizado na etapa 17

Este complemento responde à solicitação de investigar informação vertical entre
unidades semelhantes em 2D e estabilidade em coorte fixa. É uma extensão
exploratória **pós-resultados**, motivada pela crítica ao artigo; não é um
pré-registro retroativo nem altera o protocolo confirmatório v0.2. A execução
PyCrown v0.3.0, seus arquivos e o artigo da etapa15 serão preservados.

As regras abaixo e o YAML serão copiados e autenticados antes de calcular os
novos desfechos. O universo principal contém os 114 IDs de avaliação originais,
sem desenvolvimento, reposição ou nova seleção por resultados. Não há novo
processamento de LAZ, download ou ajuste de PyCrown.

## Informação vertical condicional aos descritores horizontais

Primeiro reproduzir os 538 pares antigos, com diferença de cobertura I1 até
0,05 e razão de áreas observadas até 2. A ampliação exige também diferença de
R(I4) até 0,10, onde R=(posto médio−0,5)/114 é calculado uma vez na coorte
original de avaliação. I4 continua densidade de manchas, não árvores. A análise
principal é dentro de cada corredor; pares entre corredores são apresentados
separadamente para expor possível composição geográfica.

Esses limites definem **semelhança operacional**, não equivalência estatística
ou ecológica. A sensibilidade inclui todas as nove combinações de limites I1
0,025/0,05/0,10 e R(I4) 0,05/0,10/0,20; o principal não será escolhido pela
maior diferença vertical. Publicar todos os pares, número de IDs/corredores e
diferenças absolutas de I6=P95(H) e I7=IQR(H). Apresentar medianas, quartis e
frações com diferenças ≥2/5/10m, apenas como descritores, sem convertê-las em
limiares de relevância ou acurácia. Não há modelo de erro externo que autorize
dizer que toda diferença supera o erro de medição.

Para reduzir o peso de unidades com muitos vizinhos, apresentar também a
mediana das diferenças por unidade, seguida do resumo dessas medianas. Uma
checagem sem reutilização de IDs selecionará pares dentro do corredor por
menor distância horizontal: máximo das duas diferenças divididas por seus
limites, depois soma dessas distâncias, depois IDs. A seleção gulosa não usa
altura e não promete cardinalidade máxima. Não reutilizar IDs reduz a
dependência por compartilhamento, mas não certifica independência espacial.
Reportar resultados nulos, poucos pares e corredores sem pares.

O estimando é variação vertical observada sob proximidade em I1/I4, **antes de
aplicar pesos de ordenação**. Isso pode sustentar complementaridade descritiva
nessa resolução de semelhança; não prova independência estatística,
irrecuperabilidade por qualquer função não linear, melhoria de diagnóstico,
correção da máscara ou prioridade real de intervenção.

## Estabilidade e perda de elegibilidade

Reproduzir as 11 comparações publicadas para avaliação. Para cada cenário s,
F_s são os IDs originais elegíveis nos dois lados da interseção vetorial
observada V_principal∩V_s. A coorte fixa é F*=interseção de todos os F_s, sem
reposição e sem escolher cenários mais favoráveis. Publicar a lista de IDs,
contribuição de cada corredor, contagens e motivos de exclusão dos 114 em cada
cenário. Perda por área observada insuficiente será distinguida de insuficiência
de copa/retornos; inelegibilidade não é sinônimo automático de falta de dados.

Em F*, recalcular normalizações por postos, escores, empates a12 casas e
seleções superiores de20%, tanto para A como para A+3D (peso0,5). Os IDs de
normalização são sempre os mesmos, mas os valores dos indicadores e suas
distribuições podem mudar. Publicar rho, Jaccard exato e incluindo empates,
deslocamentos, k e os próprios rankings. Se F* estiver vazia ou pequena,
declarar não estimável conforme as guardas originais; não relaxar a regra.

Coorte fixa de IDs não significa geometria observada global fixa. Os pares já
recalculados têm suporte igual **dentro de cada comparação**, mas esse suporte
pode variar entre cenários. Para tornar isso verificável, separar três
contrastes, todos nos mesmos IDs F*:

1. Método no suporte do par: principal recalculado versus cenário recalculado.
2. Suporte: principal nativo versus principal recalculado no suporte do par.
3. Total: principal nativo versus cenário recalculado no suporte do par.

Não subtrair rho ou Jaccard para criar uma decomposição aditiva fictícia. O
contraste de suporte também inclui a renormalização decorrente da mudança dos
descritores. Documentar perda de área em F*; não declarar uma interseção global
de pixels que não foi remensurada. A estabilidade é condicional aos
sobreviventes, cuja representatividade será descrita, sem imputar estabilidade
aos excluídos. Rankings A versus A+3D também serão comparados em F* para que a
mudança de composição não fique confundida com o resultado original de114IDs.

## Entrega e limites

Código executável, testes de invariantes, fontes com SHA-256, tabelas completas,
figuras exportáveis e relatório com resultados efetivamente calculados. Uma
revisão separada do manuscrito poderá incorporar os achados sem apagar a versão
anterior. A revisão humana, o endereço autoral e a submissão continuam sujeitos
às pendências já registradas; nenhum resultado é uma validação externa.
