# Etapa 12 — amostra exploratória PyCrown, versão 0.3.0

Autorização do usuário em 26/10/2026: “implemente a etapa 12 sem e referencia
externa e usando o pycrown [...] pode proceder com a implementação”. Esta
autorização permite execução exploratória sem referência. Não satisfaz o gate
de validação da máscara da versão 0.2.0. Preservam-se os produtos e protocolos
0.1/0.2; não se declara pré-registro retroativo nem acurácia externa.

Reutilizam-se exatamente os dez corredores e blocos propostos na etapa 11:
oito de avaliação e dois de desenvolvimento. Não se seleciona por discordância
ou vantagem do 3D. Blocos de proximidade são provisórios; independência e
permutabilidade não foram demonstradas. Nenhuma estimativa municipal, teste
de significância, intervalo de confiança ou melhora em relação à verdade.

MDT/MDS de 2020, EPSG:31983, domínio de medição no polígono original; contexto
de 20 m, aumentado nesta versão para comportar os raios de sensibilidade.
Completar somente pares faltantes em pasta própria. Um trabalhador, LAZ em
blocos, janelas de 200 m com 10 m de contexto de terreno, raio TIN de 5 m e
orçamento de 8 GiB. Sem correção geoidal adicional. Pontos MDS têm um único
dono nominal de folha e de janela. H contínuo = Z absoluto − TIN(X,Y).
NoData, QC, ausência de retorno e ausência de candidato são estados distintos.
Não interpolar buracos no CHM. O mosaico do corredor completo precede a
segmentação; fronteiras das janelas não cortam IDs de copa.

PyCrown original (GPLv3), commit 3d8db4e03d82d5846ff68fc5fa9c18803d823464,
fonte https://github.com/manaakiwhenua/pycrown, preservado em third_party.
Um processo isolado chama os métodos originais de máximos locais e os módulos
Numba originais Dalponte/CIRC. IO é adaptado a Rasterio/Laspy2. Não se afirma
executar o pipeline legado completo ou a correção DSM original. Centroide de
platô fora do próprio máximo é ajustado ao pixel pertencente mais próximo,
com posição original e alteração registradas. Publicar separadamente a semente
CHM e o retorno de maior Z absoluto dentro do segmento, com XYZ/H e fonte.

CHM candidato = máximo H por célula das classes 3/4/5 com QC e terreno válidos;
sem suavização, preenchimento de lacunas ou corte implícito de 60 m. Entrada
PyCrown float32, estatísticas de retornos float64. Principal: 1 m, H > 3 m,
raio de detecção 3 m, raio máximo CIRC 8 m, th_seed=0.7, th_crown=0.55.
O parâmetro ws original significa raio; as unidades são convertidas pelo
próprio método de detecção. Crescimento original também usa H estritamente
maior que o limiar; diferença para o baseline H>=3 é registrada.

Doze cenários fixos: principal; resolução 0.5/2 m; raio de detecção 2/5 m;
altura 2/5 m; raio de copa 6/12 m; Dalponte padrão; retenção determinística
de 50/25% dos registros MDS, semente 2027. Uma mesma identidade folha/índice
LAZ mantém subconjuntos aninhados. MDT não é rarefeito. Concordância espacial
entre cenários mede estabilidade interna, não acurácia. Comparações físicas
pareadas entre cenários exigem interseção vetorial do suporte observado.

Indicadores primários em grades 25/50/100 m; sensibilidade física em 50 m.
I1 = área de copa estimada / área observada; I4 mantém a densidade de manchas
conectadas da união de copas, nunca o número de árvores. Uma coluna separada
registra a densidade de sementes estimadas. I5/I6/I7 são média/P95/IQR dos
retornos candidatos dentro da copa; não médias de árvores. Elegibilidade:
área>=25 m², observado>=95%, copa>=10 m² e >=50 retornos vegetais para altura.
Unidades pequenas, sem copa ou sem suporte permanecem na tabela com motivos.

Selecionar até 15 unidades elegíveis de 50 m por corredor usando hash(seed,ID),
antes dos escores. Meta de avaliação 120, desenvolvimento 30; eventual falta
não será compensada por escolha favorável. A/A+3D usam a mesma coorte e
normalização por ranks médios (r−0.5)/n, peso principal 0.5, top20%, controles
de peso 0/.25/.5/.75, sinal oposto do IQR, I6 isolado e duplicado. H1 compara
coberturas semelhantes sem tratar pares como réplicas independentes. Sem eixo
revalidado nesta nova amostra, B/C longitudinais ficam indisponíveis.

Os resultados são topos e contornos estimados em resolução de raster. Sem
referência não se conhece erro de posição, omissão, comissão ou contorno real;
não se chama cada segmento de árvore verdadeira. A finalidade é avaliar
viabilidade, estrutura e estabilidade para subsidiar o artigo SBSR 2027.

Conversão discreta: raio de detecção efetivo = ceil(raio_m/resolução) × resolução. Na resolução de 2 m, o raio nominal de 3 m corresponde a 4 m; registrar ambos. Isso é definido antes da execução dos casos.
