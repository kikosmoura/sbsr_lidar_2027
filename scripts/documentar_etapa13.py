"""Fechar a etapa13 somente depois da auditoria, dos testes e da revisão visual."""
from pathlib import Path
import json
import re
from sbsr_lidar.storage import read_json,atomic_write_json,fingerprint
from sbsr_lidar.schemas import ProjectState


def document():
    project=Path(__file__).resolve().parents[1];reports=project/'relatorios/etapa13'
    pointer=read_json(reports/'ultima_execucao.json');root=Path(pointer['output_root']);manifest=read_json(root/'manifest.json')
    audit=read_json(reports/'verificacao_independente.json');regeneration=read_json(reports/'regeneracao.json');visual=read_json(reports/'revisao_visual.json')
    if not audit['ok'] or audit['stage13_run_id']!=pointer['run_id'] or not regeneration['ok'] or not visual['approved']:
        raise ValueError('Auditoria, regeneração e revisão visual são requisitos de conclusão')
    ev=read_json(root/'resultados_publicaveis.json');items=read_json(root/'indice_figuras_tabelas.json')['items']
    m=lambda key:ev['metrics'][key]['value']
    tests=(reports/'testes_cientificos.txt').read_text();test_count=int(re.search(r'(\d+) passed',tests).group(1))
    index=['# Índice de evidências — etapa13','',f"Protocolo científico0.3.0, execução {ev['source_run_id']}. Pacote de apresentação1.0.0.",
        '', 'Cada receita do JSON é executável e inclui caminho, SHA-256, colunas, filtros e agregação. Valores derivados apontam para os operandos. Nenhum número foi digitado para ajustar uma narrativa.',
        '', '| ID | Valor | Unidade | Agregação / expressão | Fonte / colunas / filtros |','|---|---:|---|---|---|']
    for key,value in ev['metrics'].items():
        recipe=value.get('recipe');source=value.get('source_fingerprint',{})
        desc=json.dumps(recipe,ensure_ascii=False) if recipe else value.get('json_pointer') or value.get('expression')
        reference=source.get('path') or ', '.join(value.get('derived_from',[]))
        index.append(f"| {key} | {value['value']} | {value['unit']} | {desc} | {reference} |")
    index+=['','## Afirmações e limites','','| ID | Classificação | Afirmação | Evidência / limites |','|---|---|---|---|']
    for claim in ev['claims']:
        index.append(f"| {claim['claim_id']} | {claim['classification']} | {claim['statement']} | {', '.join(claim['metric_ids'])}; {', '.join(claim['limitations'])} |")
    (root/'indice_evidencias.md').write_text('\n'.join(index)+'\n')
    body=f'''# Etapa 13 — evidências, tabelas e figuras da amostra exploratória

Etapa implementada sobre a execução PyCrown v0.3.0 `{ev['source_run_id']}`.
Foram usados os produtos reais da amostra de dez corredores. Nenhuma nuvem
LAZ foi reprocessada; máscaras, indicadores, escores e seleção da etapa12
permanecem preservados. Não se converte a análise em amostra confirmatória.

## Entrega

Pacote: `{root}`.

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

A avaliação contém {m('units_evaluation')} unidades, e o desenvolvimento,
{m('units_development')}; a meta de avaliação era {m('target_evaluation')},
com déficit de {m('evaluation_shortfall')} unidades. Não houve reposição das
unidades inelegíveis. O universo físico de 50 m contém {m('all_grid_units_50m')}
fragmentos e as três escalas somam {m('all_grid_units_multiscale')} unidades.
As {m('source_files_qc')} fontes MDT/MDS de {m('source_tile_pairs')} pares foram
decodificadas na etapa12: {m('source_decoded_records'):,} registros. A soma
contém dependência entre produtos/retornos e não mede observações independentes.

A área observada varia de {100*m('observed_fraction_min'):.2f}% a
{100*m('observed_fraction_max'):.2f}%. Nos mapas, não processado, NoData no
contexto, observado sem copa detectada e copa estimada têm representações
distintas. Nenhum desses estados recebe o rótulo de ausência verdadeira de árvore.

Na ablação primária A/A+3D, ρ={m('primary_spearman_rho'):.4f} e
Jaccard top20%={m('primary_jaccard_exact'):.4f}. Cada lista contém
{m('primary_k')} unidades e compartilha {m('primary_top_intersection_n')}.
Há {m('top_group_kept')} mantidas, {m('top_group_lost')} que saem,
{m('top_group_gained')} que entram e {m('top_group_neither')} fora de ambas.
As posições desenhadas são ordinais com desempate por ID; ρ usa ranks médios.
Mudança de ranking não equivale a melhora de diagnóstico ou utilidade real.

Os cenários pareados mantêm de {m('sensitivity_paired_eligible_units_min')} a
{m('sensitivity_paired_eligible_units_max')} IDs elegíveis. A faixa de ρ é
{m('sensitivity_spearman_rho_min'):.4f}–{m('sensitivity_spearman_rho_max'):.4f};
a de J é {m('sensitivity_jaccard_exact_min'):.4f}–{m('sensitivity_jaccard_exact_max'):.4f}.
São universos condicionais diferentes, não uma garantia de estabilidade
simultânea de todas as unidades. Não foram criados IC ou p-valores.

Os pareamentos de cobertura semelhante são apenas descritores: há
{m('similar_cover_pairs')} pares na avaliação, com diferença mediana de P95
de {m('pairs_absolute_P95_difference_m_median'):.3f} m. Os pares não são réplicas
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

Verificações: {test_count} testes científicos aprovados, incluindo12 novos;
{len(audit['checks'])} verificações de receitas, universos, top, Spearman,
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
'''
    (project/'docs/evidencias_tabelas_figuras_etapa13.md').write_text(body)
    (root/'LEIA_ME.md').write_text(body)
    decisions=project/'docs/decisoes_metodologicas.md'
    if '| D138 |' not in decisions.read_text():
        with decisions.open('a') as f:f.write('''\n\n## Etapa13 — apresentação da amostra exploratória v0.3.0\n\n| ID | Decisão | Evidência / limite |\n|---|---|---|\n| D138 | Usar execução PyCrown v0.3.0 como fonte imutável | Amostra exploratória real, sem reprocessar LAZ ou satisfazer gate confirmatório |\n| D139 | A/A+3D substitui A/B/C nas figuras desta amostra | B/C sem eixo revalidado; não renomear ablação como C |\n| D140 | Cada número central tem receita e SHA-256 | Filtros/coorte/escala/versão/execução e agregações no JSON de evidências |\n| D141 | Quatro figuras principais e três tabelas em tamanho final |86/178mm, fonte>=7pt, legendas9pt; PDF/SVG/PNG600dpi; provas não são manuscrito |\n| D142 | Exemplos balanceados por categoria com primeiro hash | Mantida/sai/entra/fora; pós-resultados, ilustrativos; sem selecionar maior discordância |\n| D143 | Mostrar perdas de suporte e amostra abaixo da meta |114/120 na avaliação;30 desenvolvimento; sensibilidade usa78–114 elegíveis por par |\n| D144 | Não produzir acurácia, IC ou significância fictícios | Grupos não certificados independentes, sem alvo externo; afirmações classificadas |\n| D145 | Concluir após auditoria, provas visuais e regeneração | Fontes experimentais preservadas; snapshots dos documentos operacionais mutáveis; próxima etapa14 somente quando acionada |\n''')
    state_path=project/'docs/estado_projeto.json';state=read_json(state_path)
    state.update(etapa_atual='13',status='etapa13_concluida_evidencias_exploratorias',atualizado_em='2026-10-26')
    state['etapas']['13'].update(status='concluida',artefatos=['docs/evidencias_tabelas_figuras_etapa13.md','docs/manifesto_etapa13.json',str(root)],
        escopo='evidencias_graficas_amostra_exploratoria_pycrown_v0_3_0',run_id=pointer['run_id'],
        fonte_etapa12_preservada=True,alvo_independente_validado=False)
    state['pacote_evidencias_etapa13']={'run_id':pointer['run_id'],'output_root':str(root),'source_run_id':manifest['source_run_id'],
        'primary_figures':sum(i['primary'] and i['figure_id'].startswith('F') for i in items),
        'supplementary_figures':sum(not i['primary'] for i in items),'tables':sum(i['figure_id'].startswith('T') for i in items),
        'tests_passed':test_count,'product_checks_passed':len(audit['checks']),'external_accuracy_evaluated':False,'manuscript_written':False}
    ProjectState.model_validate(state);atomic_write_json(state_path,state)
    sources=[project/'configs/apresentacao_etapa13.yaml',project/'scripts/gerar_evidencias_etapa13.py',project/'scripts/verificar_etapa13.py',Path(__file__).resolve(),
        project/'tests/cientifico/test_publication.py',project/'docs/evidencias_tabelas_figuras_etapa13.md',decisions,state_path]
    sources += list((project/'scripts/etapa13').glob('*.py'))
    sources += [p for p in root.rglob('*') if p.is_file()]
    sources += [p for p in reports.glob('*.json') if p.is_file()]+[reports/'testes_cientificos.txt',reports/'testes_novos.txt']
    aggregate={'stage':'13','status':'completed_exploratory_evidence_package','run_id':pointer['run_id'],
        'scientific_protocol':'0.3.0','source_run_id':manifest['source_run_id'],'source_manifest12':fingerprint(project/'docs/manifesto_etapa12.json'),
        'source_products_modified':False,'external_accuracy_evaluated':False,'manuscript_written':False,'submitted':False,
        'tests_passed':test_count,'checks_passed':len(audit['checks']),'regeneration_verified':True,'visual_review':visual,
        'artifacts':[fingerprint(p) for p in sorted(set(sources))],
        'mutable_stage12_snapshots':manifest['historical_mutable_snapshots']}
    atomic_write_json(project/'docs/manifesto_etapa13.json',aggregate)
    print(json.dumps({'status':state['status'],'output_root':str(root),'artifacts':len(aggregate['artifacts']),'checks':len(audit['checks'])},ensure_ascii=False,indent=2))


if __name__=='__main__':document()
