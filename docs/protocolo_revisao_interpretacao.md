# Revisão de interpretação, distribuição dos pares e erro de medição

Revisão solicitada após o complemento17. Versão0.3.2-interpretacao, de caráter
exploratório pós-resultados. Não mudar pesos, sinais, coorte, máscara, seleção
dos16pares ou qualquer produto PyCrown para obter resultado mais favorável.

1. Descrever a função dos indicadores como descritores da distribuição de
   retornos, sem converter altura ou dispersão em valor ecológico. A fórmula
   existente será mantida como configuração experimental de ordenação: os
   sinais inversos favorecem valores menores por construção, sem diagnóstico
   de degradação ou recomendação de intervenção. Renomear o símboloV+ como
   Vexp no texto é apresentação, com a mesma receita identificada como Vplus
   no código e nas evidências históricas.
2. Reapresentar os mesmos16pares selecionados apenas pela distância horizontal.
   Para |ΔP95| e |ΔIQR|, calcular mínimo, Q1, mediana, Q3 e máximo por quantis
   lineares. Publicar os valores por par e uma tabela compacta no artigo.
   Explicitar que distribuição assimétrica e diferenças quase nulas também
   integram a evidência; não apresentar os pares como réplicas independentes.
3. Examinar os XML oficiais MDT/MDS2020 e o atestado técnico vinculado a eles,
   confrontados com as fontes públicas consultadas. Separar declaração de
   conformidade, especificação de sensor, resolução/quantização e erros
   efetivamente estimados. Não inferir RMSE ou erro máximo de PEC-PCD ClasseA,
   tamanho de pixel, escala LAS ou descrição genérica de outro levantamento.
4. Resumir controles internos **já executados** da v0.3.0 nos oito corredores
   de avaliação, usando todas as janelas registradas por hash e somente TIN5.
   Separar pontos e blocos MDT reservados. Publicar RMSE por janela, resumo
   dessas distribuições e fração válida, condicionados ao suporte. Não tratar
   resíduos do mesmo sensor como acurácia externa de H ou de copas. Não
   agregar desenvolvimento e avaliação nem escolher o interpolador vencedor.
5. A propagação de incerteza de H=Z−TIN depende de erros em ambas as parcelas
   e sua covariância. Classificação, seleção de retornos, oclusão e segmentação
   introduzem componentes adicionais. Sem resíduos independentes e modelo de
   erro apropriado, não concluir que diferenças entre percentis superam o
   erro total, nem dividir RMSE por raiz do número de retornos.

Saídas versionadas, cópia separada do artigo, fontes/receitas comSHA-256 e
verificações compatíveis. Preservar a entrega17 e seus estados históricos.
Nenhuma submissão, validação fictícia ou aprovação em nome do autor.
