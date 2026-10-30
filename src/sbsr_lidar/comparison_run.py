"""Etapa 09: comparações descritivas rastreáveis; sem alvo independente fictício."""
from __future__ import annotations

import json
import resource
import shutil
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil

from .annotations import check_annotations
from .comparison_analysis import analyze_comparisons
from .comparison_scores import primary_variant
from .doctor import existing_parent
from .environment import environment_snapshot, source_digest
from .runtime import Run, exclusive_lock
from .schemas import RunManifest
from .storage import atomic_write_json, cache_key, fingerprint, load_cache, read_json, save_cache


def frozen_indicators(config, state, case):
    if state.get('etapas', {}).get('08', {}).get('status') != 'concluida':
        raise ValueError('Concluir etapa 08 antes da comparação')
    label = 'principal' if case == 'main' else 'adverso'
    entry = state['indicadores_piloto'][label]
    aggregate = config.paths.project_root/'docs/manifesto_etapa08.json'
    inventory = {p['path']: p for p in read_json(aggregate)['artifacts']}
    records = [fingerprint(Path(entry[k])) for k in ['manifest', 'report', 'parquet', 'csv', 'data_dictionary']]
    if any(inventory.get(p['path']) != p for p in records):
        raise ValueError('Indicadores congelados mudaram; rever etapa 08 antes de comparar')
    manifest = RunManifest.model_validate(read_json(Path(entry['manifest'])))
    if manifest.stage != '08' or manifest.status != 'completed':
        raise ValueError('Manifesto de indicadores incompatível')
    parents = [fingerprint(Path(p.path)) for p in manifest.inputs]
    if parents != [p.model_dump() for p in manifest.inputs]:
        raise ValueError('Fontes ancestrais dos indicadores mudaram')
    if manifest.config['support'] != config.support.model_dump(mode='json'):
        raise ValueError('Critérios de suporte divergem dos indicadores congelados')
    table = gpd.read_parquet(entry['parquet'])
    if (not table.unit_id.is_unique or not table.case.eq(case).all() or not table.corridor_id.eq(entry['corridor_id']).all()
            or table.scenario.nunique() != 1 or table.canopy_run_id.nunique() != 1 or table.units_run_id.nunique() != 1
            or not table.indicator_run_id.eq(entry['run_id']).all() or not table.protocol_version.eq(config.protocol_version).all()
            or table.crs.to_epsg() != config.grid.epsg):
        raise ValueError('Domínio/máscara/unidades/cenário não são comuns no arquivo de indicadores')
    eligible = table.eligible_A_plus_3D.astype(bool)
    if not np.isfinite(table.loc[eligible, ['I1', 'I4', 'I6', 'I7']].to_numpy(dtype=float)).all():
        raise ValueError('Unidade declarada elegível contém indicador ausente; sem imputação')
    inputs = list({p['path']: p for p in [*records, *parents, fingerprint(aggregate)]}.values())
    return entry, table, inputs


def score_protocol(config):
    return {'version': '0.1.0', 'stage': '09',
        'normalizer': 'R(x)=(average_rank(x)-0.5)/n; constant variable receives 0.5',
        'fit_scope': 'same_case_family_scale_paired_canopy_cohort_for_descriptive_comparison',
        'A': '(1-R(I1)+R(I4))/2',
        'B': '(S_A+(R(I2)+R(I3_local/L_observable))/2)/2; only valid longitudinal cohort',
        'vertical_Vplus': '(1-R(I6)+1-R(I7))/2',
        'vertical_Vminus': '(1-R(I6)+R(I7))/2',
        'C': '(1-w)*S_B+w*V; never rename A_plus_3D as C',
        'A_plus_3D': '(1-w)*S_A+w*V',
        'I6_only': 'V=1-R(I6)', 'I6_duplicate_control': 'V=((1-R(I6))+(1-R(I6)))/2; must equal I6_only',
        'vertical_weights': sorted(set(config.sensitivity.vertical_weights)),
        'primary_variant': primary_variant(config), 'primary_top_fraction': config.comparison.primary_top_fraction,
        'height_auxiliary_I5': 'correlation/distribution only, never added alongside I6 in primary score',
        'absence': 'common superior priority class, tied within class; no height/score/normalizer imputation',
        'conditional_and_joint_lists': 'reported separately; different universes must not be silently compared',
        'ties': f'scores rounded to {config.comparison.score_tie_decimals} decimals for numerical ties only; raw indicators untouched; mean ranks; operational ID tie-break',
        'top_k': 'ceil(q*n), fixed cardinality and inclusion of the entire cutoff tie group as separate sensitivity',
        'Jaccard_guard': f'null if k<{config.comparison.minimum_top_k_for_jaccard}, even when inclusive ties enlarge set',
        'Spearman': f'descriptive correlation of average ranks; null for constant variables or n<{config.comparison.minimum_spearman_units}; no p-values',
        'H1_pairs': f'same cohort, abs(I1_i-I1_j)<={config.comparison.similar_cover_tolerance:g}, max(O_i,O_j)/min(O_i,O_j)<={config.comparison.maximum_observed_area_ratio:g}',
        'surrogates': 'not run without sufficient independent exchangeable corridor groups; geometric grid cells are not certified independent blocks',
        'predictive_benchmark': 'requires legitimate independent priority target and spatially separated training/test design; not available in this pilot',
        'no_weight_optimization': True, 'no_superiority_assumption': True,
        'parameters': config.comparison.model_dump(mode='json')}


def json_records(frame):
    return json.loads(frame.to_json(orient='records', double_precision=15))


def comparison_run(config, case, *, use_cache=True):
    if not config.paths.mount_root.is_mount():
        raise ValueError('HD externo não montado')
    if psutil.virtual_memory().available/2**30 < config.resources.max_ram_gib:
        raise ValueError('RAM abaixo do orçamento')
    for path, minimum in [(config.paths.runs_root, config.resources.min_local_free_gib),
                          (config.paths.output_root, config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free/2**30 < minimum:
            raise ValueError('Espaço abaixo da reserva configurada')
    state = read_json(config.paths.state_file)
    source, table, inputs = frozen_indicators(config, state, case)
    package = Path(state['referencia_anotacao']['package'])
    assessment = check_annotations(package)
    if not assessment['ok']:
        raise ValueError('Referência/anotações inconsistentes; corrigir antes da comparação')
    groups_path = package/'grupos_reservados.csv'
    groups = pd.read_csv(groups_path)
    selected = groups.loc[groups.corridor_id == source['corridor_id']]
    if len(selected) != 1 or selected.group_id.isna().any():
        raise ValueError('Grupo espacial reservado ausente ou duplicado')
    group_id = str(selected.group_id.iloc[0])
    inputs += [fingerprint(p) for p in [groups_path, package/'trabalho/anotacoes.gpkg',
              package/'trabalho/tarefas.csv', package/'trabalho/fontes_referencia.json']]
    inputs = list({p['path']: p for p in inputs}.values())
    with exclusive_lock(config.paths.runs_root/'.comparison.lock'):
        environment = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
        code = source_digest()
        snapshot = config.model_dump(mode='json')
        snapshot['execution'] = {'case': case, 'source_indicator_run_id': source['run_id'],
            'corridor_group_id': group_id, 'reference_assessment': assessment,
            'primary_variant': primary_variant(config), 'no_optimization_or_predictive_training': True}
        command = f'compare:{case}'
        key = cache_key(command=command, config=snapshot, inputs=inputs, code=code, environment=environment)
        cache_root = config.paths.runs_root/'cache'
        run = Run(config.paths.runs_root, config.paths.state_file, command, snapshot, inputs, environment, code, stage='09')
        started = time.monotonic()

        def event(name, **details):
            run.event(name, **details)
            print(f'{name}: {details}', file=sys.stderr, flush=True)

        try:
            cached = load_cache(cache_root, key) if use_cache else None
            if cached:
                outputs = [Path(p['path']) for p in cached['outputs']]
                run.finish(outputs, cache_hit=True, source_run_id=cached['source_run_id'])
                result = read_json(outputs[0])
                return {'ok': True, 'case': case, 'run_id': run.run_id, 'cache_hit': True,
                    'manifest': str(run.path/'manifest.json'), 'report': str(outputs[0]), 'products_root': result['products_root']}
            directory = config.paths.output_root/'etapa09'/case/run.run_id
            directory.mkdir(parents=True, exist_ok=False)
            event('comparison_start', case=case, source_rows=len(table), source_run=source['run_id'])
            outputs = analyze_comparisons(table, config, group_id)
            products = []
            for name, frame in outputs.items():
                frame['source_indicator_run_id'] = source['run_id']
                frame['comparison_run_id'] = run.run_id
                parquet, csv = directory/f'{name}.parquet', directory/f'{name}.csv'
                frame.to_parquet(parquet, index=False, compression='zstd')
                plain = pd.DataFrame(frame.drop(columns='geometry')) if isinstance(frame, gpd.GeoDataFrame) else frame
                if isinstance(frame, gpd.GeoDataFrame):
                    plain['geometry_wkt'] = frame.geometry.to_wkt()
                plain.to_csv(csv, index=False)
                products += [parquet, csv]
            protocol = directory/'metodologia_escores.json'
            atomic_write_json(protocol, score_protocol(config))
            products.append(protocol)
            if any(fingerprint(Path(p['path'])) != p for p in inputs):
                raise ValueError('Entrada mudou durante comparação; execução não aprovada')
            concordance = outputs['concordancia_ablacao']
            primary = concordance.loc[(concordance.family == 'grid') & (concordance.scope == 'conditional_canopy')
                & (concordance.variant_id == primary_variant(config))
                & (concordance.top_fraction == config.comparison.primary_top_fraction)] if len(concordance) else pd.DataFrame()
            matched_summaries = []
            for _, group in outputs['universos_comparacao'].iterrows():
                pairs = outputs['pares_cobertura_semelhante']
                matched = pairs.loc[(pairs.family == group.family) & (pairs.scale_m == group.scale_m)]
                ids = set(matched.unit_i) | set(matched.unit_j)
                matched_summaries.append({'family': group.family, 'scale_m': float(group.scale_m),
                    'pairs': len(matched), 'unique_units': len(ids),
                    'median_absolute_P95_difference_m': float(matched.absolute_P95_difference_m.median()) if len(matched) else None,
                    'maximum_absolute_P95_difference_m': float(matched.absolute_P95_difference_m.max()) if len(matched) else None,
                    'median_absolute_IQR_difference_m': float(matched.absolute_IQR_difference_m.median()) if len(matched) else None,
                    'pairs_not_independent': True})
            benchmark_status = ('unavailable_no_independent_priority_target' if assessment['independent_priority_references'] == 0
                                else 'independent_target_requires_audited_design_not_automatically_fitted')
            result = {'ok': True, 'stage': '09', 'case': case, 'run_id': run.run_id,
                'source_indicators': source, 'source_rows': len(table), 'mask_validated': False,
                'cohorts': json_records(outputs['universos_comparacao']),
                'method_availability': json_records(outputs['disponibilidade_metodos']),
                'primary_A_vs_A_plus_3D': json_records(primary), 'H1_matched_pairs': matched_summaries,
                'controls': json_records(outputs['controles']),
                'reference_assessment': assessment, 'predictive_benchmark_status': benchmark_status,
                'predictive_models_trained': False, 'accuracy_gain_claimed': False, 'p_values_computed': False,
                'primary_variant': primary_variant(config), 'primary_top_fraction': config.comparison.primary_top_fraction,
                'score_protocol': score_protocol(config), 'table_rows': {k: len(v) for k, v in outputs.items()},
                'products_root': str(directory), 'products': [str(p) for p in products],
                'elapsed_seconds': time.monotonic()-started,
                'peak_process_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'limitations': [
                    'Descriptive retrospective pilot; no municipal inference, causal claim or ecological superiority of 3D.',
                    'B/C remain unavailable where axis/longitudinal support fails; A_plus_3D is an ablation, not renamed C.',
                    'All scores use the same eligible cohort within case/family/scale; additional A descriptors and no-canopy stratum remain explicit.',
                    'No detected canopy receives a shared tied superior class, with height and score null, not double height penalty.',
                    'Weights, group averages and both IQR orientations fixed before analysis; no maximizing rank disagreement or advantage of C.',
                    'Average ranks handle ties; score rounding addresses numerical precision, not raw measurement resolution.',
                    'Jaccard suppressed for k<5; small lists and cutoff ties remain documented.',
                    'H1 pairs share units and spatial dependence; pair counts are not independent replicates or causal benefit.',
                    'Only one corridor group per case: independent/exchangeable blocks insufficient; no random surrogates or p-values.',
                    'Duplicate-height and zero-weight controls are deterministic checks, not statistical null distributions.',
                    'No independent priority target available in the pilot; no predictive benchmarking or accuracy improvement claimed.',
                    'Frozen crown mask remains unvalidated; human labels, adjudication and external reference remain pending.',
                    'No changes to terrain, masks, spatial units, height thresholds or municipal scope; next-stage sensitivity not started.',
                ]}
            report, text = run.path/'comparacao.json', run.path/'comparacao.md'
            atomic_write_json(report, result)
            lines = [f'# Comparação exploratória — {source["corridor_id"]}', '', f'Execução `{run.run_id}`.', '',
                f'|Escala|n pareado|Spearman A/A+3D|k top {100*config.comparison.primary_top_fraction:g}%|Jaccard exato|', '|---|---:|---:|---:|---:|']
            for row in result['primary_A_vs_A_plus_3D']:
                lines.append(f"|{row['scale_m']:g}|{row['n']}|{row['spearman_rho']}|{row['k']}|{row['jaccard_exact']}|")
            lines += ['', '## Limitações', '']+['- '+s for s in result['limitations']]
            text.write_text('\n'.join(lines)+'\n', encoding='utf-8')
            products = [report, text, *products]
            save_cache(cache_root, key, run.run_id, products)
            run.finish(products)
            event_result = {'ok': True, 'case': case, 'run_id': run.run_id, 'cache_hit': False,
                'manifest': str(run.path/'manifest.json'), 'report': str(report), 'products_root': str(directory)}
            return event_result
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt)); raise
