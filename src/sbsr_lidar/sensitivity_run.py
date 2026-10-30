"""Etapa 10 executável: piloto limitado, cache verificável e validação separada."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import resource
import shutil
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import rasterio
import shapely

from .annotations import check_annotations
from .comparison_run import frozen_indicators
from .doctor import existing_parent
from .domain import build_domain, input_plan
from .environment import environment_snapshot, source_digest
from .indicator_run import indicator_sources
from .runtime import Run, exclusive_lock
from .sensitivity_scenarios import scenarios, maximal_domain, scenario_domain, thinning_uniform, plan
from .sensitivity_data import extract_roi, Intermediates, native_mask, unit_owners
from .sensitivity_analysis import (metrics, paired_comparison, strict_ensemble, recipe_stability,
    cross_scale_transfer, density_diagnostics, rank_table, area_support)
from .comparison_scores import compare_rankings
from .storage import atomic_write_json, fingerprint, read_json, cache_key, load_cache, save_cache


def sensitivity_plan(config, case):
    return dict(ok=True, stage='10', **plan(config, case))


def verify_primary(product, table, canonical, mask):
    for filename, array in [(mask['mask_context'], product['support'].canopy), (mask['observation'], product['support'].observation)]:
        with rasterio.open(filename) as ds:
            if ds.transform != product['support'].transform or not np.array_equal(ds.read(1), array):
                raise ValueError('Replay nativo não reproduz máscara/observação congelada')
    old = canonical.loc[canonical.family.eq('grid')].set_index('unit_id').sort_index()
    new = table.set_index('unit_id').sort_index()
    if not old.index.equals(new.index): raise ValueError('Replay mudou IDs de unidades')
    checks = {}
    for key in ['area_observed_m2', 'area_canopy_m2', 'I1', 'I4', 'I5', 'I6', 'I7', 'n_vegetation_records']:
        a, b = old[key].to_numpy(dtype=float), new[key].to_numpy(dtype=float)
        if not np.allclose(a, b, rtol=0, atol=1e-6, equal_nan=True):
            raise ValueError(f'Replay difere dos indicadores congelados: {key}, maxdelta={np.nanmax(np.abs(a-b))}')
        checks[key] = float(np.nanmax(np.abs(a-b))) if np.isfinite(a-b).any() else None
    for key in ['eligible_A', 'eligible_A_plus_3D']:
        if not np.array_equal(old[key], new[key]): raise ValueError(f'Replay mudou elegibilidade {key}')
    return {'mask_and_observation_bitwise_identical': True, 'same_ids_and_eligibility': True,
        'maximum_absolute_metric_replay_differences': checks}


def aggregation_check(fine, coarse, directory):
    a, b = fine['support'], coarse['support']
    rr, cc = np.indices(a.observation.shape)
    x, y = a.transform.c+(cc.ravel()+.5)*a.transform.a, a.transform.f+(rr.ravel()+.5)*a.transform.e
    r, c, inside = b.indices(x, y); flat = r*b.observation.shape[1]+c
    sums = np.bincount(flat[inside], weights=fine['counts']['all'].ravel()[inside], minlength=b.observation.size).reshape(b.observation.shape)
    any_canopy = np.bincount(flat[inside], weights=(a.canopy.ravel()[inside] == 1), minlength=b.observation.size).reshape(b.observation.shape) > 0
    any_valid = np.bincount(flat[inside], weights=(a.observation.ravel()[inside] == 1), minlength=b.observation.size).reshape(b.observation.shape) > 0
    check = coarse['domain'].measurement
    from rasterio.features import geometry_mask
    measured = geometry_mask([check], b.observation.shape, b.transform, invert=True)
    result = {'fine_m': .5, 'coarse_m': 2., 'native_points_used': True,
        'measurement_coarse_center_cells': int(measured.sum()),
        'sum_fine_record_counts_vs_native_coarse_different_cells': int(np.sum(measured & (sums != coarse['counts']['all']))),
        'any_fine_canopy_vs_native_coarse_different_cells': int(np.sum(measured & (any_canopy != (b.canopy == 1)))),
        'any_fine_valid_vs_native_coarse_different_cells': int(np.sum(measured & (any_valid != (b.observation == 1)))),
        'statistic_rule': 'count=sum; candidate=any only under identical H/threshold; validity reevaluated at native centers; unit P95 from original returns, never mean of cell P95',
        'coarse_P95_is_mean_of_fine_P95': False}
    atomic_write_json(directory/'teste_agregacao.json', result)
    return result


def validation_audit(config, state, case, directory):
    ref = Path(state['mascara_copa_piloto']['reference_package'])
    assessment = check_annotations(ref)
    label = 'principal' if case == 'main' else 'adverso'
    terrain_report = read_json(Path(state['terreno_altura_piloto'][label]['report']))
    objects = []
    for name, status, reason in [
        ('canopy_mask', 'pending_real_labels', 'No invented labels; pending annotation package and independent dated imagery/field checks.'),
        ('terrain', 'internal_MDT_holdout_QC_only', 'Reserved MDT points/blocks from same producer; not absolute independent altimetric validation.'),
        ('gaps', 'pending_real_reference_and_eligible_B', 'Axis/support limitations and censored gaps; same LiDAR is not external ground truth.'),
        ('rankings', 'pending_independent_priority_target', 'No accuracy, utility or improvement relative to unavailable target.')]:
        objects.append({'object': name, 'status': status, 'reason': reason, 'accuracy_claimed': False,
            'independent_corridor_groups_in_case': 1, 'confidence_interval': None,
            'interval_missing_reason': 'one_corridor_per_case; no_pixel_bootstrap_or_pseudo_replication'})
    audit = {'annotation_assessment': assessment, 'objects': objects,
        'terrain_internal_QC_source': state['terreno_altura_piloto'][label]['report'],
        'terrain_internal_QC_top_level_keys': sorted(terrain_report),
        'training_or_supervised_model': False, 'test_annotations_modified': False,
        'p_values_computed': False, 'bootstrap_performed': False, 'volume_proxy': 'not_defined_I9_excluded',
        'uncertainty_types': {
            'reference': 'pending human/external labels; independence unavailable',
            'classification': 'baseline/refined/uncertain-upper hypotheses, not validated classes',
            'interpolation': 'TIN/IDW, support radii and context; no extrapolation',
            'sampling': 'record thinning and first-return estimand; no pulse identifiers reconstructed',
            'parameters': 'resolution, height, component connectivity, unit size, fixed score recipes',
            'domain': 'P buffer changes population and is excluded from physical stability ensemble'}}
    atomic_write_json(directory/'validacao_por_objeto.json', audit)
    pd.DataFrame(objects).to_csv(directory/'validacao_por_objeto.csv', index=False)
    # Threshold diagnóstico sobre as seções congeladas; não cria observação em áreas desconhecidas.
    if case == 'adversarial':
        stations = gpd.read_file(state['segmentacao_piloto'][label]['geopackage'], layer='secoes')
        cover = next((c for c in ['canopy_fraction', 'fraction_canopy', 'canopy_cover_fraction'] if c in stations), None)
        atomic_write_json(directory/'limiares_secoes.json', {'thresholds': config.sensitivity.section_thresholds,
            'columns': list(stations.columns), 'executed': False,
            'reason': 'No eligible B at any scale; altering gap/graph distance would not validate censored gaps.',
            'cover_field_if_available': cover})
    return audit


def sensitivity_run(config, case, *, use_cache=True):
    if config.resources.workers != 1: raise ValueError('Etapa 10 mantém um trabalhador')
    if psutil.virtual_memory().available < config.resources.max_ram_gib*2**30:
        raise ValueError('RAM disponível inferior ao orçamento configurado')
    if shutil.disk_usage(existing_parent(config.paths.output_root)).free < (config.resources.min_output_free_gib+2)*2**30:
        raise ValueError('Espaço insuficiente para reserva e produtos do piloto')
    specs = scenarios(config); base = build_domain(config, case); maximal = maximal_domain(config, case)
    rows = input_plan(config, maximal)
    if any(not r['selected_laz'] for r in rows):
        raise ValueError('Complemento ausente; consultar sensitivity --plan-only antes de adquirir')
    state = read_json(config.paths.state_file)
    if state['etapas']['09']['status'] != 'concluida': raise ValueError('Concluir etapa 09')
    label = 'principal' if case == 'main' else 'adverso'
    _, canonical, inputs = frozen_indicators(config, state, case)
    units_entry, mask, terrain, parent_inputs = indicator_sources(config, state, case)
    # Também autenticar os escores congelados que documentam o protocolo de comparação.
    aggregate9 = config.paths.project_root/'docs/manifesto_etapa09.json'
    inventory = {p['path']: p for p in read_json(aggregate9)['artifacts']}
    compare = state['comparacao_piloto'][label]
    for key in ['manifest', 'report', 'scores_rankings']:
        record = fingerprint(Path(compare[key]))
        if inventory.get(record['path']) != record: raise ValueError('Comparação congelada mudou')
        inputs.append(record)
    inputs += parent_inputs+[fingerprint(aggregate9)]+[fingerprint(Path(r['selected_laz'])) for r in rows]
    inputs.append(fingerprint(Path(state['terreno_altura_piloto'][label]['products_root'])/'vertices_terreno.parquet'))
    refined_record = fingerprint(Path(mask['products_root'])/'copa_refinada_h3_contexto.tif')
    inventory6 = {p['path']: p for p in read_json(config.paths.project_root/'docs/manifesto_etapa06.json')['artifacts']}
    if inventory6.get(refined_record['path']) != refined_record: raise ValueError('Máscara refinada congelada mudou')
    inputs.append(refined_record)
    annotation_root = Path(state['mascara_copa_piloto']['reference_package'])
    inputs += [fingerprint(annotation_root/'trabalho'/name) for name in ['anotacoes.gpkg', 'tarefas.csv', 'fontes_referencia.json']]
    inputs = list({p['path']: p for p in inputs}.values())
    environment = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
    code = source_digest()
    snapshot = config.model_dump(mode='json')
    command = f'sensitivity --case {case}'
    key = cache_key(command=command, config=snapshot, inputs=inputs, code=code, environment=environment)
    with exclusive_lock(config.paths.runs_root/'sensitivity.lock'):
        run = Run(config.paths.runs_root, config.paths.state_file, command, snapshot, inputs, environment, code, stage='10')
        started = time.monotonic()
        def event(name, **kw):
            run.event(name, **kw); print(f'{name}: {kw}', file=sys.stderr, flush=True)
        try:
            cached = load_cache(config.paths.runs_root/'cache', key) if use_cache else None
            if cached:
                products = [Path(p['path']) for p in cached['outputs']]
                run.finish(products, cache_hit=True, source_run_id=cached['source_run_id'])
                report = read_json(products[0])
                return {'ok': True, 'stage': '10', 'case': case, 'run_id': run.run_id, 'cache_hit': True,
                    'manifest': str(run.path/'manifest.json'), 'report': str(products[0]), 'products_root': report['products_root']}
            directory = config.paths.output_root/'etapa10'/case/run.run_id
            directory.mkdir(parents=True, exist_ok=False)
            # Checkpoint bruto imutável por identidade de entradas/código/ambiente; nunca aproveitar arquivo parcial.
            work = config.paths.output_root/'etapa10'/'intermediarios'/case/key
            work.mkdir(parents=True, exist_ok=True)
            completed_roi = work/'ROI_complete.json'
            if completed_roi.is_file():
                record = read_json(completed_roi)
                if any(fingerprint(Path(p['path'])) != p for p in record['outputs']): raise ValueError('Cache ROI alterado')
                raw = pd.read_parquet(work/'registros_ROI.parquet')
                ground = pd.read_parquet(work/'vertices_contexto_maximo.parquet').to_numpy()
                event('ROI_cache_hit', records=len(raw))
            else:
                raw, ground = extract_roi(config, maximal, rows, work, event)
                atomic_write_json(completed_roi, {'outputs': [fingerprint(work/n) for n in
                    ['registros_ROI.parquet', 'vertices_contexto_maximo.parquet', 'QC_ROI.json']]})
            inter = Intermediates(config, base, maximal, raw, ground, state['terreno_altura_piloto'][label], work, event)
            uniforms = {}
            native, products_by_id, costs, areas, transitions = [], {}, [], [], []
            baseline_owners = None; primary_verification = None
            for spec in specs:
                if psutil.Process().memory_info().rss > config.resources.max_ram_gib*2**30:
                    raise ValueError('Memória do processo excedeu o orçamento; reduzir ROI')
                tick = time.monotonic(); event('scenario_start', scenario=spec.scenario_id, axis=spec.axis)
                if spec.fraction < 1:
                    if spec.seed not in uniforms:
                        uniforms[spec.seed] = thinning_uniform(raw.source_tile.to_numpy(), raw.source_point_index.to_numpy(), spec.seed)
                    retained = uniforms[spec.seed] < spec.fraction
                elif spec.sampling_mode == 'first_returns': retained = raw.return_number.to_numpy() == 1
                else: retained = np.ones(len(raw), dtype=bool)
                domain = scenario_domain(base, maximal, spec)
                dest = directory/spec.scenario_id; dest.mkdir()
                product = native_mask(config, domain, spec, inter, retained, mask, dest)
                if baseline_owners is None:
                    baseline_owners = unit_owners(config, base, units_entry, raw, product['support'])
                owners = unit_owners(config, domain, units_entry, raw, products_by_id['primary']['support'], spec.expansion_m) if spec.expansion_m else baseline_owners
                product['owners'] = owners
                table = metrics(config, product, owners, raw)
                table.to_parquet(dest/'indicadores.parquet', index=False)
                if spec.scenario_id == 'primary': primary_verification = verify_primary(product, table, canonical, mask)
                native.append(table)
                products_by_id[spec.scenario_id] = product
                common_with_P = product['observed'].intersection(base.measurement)
                areas.append({'scenario_id': spec.scenario_id, 'axis': spec.axis,
                    'measurement_area_m2': domain.measurement.area, 'observed_area_m2': product['observed'].area,
                    'canopy_area_m2': product['summary']['candidate_area_measurement_exact_m2'],
                    'observed_in_original_P_m2': common_with_P.area,
                    'canopy_in_original_P_m2': product['patches'].geometry.union_all().intersection(base.measurement).area,
                    'context_area_m2': domain.context.area, 'omitted_context_m2': domain.metadata['requested_context_omitted_m2'],
                    'retained_roi_records': int(retained.sum()), 'population_changed': bool(spec.expansion_m)})
                costs.append(dict(asdict(spec), elapsed_seconds=time.monotonic()-tick,
                    raw_ROI_shared=True, height_cache_key=str((inter.model_key(domain, spec), spec.radius_m, spec.method)),
                    native_raster_pixels=product['support'].canopy.size))
                event('scenario_done', scenario=spec.scenario_id, seconds=round(time.monotonic()-tick, 2),
                    eligible_50=int(table.loc[table.scale_m == 50, 'eligible_A_plus_3D'].sum()))
            specmap = {s.scenario_id: s for s in specs}; primary = products_by_id['primary']
            physical = {key: p for key, p in products_by_id.items() if not p['scenario'].expansion_m}
            global_v = primary['observed']
            for p in physical.values(): global_v = area_support(global_v.intersection(p['observed']))
            gpd.GeoDataFrame([{'support': 'all_physical_scenarios', 'area_m2': global_v.area, 'geometry': global_v}], crs=config.grid.epsg).to_parquet(directory/'suporte_global.parquet', index=False)
            pair_summaries, differences, globals_ = [], [], {}
            native_table = gpd.GeoDataFrame(pd.concat(native, ignore_index=True), crs=config.grid.epsg)
            metric_cache = {}
            def common_metrics(product, common):
                sid = product['scenario'].scenario_id
                if product['observed'].equals(common):
                    return native_table.loc[native_table.scenario_id.eq(sid)].copy()
                identity = (sid, shapely.to_wkb(shapely.normalize(common)))
                if identity not in metric_cache:
                    metric_cache[identity] = metrics(config, product, baseline_owners, raw, common)
                return metric_cache[identity]
            for sid, product in physical.items():
                event('common_support_analysis', scenario=sid)
                common = area_support(primary['observed'].intersection(product['observed']))
                bt = common_metrics(primary, common)
                ct = common_metrics(product, common)
                summary, change = paired_comparison(bt, ct, config, product['scenario'], common.area)
                pair_summaries.append(summary); differences.append(change)
                globals_[sid] = common_metrics(product, global_v)
                # Suporte e elegibilidade do cenário nativo; não esconder mudança de estrato.
                b = native_table.loc[native_table.scenario_id.eq('primary')].set_index('unit_id')
                c = native_table.loc[native_table.scenario_id.eq(sid)].set_index('unit_id').loc[b.index]
                for uid in b.index:
                    transitions.append({'scenario_id': sid, 'unit_id': uid, 'scale_m': int(b.loc[uid].scale_m),
                        'primary_eligible': bool(b.loc[uid].eligible_A_plus_3D), 'scenario_eligible': bool(c.loc[uid].eligible_A_plus_3D),
                        'primary_stratum': b.loc[uid].canopy_height_stratum, 'scenario_stratum': c.loc[uid].canopy_height_stratum,
                        'primary_fraction_observed': b.loc[uid].fraction_observed, 'scenario_fraction_observed': c.loc[uid].fraction_observed})
            pairs = pd.concat(pair_summaries, ignore_index=True); changes = pd.concat(differences, ignore_index=True)
            strict, spatial = strict_ensemble(globals_, specmap, config)
            # Ensembles de cada eixo são definidos pelo plano, mesmo se o global ficar vazio.
            # Cada frequência tem V e universo fixos próprios; não misturar denominadores.
            axis_cohorts, axis_maps, axis_supports = [], [], []
            for axis in sorted({p['scenario'].axis for p in physical.values()}-{'primary'}):
                group = {sid: p for sid, p in physical.items() if p['scenario'].axis in {'primary', axis}}
                common = primary['observed']
                for p in group.values(): common = area_support(common.intersection(p['observed']))
                ensemble = 'physical_axis_'+axis
                event('axis_stability', axis=axis, scenarios=len(group))
                tables = {sid: common_metrics(p, common) for sid, p in group.items()}
                co, ma = strict_ensemble(tables, specmap, config, ensemble)
                axis_cohorts.append(co)
                if len(ma): axis_maps.append(ma)
                axis_supports.append({'ensemble': ensemble, 'scenario_ids': ','.join(group), 'area_m2': common.area, 'geometry': common})
            if axis_maps: spatial = gpd.GeoDataFrame(pd.concat([spatial, *axis_maps], ignore_index=True), crs=config.grid.epsg)
            strict = pd.concat([strict, *axis_cohorts], ignore_index=True)
            ablations = []
            for (sid, scale), t in native_table.groupby(['scenario_id', 'scale_m']):
                cohort = t.loc[t.eligible_A_plus_3D]
                if cohort.empty:
                    ablations.append({'scenario_id': sid, 'scale_m': scale, 'n': 0, 'missing_reason': 'empty_eligible_canopy_cohort'}); continue
                agreement, _, _ = compare_rankings(rank_table(cohort, config, 'A'), rank_table(cohort, config),
                    config.comparison.primary_top_fraction, config)
                ablations.append({'scenario_id': sid, 'scale_m': scale, **agreement,
                    'scope': 'within_native_scenario_same_cohort; not_cross_scenario_accuracy'})
            recipes = recipe_stability(canonical, config)
            cross, transferred = cross_scale_transfer(canonical, primary['observed'], config)
            density = density_diagnostics(native_table, changes)
            aggregation = aggregation_check(products_by_id['res_0.5'], products_by_id['res_2'], directory)
            audit = validation_audit(config, state, case, directory)
            frames = {'cenarios_custo': pd.DataFrame(costs), 'dominios_areas': pd.DataFrame(areas),
                'indicadores_nativos': native_table, 'comparacoes_suporte_comum': pairs,
                'mudancas_indicadores': changes, 'transicoes_elegibilidade': pd.DataFrame(transitions),
                'coorte_estrita': strict, 'estabilidade_fisica': spatial, 'estabilidade_receitas': recipes,
                'suportes_por_eixo': gpd.GeoDataFrame(axis_supports, crs=config.grid.epsg),
                'ablacao_por_cenario': pd.DataFrame(ablations),
                'comparacoes_entre_escalas': cross, 'transferencia_espacial': transferred,
                'sensibilidade_densidade': density,
                'indicadores_suporte_global': gpd.GeoDataFrame(pd.concat(globals_.values(), ignore_index=True), crs=config.grid.epsg)}
            for name, frame in frames.items():
                frame.to_parquet(directory/f'{name}.parquet', index=False, compression='zstd')
                plain = pd.DataFrame(frame.drop(columns='geometry')) if 'geometry' in frame else frame
                plain.to_csv(directory/f'{name}.csv', index=False)
            if any(fingerprint(Path(p['path'])) != p for p in inputs): raise ValueError('Entrada mudou durante etapa 10')
            # Arquivos de cache numérico passam a ser autenticados como produtos da execução concluída.
            result = {'ok': True, 'stage': '10', 'case': case, 'corridor_id': base.corridor_id, 'run_id': run.run_id,
                'scenario_count': len(specs), 'physical_scenario_count': len(physical), 'measurement_domain_scenarios': 2,
                'roi_records': len(raw), 'maximum_ground_vertices': len(ground), 'primary_replay': primary_verification,
                'height_replay': inter.canonical_replay, 'global_common_area_m2': global_v.area,
                'primary_observed_area_m2': primary['observed'].area,
                'strict_cohorts': strict.to_dict('records'), 'aggregation_check': aggregation,
                'independent_corridor_groups_per_case': 1, 'p_values_computed': False, 'confidence_intervals_computed': False,
                'validation_status': [{k: v for k, v in o.items()} for o in audit['objects']],
                'B_available': False, 'C_available': False, 'horizontal_gap_distance_executed': False,
                'mask_validated': False, 'accuracy_gain_claimed': False, 'full_pilot_completed': False,
                'products_root': str(directory), 'intermediates_root': str(work),
                'table_rows': {name: len(f) for name, f in frames.items()},
                'elapsed_seconds': time.monotonic()-started,
                'peak_process_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'inference': 'descriptive_retrospective_pilot; no municipal or causal inference; empirical ranges not CI'}
            report = run.path/'sensibilidade.json'; atomic_write_json(report, result)
            products = [report]+sorted(p for p in directory.rglob('*') if p.is_file())+sorted(p for p in work.iterdir() if p.is_file())
            save_cache(config.paths.runs_root/'cache', key, run.run_id, products)
            run.finish(products)
            return {'ok': True, 'stage': '10', 'case': case, 'run_id': run.run_id, 'cache_hit': False,
                'manifest': str(run.path/'manifest.json'), 'report': str(report), 'products_root': str(directory)}
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt)); raise
