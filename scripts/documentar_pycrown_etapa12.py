"""Consolidar somente evidências de execução e auditoria realmente presentes."""
from pathlib import Path
import json
import re
import geopandas as gpd
import pandas as pd
from sbsr_lidar.storage import read_json,atomic_write_json,fingerprint


def main():
    report=Path('relatorios/etapa12');r=read_json(report/'execucao.json');v=read_json(report/'verificacao_independente.json')
    resume=read_json(report/'retomada.json')
    if not v['ok'] or not resume['all_cases_cache_hit']:raise ValueError('Auditoria e retomada devem passar antes de concluir')
    exported=read_json(report/'exportacao_qgis.json')
    if fingerprint(Path(exported['package']['path']))!=exported['package']:raise ValueError('GeoPackage consolidado mudou')
    pooled_proof=read_json(report/'sensibilidade_agrupada.json')
    if not pooled_proof['all_22_predeclared_scenario_role_pairs_present'] or fingerprint(Path(pooled_proof['output']['path']))!=pooled_proof['output']:
        raise ValueError('Consolidação de sensibilidade não confere')
    base=Path(r['products_root']);cohort=gpd.read_parquet(base/'coorte_selecionada.parquet');physical=gpd.read_parquet(base/'indicadores_multiescala.parquet')
    stats=pd.read_parquet(base/'concordancia_ablacao.parquet');sens=pd.read_parquet(base/'sensibilidade_cenarios.parquet')
    agreements=stats.loc[stats.variant_id.eq('A_plus_3D__I6_I7__Vplus__w0.5')&stats.scope.eq('conditional_canopy')&stats.top_fraction.eq(.2)]
    frame=pd.DataFrame(v['sample']);frame.to_csv(report/'amostra_real.csv',index=False)
    original_criteria=pd.read_csv('docs/criterios_evidencias_etapa11.csv')
    revised={
        'C11_01':('atendido_na_amostra_exploratoria','Hashes, decodificação integral, auditoria independente e prova de retomada.'),
        'C11_02':('parcial_utilizavel_no_suporte','TIN5, retenção interna de pontos/blocos e costuras; fração observada por unidade; sem acurácia absoluta.'),
        'C11_03':('pendente_para_acuracia_externa','Execução exploratória sem referência expressamente autorizada; máscara e identidade de árvore continuam não validadas.'),
        'C11_04':('atendido_tecnicamente','NoData, ausência de MDS, terreno/H sem suporte e QC separado; nenhuma área desconhecida vira ausência de árvore.'),
        'C11_05':('limitado_a_grade_A_Amais3D','Eixos desta amostra não revalidados; B/C indisponíveis, sem renomear A+3D como C.'),
        'C11_06':('contexto20m_e_censura_registrados','Mosaico antes de segmentar; contexto não expande medição. Comparação entre halos não repetida nesta versão.'),
        'C11_07':('interpretacao_exploratoria','I4=manchas; densidade de sementes separada; I5/I6/I7 são retornos; sem benefício universal ou árvore verdadeira.'),
        'C11_08':('estabilidade_pareada_nao_garantia_global','Doze cenários, 110 pares locais e22 agrupados; suporte e IDs comuns por par, com perdas; sem afirmar estabilidade sob todos os cenários simultâneos.'),
        'C11_09':('nao_testavel_sem_referencia','Nenhum alvo independente usado; discordância e IoU entre cenários não são melhora de diagnóstico ou acurácia.'),
        'C11_10':('amostra_exploratoria_materializada','Dez corredores, dois desenvolvimento/oito avaliação; grupos provisórios; sem poder, independência certificada, IC ou inferência municipal.'),
        'C11_11':('executado_e_medido_na_amostra','Driver de múltiplos corredores, janelas, orçamento e retomada demonstrados; não garante escala municipal.')}
    original_criteria['status_etapa12']=original_criteria.criterion_id.map(lambda x:revised[x][0])
    original_criteria['evidencia_etapa12']=original_criteria.criterion_id.map(lambda x:revised[x][1])
    original_criteria.to_csv(report/'reavaliacao_criterios.csv',index=False)
    resources=v['resources'];rows=[]
    test_total=int(re.search(r'(\d+) passed', (report/'testes_cientificos.txt').read_text()).group(1))
    shortfall=max(0,r['sample']['target_evaluation_units']-r['sample']['selected_evaluation_units'])
    pooled=pd.read_parquet(base/'sensibilidade_rankings_agrupada.parquet')
    pooled_eval=pooled.loc[pooled.role.eq('evaluation')]
    for x in v['sample']:
        rows.append(f"| {x['corridor_id']} | {x['role']} | {x['observed_fraction']:.2%} | {x['segments_intersecting_P']} | {x['seeds_inside_P']} | {x['connected_patches_intersecting_P']} | {x['eligible_units_50m']} | {x['selected_units_50m']} |")
    rankings=[]
    for x in agreements.to_dict('records'):
        jaccard=f"{x['jaccard_exact']:.4f}" if pd.notna(x['jaccard_exact']) else 'indefinido: lista pequena'
        rankings.append(f"| {x['case']} | {x['n']} | {x['spearman_rho']:.4f} | {x['k']} | {jaccard} |")
    qc=pd.read_parquet(base/'qc_fontes.parquet');unique_sources=qc.drop_duplicates(['product','tile'])
    raw_count=int(unique_sources.declared_points.sum());visits=int(qc.declared_points.sum())
    terrain_rows=[];seam_rows=[];height_rows=[]
    for cid,record in r['case_results'].items():
        qa=read_json(Path(record['root'])/'qc.json');val=read_json(Path(qa['internal_validation']['path']))
        height_rows.append({'corridor_id':cid,**val['height_counts'],'duplicate_source_id_records':val['duplicate_source_id_records']})
        for w in val['terrain_holdout']:
            for m in w.get('metrics',[]):
                terrain_rows.append({'corridor_id':cid,'wx':w['wx'],'wy':w['wy'],**{k:x for k,x in m.items() if k!='common'},
                    'common_n':m['common']['n'],'common_rmse_m':m['common']['rmse_m'],'external_accuracy':False})
        for seam in val['seam_checks']:
            seam_rows.append({'corridor_id':cid,'window':str(seam['window']),'neighbor':str(seam['neighbor']),
                'tested':seam['tested'],'both_valid':seam['both_valid'],'neighbor_lost_support':seam['neighbor_lost_support'],**seam['terrain_difference_m']})
    pd.DataFrame(terrain_rows).to_csv(report/'terreno_validacao_interna.csv',index=False)
    pd.DataFrame(seam_rows).to_csv(report/'costuras_janelas.csv',index=False)
    pd.DataFrame(height_rows).to_csv(report/'alturas_QC.csv',index=False)
    text=f'''# Etapa 12 — execução exploratória com PyCrown, v0.3.0

Implementação e execução em 26/10/2026, sob autorização expressa do usuário
para prosseguir sem referência externa. O gate da amostra confirmatória v0.2.0
continua pendente. Este braço mede estrutura estimada e estabilidade interna;
não mede acurácia de vegetação, árvores verdadeiras ou melhora do diagnóstico.

## Execução observada

- Execução: `{r['run_id']}`.
- Dez corredores previamente selecionados: dois de desenvolvimento e oito de
  avaliação, em dez blocos provisórios de proximidade. Número de grupos
  independentes certificados: **não estabelecido**.
- {len(cohort.loc[cohort.role.eq('evaluation')])} unidades de avaliação e
  {len(cohort.loc[cohort.role.eq('development')])} de desenvolvimento selecionadas,
  meta máxima 120/30. Seleção por hash(seed=2027, ID) entre elegíveis de 50 m,
  sem usar escores ou discordância. Todas as {len(physical)} unidades físicas
  de 25/50/100 m, inclusive exclusões, permanecem na tabela.
- 59 pares de folhas (118 arquivos) no plano de contexto de 20 m; 16 arquivos
  faltantes adquiridos em insumos_complementares. Não houve lote municipal.
- {len(unique_sources)} fontes distintas com {raw_count:,} registros declarados;
  {len(qc)} visitas às fontes com {visits:,} registros decodificados. Nesta
  seleção não houve compartilhamento de folha entre corredores. CRC dos ZIPs
  e contagem integral conferidos; contagens MDT/MDS não são réplicas independentes.
- 12 cenários por corredor, 120 segmentações; 110 pares de sensibilidade com
  interseção vetorial do suporte observado e IDs primários fixos. Unidades que
  perdem elegibilidade são informadas, sem substituir por outras favoráveis.
- Tempo da fase monitorada: {resources['elapsed_seconds']/60:.2f} min, excluindo
  instalação, downloads prévios e hashing inicial das entradas; pico amostrado
  de RAM do processo e filhos: {resources['peak_rss_gib']:.3f} GiB, orçamento
  {resources['budget_gib']} GiB. Um trabalhador, amostragem de recursos a 1 s.
- {len(v['checks'])} verificações de produtos aprovadas; retomada demonstrada
  nos dez casos por checkpoints, sem decodificar novamente as nuvens.

| Corredor | Papel | Área observada | Segmentos que intersectam P | Sementes em P | Manchas em P | Elegíveis 50 m | Selecionadas |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Sementes dentro de P e segmentos que intersectam P são estimandos diferentes:
uma copa pode cruzar o limite com sua semente fora do corredor. As contagens
acima não são inventário de árvores. Áreas observadas e limites não foram
expandidos pelo halo; ele serve somente ao processamento.
O suporte observado variou de {frame.observed_fraction.min():.2%} a
{frame.observed_fraction.max():.2%}; as unidades selecionadas descrevem somente
a parcela elegível, não permitem extrapolar alturas ou árvores às áreas NoData.
Os onze critérios da etapa 11 foram reavaliados em
`relatorios/etapa12/reavaliacao_criterios.csv`; o gate de referência não foi
declarado satisfeito. MDT e MDS podem compartilhar retornos; sua soma não
representa observações independentes.

**A meta de 120 unidades de avaliação não foi atingida:** faltaram {shortfall}
unidades. CO_BT_05 ofereceu 13 elegíveis e CO_MG_02 ofereceu 11, frente às 15
previstas por corredor. As seis faltantes não foram repostas por outros casos
ou por unidades abaixo dos critérios. A execução exploratória dos dez casos
foi concluída; a insuficiência amostral permanece registrada.

## Produtos para abrir no QGIS

Raiz consolidada: `{base}`.

- `produtos_pycrown.gpkg`: pacote consolidado para QGIS, com copas no contexto
  e recortadas ao corredor, sementes CHM, ápices de retornos PointZ e unidades.
- `indicadores_multiescala.parquet`: unidades 25/50/100 m, I1/I4/I5/I6/I7,
  suporte, retornos, exclusões e densidade separada de sementes estimadas.
- `todas_unidades_50m.parquet` e `coorte_selecionada.parquet`: universo e amostra.
- `escores_rankings.parquet`, `concordancia_ablacao.parquet`,
  `pares_cobertura_semelhante.parquet` e `membros_top.parquet`: A/A+3D e controles.
- `sensibilidade_cenarios.parquet`: suporte, IoU da união de copas e estabilidade
  de ranks entre cenários. IoU aqui é concordância entre algoritmos, não acurácia.
- `sensibilidade_rankings_agrupada.parquet`: os 22 pares cenário/papel,
  normalizados sobre os mesmos IDs elegíveis remanescentes da coorte congelada,
  após intersectar o suporte dentro de cada corredor; sem substituir exclusões.
- `result.json` aponta para a raiz de cada corredor. Em cada raiz:
  `primary/copas_topos.gpkg` contém copas estimadas, sementes CHM e manchas;
  `primary/topos_estimados.parquet` contém também XYZ/H e identidade do retorno
  de maior elevação absoluta no segmento. `primary/labels.tif` preserva -1 sem
  suporte, 0 observado sem segmento e rótulos positivos.
- `rasters_r1_f1/` contém CHM/terreno/suporte/contagens; `qc.json` referencia a
  auditoria interna e fontes. Todos os derivados grandes estão no HD externo.
- Figuras revisáveis: `relatorios/etapa12/figuras/`. Janelas ilustrativas seguem
  a primeira unidade por hash, não a melhor aparência de segmentação.

## Comparação descritiva A × A+3D

| Coorte | n | Spearman | k top20% | Jaccard exato |
|---|---:|---:|---:|---:|
{chr(10).join(rankings)}

Os métodos usam os mesmos IDs, máscara e denominadores dentro da comparação.
I4 continua contando manchas conectadas; não foi redefinido como número de
copas. I6/I7 são P95/IQR dos retornos candidatos dentro das copas estimadas,
com quantis exatos lineares. A normalização é descritiva na própria coorte;
não há treinamento preditivo. Peso zero, sinal oposto do IQR, I6 isolado e I6
duplicado foram preservados como controles. B/C longitudinais estão
indisponíveis porque eixos desta nova amostra não foram revalidados.

Na sensibilidade agrupada da avaliação, permaneceram entre
{int(pooled_eval.paired_eligible_units.min())} e {int(pooled_eval.paired_eligible_units.max())}
das 114 unidades primárias, conforme o cenário. No conjunto remanescente de
cada par, Spearman variou de {pooled_eval.spearman_rho.min():.4f} a
{pooled_eval.spearman_rho.max():.4f}, e Jaccard top20% de
{pooled_eval.jaccard_exact.min():.4f} a {pooled_eval.jaccard_exact.max():.4f}.
Essas faixas descrevem universos condicionais diferentes; não demonstram
estabilidade para todas as 114 unidades sob todos os cenários ao mesmo tempo.

## Método e limites

Protocolo: `docs/protocolo_pycrown_v0_3_0.md` e
`configs/protocolo_congelado_pycrown_v0_3_0.json`. PyCrown original GPLv3,
commit 3d8db4e03d82d5846ff68fc5fa9c18803d823464, preservado e conferido por hash.
O adaptador executa detecção original e os backends Numba originais em
`.venv-pycrown`, separado do ambiente científico. Não executa a pilha de IO
legada nem a correção original baseada em DSM. O retorno de maior Z é um
produto adicional explicitamente distinto da semente CHM.

H contínuo = Z absoluto − TIN de raio 5 m, sem correção geoidal adicional.
Classes 3/4/5, CHM de máximos sem suavização ou preenchimento; crescimento
PyCrown estritamente H>limiar. Janelas de 200 m normalizam os pontos, com 10 m
de terreno ao redor; o CHM é mosaificado por corredor antes de segmentar.
Um dono nominal de folha e de janela evita duplicação de borda. Em 2 m, o
raio de detecção nominal 3 m é arredondado para 4 m, explicitamente registrado.
Não existe fronteira subpixel exata de copa nesta análise em raster.

O QC interno inclui todos os registros comprimidos, headers, unidades/datum,
unicidade de IDs, fórmula H, NoData e conservação de áreas. Em até três janelas
por corredor, escolhidas por hash, faz retenção de pontos/blocos MDT e checa
costuras. Isso avalia interpolação do mesmo sensor, não acurácia altimétrica
absoluta. A comparação com user_data é somente consistência interna.

Sem referência independente não se estima omissão/comissão, erro posicional,
erro de contorno ou número real de árvores. A classificação LAS pode confundir
vegetação e estruturas; a tela de incerteza desta rota identifica classe 1 alta
e suporte, sem executar os filtros geométricos completos do piloto anterior.
Segmentação pode dividir uma copa ou juntar várias. Parâmetros alteram
detecção e áreas. Corredores estreitos e bordas têm censura registrada.
Na prévia CO_IP_05 há feições lineares altas segmentadas no contexto; sem
rótulo independente sua natureza arbórea não está confirmada. A inspeção
visual deste produto não substitui validação semântica.
Geometrias de 2026 são confrontadas a LiDAR de 2020; o estudo é retrospectivo.
Não se declara causalidade, prioridade normativa, biomassa, conectividade
funcional, significância ou inferência para toda São Paulo.

## Reprodução e retomada

```bash
.venv-cientifico/bin/python -m sbsr_lidar --config configs/terreno_congelado_etapa04.yaml sample-pycrown --plan-only
.venv-cientifico/bin/python scripts/executar_pycrown_etapa12.py
.venv-cientifico/bin/python scripts/exportar_pycrown_etapa12.py
.venv-cientifico/bin/python scripts/verificar_etapa12.py
.venv-cientifico/bin/python scripts/consolidar_sensibilidade_pycrown_etapa12.py
.venv-cientifico/bin/python scripts/visualizar_pycrown_etapa12.py
```

Para um caso de desenvolvimento, adicionar `--case CO_PR_03`. Complementos
faltantes exigem `--download-missing`; o plano é limitado aos dez casos.
O wrapper grava um JSON por execução e preserva `relatorios/etapa12/execucao.json`
como primeira execução base. Auditoria, exportação e figuras leem esse ponteiro;
novas retomadas ficam em `ultima_execucao.json` e nos manifestos, sem substituir
o custo observado da execução base por um tempo de cache.
Reexecutar o mesmo comando confere hashes e reutiliza fontes, janelas e casos.
Cache inclui entradas, geometria, parâmetros, código e versões do ambiente;
fontes de extração/normalização e análise têm identidades separadas.

Ambiente isolado: criar com `python3.10 -m venv .venv-pycrown` e instalar usando
`.venv-pycrown/bin/python -m pip install -r relatorios/etapa12/requirements_pycrown.lock.txt`.
As fontes originais e LICENSE estão em `third_party/pycrown_upstream`.

Verificações: {test_total} testes científicos ({test_total-168} novos PyCrown) e 25
testes do downloader com seus subtestes; relatórios em `relatorios/etapa12`.
A calibração preliminar foi preservada em `calibracao_CO_PR_03.json`; após
conferência, a consolidação passou a traduzir explicitamente os papéis em
português para os identificadores internos. Nenhuma escolha de peso, cobertura
ou raio foi ajustada para favorecer os resultados de avaliação.

Os manifestos preservam também duas interrupções controladas: correção de
campos auxiliares de elegibilidade/contagem e inclusão da geometria nominal
da grade na identidade do cache. A execução final usa o código corrigido em
todos os casos; não mistura produtos dessas tentativas com a amostra final.

Próximo passo: etapa 13, quando solicitada, pode preparar o pacote de artigo
exploratório a partir destas evidências, sem declarar validação externa.
'''
    Path('docs/execucao_pycrown_etapa12.md').write_text(text)
    decisions=Path('docs/decisoes_metodologicas.md')
    if 'D126' not in decisions.read_text():
        with decisions.open('a') as f:
            f.write('''\n\n## Etapa 12 — nova rota exploratória autorizada, 26/10/2026\n\n| ID | Decisão | Motivo e limite |\n|---|---|---|\n| D126 | Criar v0.3.0 sem referência externa por solicitação expressa | Executar estimativas e estabilidade; gate confirmatório v0.2 permanece pendente |\n| D127 | Reutilizar dez corredores/blocos da proposta v0.2 | Dois desenvolvimento/oito avaliação; sem seleção por vantagem do 3D |\n| D128 | Halo 20 m e somente oito pares adicionais | Comporta raios de detecção/copa; medição continua em P original |\n| D129 | PyCrown por commit e ambiente isolado | Rotinas originais de detecção/Dalponte/CIRC; IO atual, GPL preservada, sem alegar pipeline legado completo |\n| D130 | CHM de máximo H das classes345 sem preenchimento/suavização | Suporte, NoData e contaminação LAS explícitos; float32 no algoritmo, float64 nas alturas |\n| D131 | Janelas de normalização e mosaico integral por corredor | Um dono de retorno e segmentação antes de recortar; fronteiras de janela não definem copas |\n| D132 | Separar sementes CHM de retorno de maior Z absoluto | Estimandos/proveniência explícitos; sem chamar posição de topo verdadeiro |\n| D133 | I4 mantém densidade de manchas | Densidade de sementes é coluna adicional; copas não equivalem a árvores verificadas |\n| D134 | Congelar 12 cenários e usar suporte vetorial comum | Resolução/limiar/raios/algoritmo/densidade; raio3 em resolução2 corresponde a4 m; sem otimizar rankings |\n| D135 | Hash de ID para até15 elegíveis por corredor | Preservar exclusões e eventuais faltas; grupos não certificados independentes; sem p/IC |\n| D136 | QA interno de MDT e costuras em até3 janelas por hash | Mesmo sensor não substitui acurácia absoluta ou validação da máscara |\n| D137 | Concluir somente o braço exploratório após auditoria e retomada | Preservar v0.1/v0.2, labels pendentes e gate externo; produtos concretos no HD |\n''')
    state_path=Path('docs/estado_projeto.json');s=read_json(state_path)
    s.update(etapa_atual='12',status='etapa12_exploratoria_pycrown_concluida_com_deficit_amostral' if shortfall else 'etapa12_exploratoria_pycrown_concluida',atualizado_em='2026-10-26',amostra_exploratoria_executada=True)
    s['amostra_exploratoria_pycrown']={'protocol_version':'0.3.0','status':'concluida','referencia_externa':False,
        'acuracia_externa_avaliada':False,'modo_municipal':False,'run_id':r['run_id'],'products_root':str(base),
        'sample':r['sample'],'resources':resources,'evaluation_target_reached':not bool(shortfall),'evaluation_unit_shortfall':shortfall,
        'reference_gate_0_2_fulfilled':False,'report':'docs/execucao_pycrown_etapa12.md'}
    s['etapas']['12'].update(status='concluida',escopo_concluido='amostra_exploratoria_pycrown_v0_3_0',
        amostra_confirmatoria_v0_2_0_executada=False,artefatos=['docs/execucao_pycrown_etapa12.md','docs/manifesto_etapa12.json',str(base),
        'relatorios/etapa12/verificacao_independente.json','relatorios/etapa12/retomada.json'])
    s['etapas']['12']['deficit_unidades_avaliacao']=shortfall
    atomic_write_json(state_path,s)
    artifacts=[Path('README.md'),Path('docs/schemas/run_manifest.schema.json'),Path('docs/schemas/crown_design.schema.json'),Path('docs/execucao_pycrown_etapa12.md'),decisions,state_path,Path('configs/amostra_pycrown_exploratoria_v0_3_0.yaml'),
        Path('configs/protocolo_congelado_pycrown_v0_3_0.json'),Path('docs/protocolo_pycrown_v0_3_0.md'),Path('tests/cientifico/test_crown.py')]
    artifacts += [p for p in report.rglob('*') if p.is_file() and not p.name.endswith('.part') and p.name!='documentacao_stdout.txt']
    artifacts += [p for p in Path('src/sbsr_lidar').glob('*.py')]
    artifacts += [p for p in Path('scripts').glob('*etapa12.py')]+[Path('scripts/pycrown_worker.py')]
    artifacts += [Path('third_party/PYCROWN_ADAPTER.md')]+[p for p in Path('third_party/pycrown_upstream').rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    artifacts += [p for p in base.glob('*') if p.is_file()]+[Path('configs/terreno_congelado_etapa04.yaml')]
    artifacts += [Path(c['root'])/'complete.json' for c in r['case_results'].values()]
    atomic_write_json(Path('docs/manifesto_etapa12.json'),{'stage':'12','version':'0.3.0','status':'completed_exploratory_only',
        'user_authorized_without_external_reference':True,'external_accuracy_evaluated':False,'confirmatory_gate_0_2_fulfilled':False,
        'municipal_executed':False,'run_id':r['run_id'],'run_manifest':fingerprint(Path(r['run_manifest'])),
        'sample':r['sample'],'evaluation_target_reached':not bool(shortfall),'evaluation_unit_shortfall':shortfall,'checks_passed':len(v['checks']),'resources':resources,
        'artifacts':[fingerprint(p) for p in sorted(set(artifacts))],
        'case_manifests_include_recursive_output_hashes':True,
        'protected_0_2_protocol':fingerprint(Path('configs/protocolo_congelado_amostra_v0_2_0.json')),
        'limitations':['no_external_mask_or_tree_reference','not_a_municipal_probability_sample','provisional_spatial_groups','tree_identity_and_exact_crown_boundaries_unverified']})
    print(json.dumps({'status':s['status'],'sample':r['sample'],'checks':len(v['checks'])},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
