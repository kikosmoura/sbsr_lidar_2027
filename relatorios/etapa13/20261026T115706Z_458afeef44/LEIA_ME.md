# Etapa 13 — evidências, tabelas e figuras da amostra exploratória

Etapa implementada sobre a execução PyCrown v0.3.0 `20261026T034837Z_83581b7eec`.
Foram usados os produtos reais da amostra de dez corredores. Nenhuma nuvem
LAZ foi reprocessada; máscaras, indicadores, escores e seleção da etapa12
permanecem preservados. Não se converte a análise em amostra confirmatória.

## Entrega

Pacote: `/home/s299259068/Área de Trabalho/Projetos/2026/sbsr_lidar_2027/relatorios/etapa13/20261026T115706Z_458afeef44`.

- `resultados_publicaveis.json`: índice numérico com receitas, fontes e hashes.
- `indice_evidencias.md`: leitura humana dos números, afirmações e limitações.
- `figures/`: quatro figuras principais e quatro exemplos suplementares,
  cada qual em PDF/SVG vetoriais e PNG de 600 dpi.
- `tables/`: três tabelas compactas em CSV, Markdown e LaTeX, também renderizadas
  em PDF/SVG/PNG. Dados completos de amostra, rankings, ablações, sensibilidades
  e pareamentos ficam em CSV separado, sem arredondamento manual.
- `legendas.md` e `legendas.json`: legendas geradas dos mesmos resultados.
- `provas_tamanho_final.pdf`: sete páginas A4 para inspecionar os elementos nas
  larguras de 86 mm ou 178 mm; não é o manuscrito nem um PDF para submissão.
- `selecao_exemplos.json`: regra, IDs, categoria e tamanho de cada grupo.
- `auditoria_apresentacao.json`, `manifest.json` e relatórios de conferência:
  fontes, dimensões, tipografia, ambiente e proveniência.

## Números que os elementos apresentam

A avaliação contém 114 unidades, e o desenvolvimento,
30; a meta de avaliação era 120,
com déficit de 6 unidades. Não houve reposição das
unidades inelegíveis. O universo físico de 50 m contém 753
fragmentos e as três escalas somam 3121 unidades.
As 118 fontes MDT/MDS de 59 pares foram
decodificadas na etapa12: 345,062,484 registros. A soma
contém dependência entre produtos/retornos e não mede observações independentes.

A área observada varia de 81.51% a
99.84%. Nos mapas, não processado, NoData no
contexto, observado sem copa detectada e copa estimada têm representações
distintas. Nenhum desses estados recebe o rótulo de ausência verdadeira de árvore.

Na ablação primária A/A+3D, ρ=0.6682 e
Jaccard top20%=0.3529. Cada lista contém
23 unidades e compartilha 12.
Há 12 mantidas, 11 que saem,
11 que entram e 80 fora de ambas.
As posições desenhadas são ordinais com desempate por ID; ρ usa ranks médios.
Mudança de ranking não equivale a melhora de diagnóstico ou utilidade real.

Os cenários pareados mantêm de 78 a
114 IDs elegíveis. A faixa de ρ é
0.9313–0.9949;
a de J é 0.5000–0.9167.
São universos condicionais diferentes, não uma garantia de estabilidade
simultânea de todas as unidades. Não foram criados IC ou p-valores.

Os pareamentos de cobertura semelhante são apenas descritores: há
538 pares na avaliação, com diferença mediana de P95
de 5.341 m. Os pares não são réplicas
independentes, e os percentis descrevem retornos, não alturas de árvores individuais.

## Escolha e uso no artigo

F01 mostra suporte dos dez polígonos; F02 compara a máscara 2D com Hmáx no
mesmo recorte; F03 apresenta acordo/desacordo dos rankings; F04 apresenta
estabilidade e n remanescente. T01 resume amostra e suporte; T02 distingue
indicadores/estimandos; T03 resume a ablação nas duas coortes.

O exemplo principal é o primeiro hash da coorte de avaliação. Os quatro
suplementares usam o primeiro hash dentro de cada grupo: mantida, sai, entra
e fora de ambos. A regra não usa magnitude de mudança ou aparência da copa.
As ilustrações são escolhidas depois dos resultados e não são validação.
Todas compartilham extensão de 140 m, CRS EPSG:31983 e a mesma escala de altura,
sem saturar pixels de copa. Norte indicado é o da grade UTM.

Para o limite de quatro páginas, priorizar as quatro figuras e três tabelas
compactas somente conforme o espaço real da futura redação. Se precisar
reduzir, T01 mantém o suporte mesmo que F01 vá para suplemento; F04 mantém n
explícito e não deve perder essa informação. Não inserir os quatro exemplos
suplementares no corpo por padrão. A seleção final e o encaixe no manuscrito
são trabalho da etapa14/15, sem remover resultados negativos.

## Formato e verificações

O modelo PDF fornecido foi lido e conferido: colunas de 86 mm, largura dupla
de 178 mm, Times New Roman; legendas externas de 9 pt em negrito. Textos internos
usam no mínimo 7 pt e tabelas 8 pt. PDF/SVG preservam vetores; fontes do PDF são
incorporadas, e PNG tem 600 dpi. Foram corrigidos glifos ausentes e sobreposições
nas versões preliminares; o pacote final passou em conferência automática e visual.

Normas do evento reconsultadas em 26/10/2026 na
[página oficial de submissão](https://proceedings.science/cfp/sbsr-2027?lang=pt-br).
O limite publicado inclui todos os elementos em quatro páginas PDF. As dimensões
vieram do modelo fornecido, preservado por hash. Isso não certifica conformidade
de um manuscrito ainda não composto. A página inicial indicada respondeu403;
a página oficial de normas estava acessível. Proveniência editorial em
`relatorios/etapa13/fontes_editoriais_verificadas.json`.

Verificações: 195 testes científicos aprovados, incluindo12 novos;
193 verificações de receitas, universos, top, Spearman,
tipografia, dimensões, CRS, NoData e integridade. Regeneração demonstrada por
hashes de CSV e figuras nos três formatos, sem edição manual. Os arquivos
operacionais mutáveis da etapa12 foram preservados em snapshots antes da atualização
do estado; os demais artefatos da etapa12 continuam conferidos.

## Interpretação e limite de conclusão

É sustentado que a amostra e as perdas existem e foram quantificadas.
A mudança de ranking e as diferenças3D são exploratórias. A estabilidade é
parcial e condicionada ao suporte. Acurácia de máscara, posições de topo,
contornos exatos, superioridade do3D e extrapolação municipal não foram testadas.
I4 permanece densidade de manchas, e sementes/copas estimadas não são árvores
verificadas. I5 é auxiliar; A/A+3D usam I1/I4/I6/I7. B/C continuam indisponíveis,
pois os eixos da nova amostra não foram revalidados. Os filtros geométricos
completos do piloto anterior não foram executados neste braço PyCrown.

## Reprodução

```bash
.venv-cientifico/bin/python scripts/gerar_evidencias_etapa13.py
.venv-cientifico/bin/python scripts/verificar_etapa13.py
```

A primeira linha cria uma nova pasta versionada e atualiza
`relatorios/etapa13/ultima_execucao.json`, preservando versões anteriores.
O verificador lê esse ponteiro ou recebe `--root`. Configuração em
`configs/apresentacao_etapa13.yaml`; fontes/rótulos não são inventados quando
algum grupo não tem exemplos. Redação/submissão não foram iniciadas nesta etapa.
