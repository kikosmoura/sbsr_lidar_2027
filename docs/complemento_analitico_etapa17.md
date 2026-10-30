# Informação complementar e estabilidade em coorte fixa

Execução `20261030T131555Z_1d9c6ba156`; fonte PyCrown `20261026T034837Z_83581b7eec`. Extensão exploratória pós-resultados solicitada pelo autor, sem nova segmentação, escolha de peso favorável ou validação externa.

## 1. Informação vertical antes de calcular escores

Os 538 pares anteriores foram reproduzidos integralmente (mediana |ΔP95|=5,34 m). Ao exigir também |ΔR(I4)|≤0,10 e mesmo corredor, além de |ΔI1|≤0,05 e razão de áreas≤2, restaram **25 pares de 38 unidades nos 8 corredores**. R(I4) é calculado uma única vez nos 114 IDs primários.

A mediana de |ΔP95| foi **2.40 m**, quartis 0.83–6.78 m; |ΔIQR| mediano=1.85 m. 8/25 pares tiveram |ΔP95|≥5 m. Cinco metros é corte descritivo, não limiar ecológico ou erro de medição validado.

A seleção gulosa apenas por proximidade horizontal, sem reutilização de IDs, reteve **16 pares/32 unidades**, com |ΔP95| mediano=2.80 m e |ΔIQR| mediano=1.75 m. Os IDs completos e valores estão em `complementaridade_disjoint.csv`. Não há pares adjacentes nessa seleção; ainda assim, dependência espacial não foi excluída.

**Interpretação:** a evidência já não depende de mudar pesos: existem contrastes verticais nas unidades operacionalmente próximas em dois descritores horizontais. O controle reduz a diferença de 5,34 m para 2,40 m e essa atenuação deve ser apresentada. O achado sustenta complementaridade descritiva local; não prova independência, relevância ecológica, discriminação de espécies ou superioridade de diagnóstico. Diferenças pequenas e pares quase idênticos também constam nas tabelas. A ausência de máscara/altura validadas impede separar integralmente estrutura real e erro.

As nove combinações de limites estão em `complementaridade_sensitivity.csv`, com escopos dentro/entre/todos os corredores. As medianas por unidade e os oito resumos por corredor evitam apresentar538 ou 25 pares como tamanho amostral independente. A seleção sem reutilização também é sensível ao pareamento: não representa todos os pares nem maximiza a diferença vertical.

## 2. Ordenação entre os mesmos IDs e perda de elegibilidade

A interseção dos IDs elegíveis em ambos os lados de todos os 11 pares reteve **68/114 IDs (59.6%)**, dos oito corredores. Os 46 IDs excluídos não foram repostos. `coorte_por_corredor.csv` e `perfil_sobreviventes_excluidos.csv` mostram composição e seleção dos sobreviventes; CO_MG_02 reteve apenas 4/11. A estabilidade não deve ser generalizada aos114 IDs.

Em A+3D, principal/cenário no mesmo suporte de cada par e mesmos 68 IDs: **rho=0.917–0.995; J=0.556–0.867**. Todas as seleções têm k=14. Compartilham de10 a13 dos 14 IDs. O deslocamento médio absoluto varia de1.35 a5.82 posições. As11 sensibilidades anteriores também foram reproduzidas em suas coortes variáveis.

| Cenário | Elegíveis por par | Perdas com observação<95% | Outras perdas | rho fixo | J fixo |
|---|---:|---:|---:|---:|---:|
| resolution_0.5 | 87 | 20 | 7 | 0.951 | 0.647 |
| resolution_2 | 104 | 10 | 0 | 0.917 | 0.647 |
| detection_radius_2 | 114 | 0 | 0 | 0.956 | 0.750 |
| detection_radius_5 | 108 | 0 | 6 | 0.930 | 0.556 |
| height_2 | 114 | 0 | 0 | 0.975 | 0.750 |
| height_5 | 104 | 0 | 10 | 0.935 | 0.647 |
| crown_radius_6 | 114 | 0 | 0 | 0.989 | 0.867 |
| crown_radius_12 | 114 | 0 | 0 | 0.979 | 0.867 |
| dalponte_standard | 114 | 0 | 0 | 0.995 | 0.867 |
| density_0.5 | 109 | 4 | 1 | 0.975 | 0.750 |
| density_0.25 | 78 | 25 | 11 | 0.956 | 0.556 |

O contraste principal nativo/principal recalculado só no suporte do par teve rho≥0.999714, J=1 e deslocamento médio≤0.294 posições em F*. Assim, entre esses sobreviventes, a restrição de suporte teve efeito pequeno sobre a ordenação; isso não minimiza a exclusão dos demais. Os contrastes de método, suporte e total estão separados em `estabilidade_comparisons.csv`, também para A. Não são componentes aditivos.

**Geometria:** F* fixa os IDs, não uma interseção global de pixels. Cada comparação herda a mesma interseção vetorial observada nos dois lados, autenticada nas fontes da etapa12. O suporte pode variar entre cenários; `estabilidade_area.csv` registra isso por unidade. Portanto não se declara robustez sob geometria global idêntica. Normalizadores usam os mesmos 68 IDs, com indicadores novamente medidos e postos recalculados.

## 3. Como a mensagem científica muda

Formulação sustentada: “Atributos de altura revelam contrastes verticais entre unidades semelhantes em cobertura e fragmentação, sem depender da ponderação do índice. Entre IDs elegíveis em todas as sensibilidades, a concordância global é elevada, mas a composição das listas superiores permanece sensível. A perda de elegibilidade constitui um segundo limite, quantificado separadamente.”

Evitar “o LiDAR melhora a prioridade”, “as diferenças são significativas”, “há equivalência2D comprovada” ou “68 unidades representam os corredores”. O resultado mais forte é a mensuração da heterogeneidade vertical condicional e da fragilidade da seleção superior, não uma recomendação de intervenção. Pareamento pós-resultados e semântica de copa não validada permanecem limites explícitos.

## Reprodução e verificações

```bash
.venv-cientifico/bin/python scripts/analisar_complemento_etapa17.py
.venv-cientifico/bin/python -m pytest tests/cientifico/test_complementary_analysis.py -q
```

Cada execução cria pasta própria. Regras e protocolo são copiados antes dos cálculos; SHA-256 dos arquivos de entrada, selos recursivos e código constam em `proveniencia.json`. O uso das fontes não altera suas chaves ou caches. Figuras PDF/SVG/PNG600dpi estão em `figuras/`. A revisão de artigo fica em `artigo/complemento_etapa17/`; a versão15 foi preservada.

Como referência metodológica geral, a necessidade de examinar os efeitos da ponderação e a robustez das inferências em indicadores compostos é discutida no [guia do JRC](https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en). Os limites de pareamento e a coorte desta análise são decisões locais documentadas, não regras prescritas pelo guia.
