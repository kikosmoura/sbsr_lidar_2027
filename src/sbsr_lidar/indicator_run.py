"""Etapa 08: indicadores físicos rastreáveis em unidades e máscara congeladas."""
from __future__ import annotations

import resource
import shutil
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import shapely

from .doctor import existing_parent
from .domain import build_domain
from .environment import environment_snapshot, source_digest
from .indicator_metrics import area_metrics, height_metrics, longitudinal_metrics
from .indicator_support import aggregate_returns, read_support
from .reference import terrain_sources
from .runtime import Run, exclusive_lock
from .segmentation import frozen_mask
from .spatial_units import stable_geometry_id, polygonal
from .storage import atomic_write_json, cache_key, fingerprint, load_cache, read_json, save_cache


def indicator_sources(config, state, case):
    if state.get('etapas', {}).get('07', {}).get('status') != 'concluida':
        raise ValueError('Concluir etapa 07 antes de calcular indicadores')
    label = 'principal' if case == 'main' else 'adverso'
    units = state['segmentacao_piloto'][label]
    mask, inputs = frozen_mask(config, state, case)
    mask_report = read_json(Path(mask['report']))
    mask_config = read_json(Path(mask['manifest']))['config']
    if (mask_report['case'] != case or mask_report['run_id'] != mask['run_id']
            or mask_report['analysis_version'] != mask['analysis_version']
            or mask_report['selection']['version'] != f'baseline_h{config.vegetation.minimum_height_m:g}'
            or mask_report['grid']['resolution_m'] != config.grid.resolution_m
            or mask_config['vegetation']['classes'] != config.vegetation.classes
            or mask_config['vegetation']['connectivity'] != config.vegetation.connectivity):
        raise ValueError('Parâmetros/caso divergem da máscara congelada')
    aggregate = config.paths.project_root/'docs/manifesto_etapa07.json'
    inventory = {p['path']: p for p in read_json(aggregate)['artifacts']}
    records = [fingerprint(Path(units[k])) for k in ['manifest', 'report', 'geopackage']]
    if any(inventory.get(p['path']) != p for p in records):
        raise ValueError('Unidades congeladas mudaram; rever etapa 07')
    units_report = read_json(Path(units['report']))
    if units_report['case'] != case or units_report['frozen_mask']['run_id'] != mask['run_id']:
        raise ValueError('Unidades e máscara pertencem a casos/execuções diferentes')
    terrain = terrain_sources(config, state)[case]
    paths = [Path(terrain['entry'][k]) for k in ['manifest', 'report']]
    paths += [terrain['products'][k] for k in ['alturas_pontos.parquet', 'primary_validity']]
    expected = {p['path']: p for p in read_json(Path(mask['manifest']))['inputs']}
    heights_records = [fingerprint(p) for p in paths]
    if any(expected.get(p['path']) != p for p in heights_records):
        raise ValueError('H/terreno diferem da origem usada na máscara congelada')
    inputs += [*records, *heights_records, fingerprint(aggregate)]
    return units, mask, terrain, list({p['path']: p for p in inputs}.values())


def support_geometries(support, measurement, observed):
    states = {code: support.geometry(support.observation == code, measurement) for code in [1, 2, 3, 4]}
    if states[1].symmetric_difference(observed).area > .0001:
        raise ValueError('Domínio vetorial observado não corresponde ao raster congelado')
    covered = polygonal(shapely.union_all(list(states.values())))
    return {
        'area_MDS_observed_m2': polygonal(shapely.union_all([states[1], states[3], states[4]])),
        'area_MDS_usable_m2': polygonal(shapely.union_all([states[1], states[3]])),
        'area_no_MDS_m2': states[2], 'area_no_terrain_or_point_H_m2': states[3],
        'area_only_QC_excluded_m2': states[4],
        'area_outside_observation_context_m2': polygonal(measurement.difference(covered)),
        'area_valid_terrain_m2': support.geometry(support.terrain_valid, measurement),
        'area_classification_uncertain_m2': support.geometry(
            (support.uncertainty != 65535) & ((support.uncertainty & 31) != 0), measurement)}


def compute_indicators(config, domain, groups, support, observed, crown, patches,
                       height_path, stations, sequences, provenance, event=lambda *a, **k: None):
    if sum(map(len, groups.values())) > config.indicators.maximum_units:
        raise ValueError('Quantidade de unidades excede orçamento do piloto')
    geoms = support_geometries(support, domain.measurement, observed)
    pools, point_report = aggregate_returns(config, height_path, groups, support, domain.measurement, crown, event)
    rows, patch_rows = [], []
    for name, pool in pools.items():
        units = pool['assigner'].units
        for i, unit in enumerate(units.to_dict('records')):
            geometry = unit['geometry']
            area, intersections = area_metrics(geometry, observed, patches, geoms, config)
            counts = {k: int(v[i]) for k, v in pool['counts'].items()}
            heights = pool['heights'][i]
            assert counts['n_vegetation_records'] == len(heights)
            height = height_metrics(heights, area, config)
            longitudinal = longitudinal_metrics(unit, stations, sequences, area, config)
            row = {k: unit.get(k) for k in ['unit_id', 'corridor_id', 'part_id', 'branch_id',
                'family', 'nominal_size_m', 'tiles', 'start_m', 'end_m', 'length_m', 'short_remainder']}
            row.update({**provenance, 'case': domain.case,
                'measurement_id': unit['unit_id']+'__'+provenance['scenario'],
                'units_source_layer': f"grade_{unit['nominal_size_m']:g}m" if unit['family'] == 'grid' else f"influencia_{unit['nominal_size_m']:g}m",
                'geometry_sha256_prefix': stable_geometry_id(geometry),
                **area, **counts, **height, **longitudinal,
                'density_MDS_records_per_total_m2': counts['n_mds_records']/area['area_total_m2'],
                'density_valid_H_records_per_observed_m2': counts['n_records_common_valid_H']/area['area_observed_m2'] if area['area_observed_m2'] > 0 else None,
                'density_vegetation_records_per_canopy_m2': counts['n_vegetation_records']/area['area_canopy_m2'] if area['area_canopy_m2'] > 0 else None,
                'eligible_B_plus_3D': bool(longitudinal['eligible_B'] and height['height_support_sufficient']),
                'geometry': geometry})
            rows.append(row)
            for item in intersections:
                patch_rows.append({'measurement_id': row['measurement_id'], 'unit_id': unit['unit_id'],
                    'family': unit['family'], 'nominal_size_m': unit['nominal_size_m'],
                    'scenario': provenance['scenario'], **item})
    table = gpd.GeoDataFrame(rows, geometry='geometry', crs=config.grid.epsg)
    patches_table = pd.DataFrame(patch_rows, columns=['measurement_id', 'unit_id', 'family', 'nominal_size_m',
        'scenario', 'patch_id', 'intersection_area_m2', 'patch_touches_context_limit',
        'patch_touches_invalid_support', 'patch_crosses_measurement_boundary'])
    qc = []
    for (family, scale), units in table.groupby(['family', 'nominal_size_m']):
        origin = groups[f'{family}_{scale:g}']
        target = origin.union_all()
        canopy_area = target.intersection(crown).area
        observation = target.intersection(observed).area
        ok = (abs(units.area_total_m2.sum()-target.area) <= config.segmentation.area_tolerance_m2
              and abs(units.area_observed_m2.sum()-observation) <= config.segmentation.area_tolerance_m2
              and abs(units.area_canopy_m2.sum()-canopy_area) <= config.segmentation.area_tolerance_m2)
        if not ok:
            raise ValueError('Indicadores violam conservação de área/copa/suporte')
        if family == 'grid' and units.n_mds_records.sum() != point_report['records_in_exact_measurement']:
            raise ValueError('Contagem de retornos não é conservada na grade')
        qc.append({'family': family, 'scale_m': float(scale), 'rows': len(units),
            'area_total_m2': float(units.area_total_m2.sum()), 'area_observed_m2': float(units.area_observed_m2.sum()),
            'area_canopy_m2': float(units.area_canopy_m2.sum()),
            'n_mds_records': int(units.n_mds_records.sum()), 'n_vegetation_records': int(units.n_vegetation_records.sum()),
            'n_patches_unique': int(patches_table.loc[(patches_table.family == family) & (patches_table.nominal_size_m == scale)].patch_id.nunique()),
            'eligible_A': int(units.eligible_A.sum()), 'eligible_A_plus_3D': int(units.eligible_A_plus_3D.sum()),
            'eligible_B': int(units.eligible_B.sum()), 'height_values_available': int(units.I6.notna().sum()),
            'without_detected_canopy': int(units.detected_canopy_state.eq('observado_sem_vegetacao').sum()),
            'without_common_support': int(units.area_observed_m2.eq(0).sum()), 'area_invariants_ok': bool(ok)})
    return table, patches_table, {'groups': qc, 'point_aggregation': point_report,
        'height_missing_reasons': {str(k): int(v) for k, v in table.height_missing_reason.fillna('disponivel').value_counts().items()},
        'longitudinal_missing_reasons': {str(k): int(v) for k, v in table.longitudinal_missing_reason.fillna('disponivel').value_counts().items()}}


def data_dictionary(table, config):
    core = {
        'I1': ('fração', 'T/O; null se O=0', 'área horizontal da copa candidata / área observada comum'),
        'I4': ('manchas/ha observado', 'N*10000/O; N=IDs distintos com interseção de área>0; null se O=0', 'componentes de copa conectividade congelada, não árvores individuais'),
        'I5': ('m', 'mean(H)', 'retornos MDS classes 3/4/5, H válido>=limiar, dentro da copa e V'),
        'I6': ('m', 'quantile(H,0.95,method=linear)', 'mesmos retornos de I5; não P95 de células ou árvores'),
        'I7': ('m', 'quantile(H,0.75)-quantile(H,0.25)', 'IQR da distribuição dos mesmos retornos; não volume/biomassa'),
        'I2': ('fração de comprimento', 'L_lacuna_observada/L_observável', 'estações/seções de largura completa; somente unidade longitudinal elegível'),
        'I3_local_m': ('m', 'max comprimento de interseção de lacuna do ramo com intervalo da unidade', 'censura por corte/suporte mantida; não área sem copa'),
        'I3_local_over_observable_length': ('fração', 'I3_local_m/L_observável', 'mesmo domínio longitudinal elegível'),
        'I3_branch_m': ('m', 'comprimento completo da lacuna associada à maior interseção local, se não censurada', 'null com censura externa, sem lacuna associada ou sem elegibilidade'),
    }
    columns = {}
    for key in table.columns:
        unit = ('m²' if key.startswith('area_') or key.endswith('_m2') else
                'm' if key.endswith('_m') else 'contagem de registros/células' if key.startswith('n_') else
                'booleano' if pd.api.types.is_bool_dtype(table[key]) else 'fração' if 'fraction' in key else 'atributo')
        columns[key] = {'storage_dtype': str(table[key].dtype), 'unit': unit,
            'meaning': key, 'null': 'ausência explícita; consultar campos *_missing_reason/exclusion_reason_*'}
        if key in core:
            unit, formula, estimand = core[key]
            columns[key].update(unit=unit, formula=formula, estimand=estimand,
                support=('T>=minimum_canopy_area_m2 e n>=minimum_vegetation_returns; A+3D exige também elegibilidade A' if key in ['I5', 'I6', 'I7'] else
                            'eixo aceito, A>=25m², O/A>=0.95 e >=95% do comprimento com seções observáveis' if key.startswith(('I2', 'I3')) else
                            'valor físico se O>0; elegibilidade A requer A>=25m² e O/A>=0.95'))
        elif key.startswith('n_'):
            columns[key]['meaning'] = ('Contagem por centro de célula; distinta de área vetorial exata.' if 'cells' in key else
                'Registros MDS com posse única entre unidades na família/escala; não pulsos/árvores independentes.' if 'records' in key else
                'Número de IDs de manchas; componente conectado pode conter várias árvores.')
        elif key.startswith('area_'):
            columns[key]['formula'] = 'area(U ∩ geometria de suporte/copa indicada); área vetorial exata, EPSG:31983'
    columns['area_total_m2']['formula'] = 'area(U)'
    columns['area_observed_m2']['formula'] = 'area(U ∩ V), V congelado da etapa 06'
    columns['area_canopy_m2']['formula'] = 'sum area(U ∩ mancha_contextual); T sem atribuir copa externa inteira'
    columns['canopy_total_fraction_lower_bound']['formula'] = 'T/A'
    columns['canopy_total_fraction_upper_bound']['formula'] = '(T+A-O)/A'
    columns['eligible_A']['formula'] = 'A>=minimum_unit_area_m2 and O/A>=minimum_observed_fraction'
    columns['eligible_A_plus_3D']['formula'] = 'eligible_A and height_support_sufficient'
    columns['geometry']['meaning'] = 'GeoParquet WKB com metadados EPSG:31983; no CSV corresponde a geometry_wkt.'
    details = {
        'area_MDS_observed_m2': 'Área de pixels com qualquer registro MDS: estados 1/3/4; inclui registros excluídos por QC.',
        'area_MDS_usable_m2': 'Área de pixels com registros MDS após QC: estados 1/3.',
        'area_no_MDS_m2': 'Estado 2: sem observação MDS; não é ausência de copa.',
        'area_no_terrain_or_point_H_m2': 'Estado 3: MDS utilizável, sem terreno/H comum válido.',
        'area_only_QC_excluded_m2': 'Estado 4: somente registros MDS excluídos por QC.',
        'area_outside_observation_context_m2': 'Parte de U sem estado 1/2/3/4 no raster; conservada no total A.',
        'area_valid_terrain_m2': 'Pixels com status de terreno 0; não implica observação de copa.',
        'area_classification_uncertain_m2': 'União dos pixels com bits semânticos 1/2/4/8/16 da etapa 06; permanece em O.',
        'n_mds_records': 'Todos os registros MDS da etapa 04 com XY em U, inclusive sem H; posse única por família/escala.',
        'n_records_QC_usable': 'Registros sem bit 2 de exclusão de QC.',
        'n_records_valid_H': 'QC utilizável, terrain_status=0 e H finito, de qualquer classe.',
        'n_records_common_valid_H': 'Registros válidos de qualquer classe cujo pixel pertence ao V congelado.',
        'n_candidate_class_valid_H': 'Registros classes 3/4/5 com H válido>=limiar, antes da seleção por máscara/V.',
        'n_vegetation_records': 'Registros candidatos com pixel de copa/V e XY na copa de medição; mesmos retornos de I5/I6/I7.',
        'n_height_extreme_warning': 'Registros com bit 16 de alerta de H extremo; alerta não é remoção automática.',
        'n_vegetation_height_extreme_warning': 'Registros selecionados para altura que conservam alerta de H extremo.',
        'n_patches': 'IDs distintos de manchas do contexto que têm área positiva em U; não soma de fragmentos de um mesmo ID.',
        'largest_patch_intersection_m2': 'Maior área de interseção U∩mancha; zero se nenhuma área de copa detectada.',
        'largest_patch_fraction_of_canopy': 'Maior interseção de mancha/T; null se T=0.',
        'length_candidate_gap_m': 'Diagnóstico: comprimento observado em lacuna candidata dentro do intervalo; não substitui I2.',
        'max_detected_gap_intersection_m': 'Diagnóstico de maior trecho de lacuna no intervalo, inclusive com suporte insuficiente.',
        'associated_branch_gap_detected_length_m': 'Comprimento detectado da sequência original; pode ser censurado e não é automaticamente I3_branch_m.',
        'associated_gap_start_m': 'Início da lacuna original na referência linear do ramo, preservado mesmo se I2/I3 inelegíveis.',
        'associated_gap_end_m': 'Fim da lacuna original na referência linear do ramo; sem extrapolação sobre suporte desconhecido.',
        'detected_gap_intersection_left_cut': 'Corte local da lacuna no início da unidade; diagnóstico preservado mesmo em unidade inelegível.',
        'detected_gap_intersection_right_cut': 'Corte local da lacuna no fim da unidade; diagnóstico preservado mesmo em unidade inelegível.',
        'associated_branch_gap_left_censored': 'Lacuna original censurada à esquerda por suporte/limite; não é comprimento completo conhecido.',
        'associated_branch_gap_right_censored': 'Lacuna original censurada à direita por suporte/limite.',
        'associated_gap_domain_truncated': 'O ramo pertence a domínio recortado; comprimento integral do corredor não foi observado.',
        'height_missing_reason': 'Motivo de I5/I6/I7 ausentes; sem_vegetacao é ausência detectada na regra, não validação humana.',
        'longitudinal_missing_reason': 'Motivo de I2/I3 ausentes; grade não recebe projeção longitudinal artificial.',
        'B_unavailable_case_reason': 'Limitação do caso registrada na etapa 07, preservada para auditoria.',
        'geometry_sha256_prefix': 'Prefixo SHA256 de 12 dígitos hexadecimais da geometria normalizada, junto ao ID e origem da unidade.',
        'mask_validated': 'False: disponibilidade numérica não comprova validade semântica da máscara.',
        'canopy_height_stratum': 'Separa sem suporte, sem copa detectada, copa com altura suficiente e copa com altura insuficiente.',
    }
    for key, meaning in details.items():
        if key in columns:
            columns[key]['meaning'] = meaning
    for key, formula in {
        'density_MDS_records_per_total_m2': 'n_mds_records/A',
        'density_valid_H_records_per_observed_m2': 'n_records_common_valid_H/O; null se O=0',
        'density_vegetation_records_per_canopy_m2': 'n_vegetation_records/T; null se T=0',
    }.items():
        columns[key].update(unit='registros/m²', formula=formula,
            estimand='densidade de registros da aquisição, não observações independentes ou árvores por área')
    return {'schema_version': '0.1.0', 'stage': '08', 'columns': columns,
        'CSV_extra_columns': {'geometry_wkt': 'Mesma geometria da unidade em WKT, EPSG:31983.'},
        'parameters': {'indicators': config.indicators.model_dump(mode='json'), 'support': config.support.model_dump(mode='json')},
        'rules': ['I1/I4 disponíveis numericamente não significam unidade elegível ou máscara validada.',
            'Limites de cobertura tratam somente suporte não observado; não são intervalos de confiança nem corrigem erros de classificação.',
            'Incerteza semântica é quantificada e permanece no denominador O.',
            'I5/I6/I7 não misturam retornos com superfície superior por célula; sem ponderação por área de copa.',
            'Contagens são registros; repetições internas ao MDS preservadas. Pesos de aquisição/oclusão afetam distribuição.',
            'I2/I3 ausentes na grade ou suporte insuficiente; comprimentos diagnósticos não são indicadores longitudinais elegíveis.',
            'Ausência detectada de copa é estrato próprio; H/P95/IQR ausentes, nunca preenchidos com zero.',
            'I8/I9/I10 fora do núcleo; sem proxy de biomassa, volume real ou conectividade funcional.']}


def indicators_run(config, case, *, use_cache=True):
    if not config.paths.mount_root.is_mount():
        raise ValueError('HD externo não montado')
    if psutil.virtual_memory().available/2**30 < config.resources.max_ram_gib:
        raise ValueError('RAM abaixo do orçamento')
    for path, minimum in [(config.paths.runs_root, config.resources.min_local_free_gib),
                          (config.paths.output_root, config.resources.min_output_free_gib)]:
        if shutil.disk_usage(existing_parent(path)).free/2**30 < minimum:
            raise ValueError('Espaço abaixo da reserva configurada')
    state = read_json(config.paths.state_file)
    units, mask, terrain, inputs = indicator_sources(config, state, case)
    domain = build_domain(config, case)
    with exclusive_lock(config.paths.runs_root/'.indicators.lock'):
        environment = environment_snapshot(config.tools.pdal, config.tools.gdalinfo, config.tools.timeout_seconds)
        code = source_digest()
        snapshot = config.model_dump(mode='json')
        snapshot['execution'] = {'case': case, 'mask_run_id': mask['run_id'], 'units_run_id': units['run_id'],
                                 'scenario': mask['analysis_version'], 'selected_comparison_family': 'grid'}
        command = f'indicators:{case}'
        key = cache_key(command=command, config=snapshot, inputs=inputs, code=code, environment=environment)
        cache_root = config.paths.runs_root/'cache'
        run = Run(config.paths.runs_root, config.paths.state_file, command, snapshot, inputs, environment, code, stage='08')
        started = time.monotonic()

        def event(name, **details):
            run.event(name, **details)
            print(f'{name}: {details}', file=sys.stderr, flush=True)

        try:
            cached = load_cache(cache_root, key) if use_cache else None
            if cached:
                outputs = [Path(p['path']) for p in cached['outputs']]
                run.finish(outputs, cache_hit=True, source_run_id=cached['source_run_id'])
                report = read_json(outputs[0])
                return {'ok': True, 'case': case, 'run_id': run.run_id, 'cache_hit': True,
                    'manifest': str(run.path/'manifest.json'), 'report': str(outputs[0]), 'products_root': report['products_root']}
            directory = config.paths.output_root/'etapa08'/case/run.run_id
            directory.mkdir(parents=True, exist_ok=False)
            groups = {}
            for scale, spec in units['scales'].items():
                for family, column in [('grid', 'grid_layer'), ('longitudinal', 'influence_layer')]:
                    g = gpd.read_file(units['geopackage'], layer=spec[column])
                    if len(g):
                        groups[f'{family}_{float(scale):g}'] = g
            measured = gpd.read_file(units['geopackage'], layer='partes').union_all()
            if measured.symmetric_difference(domain.measurement).area > config.segmentation.area_tolerance_m2:
                raise ValueError('Unidades congeladas não pertencem ao domínio atual')
            support = read_support(mask, terrain['products']['primary_validity'])
            observed = polygonal(gpd.read_file(mask['patches'], layer=mask['observed_layer']).union_all())
            crown = polygonal(gpd.read_file(mask['patches'], layer=mask['measurement_layer']).union_all())
            patches = gpd.read_file(mask['patches'], layer=mask['context_layer'])
            stations = gpd.read_file(units['geopackage'], layer='secoes')
            sequences = gpd.read_file(units['geopackage'], layer='sequencias_ramo')
            provenance = {'scenario': mask['analysis_version'], 'mask_version': mask['analysis_version'],
                'mask_validated': False, 'mask_connectivity': config.vegetation.connectivity,
                'raster_resolution_m': config.grid.resolution_m, 'height_minimum_m': config.vegetation.minimum_height_m,
                'protocol_version': config.protocol_version, 'terrain_run_id': terrain['entry']['run_id'],
                'canopy_run_id': mask['run_id'], 'units_run_id': units['run_id'], 'indicator_run_id': run.run_id,
                'source_units_file': units['geopackage'], 'source_height_file': str(terrain['products']['alturas_pontos.parquet']),
                'B_unavailable_case_reason': units['B_unavailable_reason']}
            event('indicators_start', case=case, families=list(groups), rows=sum(map(len, groups.values())))
            table, intersections, qc = compute_indicators(config, domain, groups, support, observed, crown, patches,
                terrain['products']['alturas_pontos.parquet'], stations, sequences, provenance, event)
            output = directory/'indicadores.parquet'
            table.to_parquet(output, index=False, compression='zstd')
            csv = pd.DataFrame(table.drop(columns='geometry'))
            csv['geometry_wkt'] = table.geometry.to_wkt()
            csv.to_csv(directory/'indicadores.csv', index=False)
            intersections.to_parquet(directory/'intersecoes_manchas.parquet', index=False, compression='zstd')
            intersections.to_csv(directory/'intersecoes_manchas.csv', index=False)
            dictionary = data_dictionary(table, config)
            atomic_write_json(directory/'dicionario_dados.json', dictionary)
            outputs = [output, directory/'indicadores.csv', directory/'intersecoes_manchas.parquet',
                       directory/'intersecoes_manchas.csv', directory/'dicionario_dados.json']
            if any(fingerprint(Path(p['path'])) != p for p in inputs):
                raise ValueError('Entrada mudou durante indicadores; execução não aprovada')
            report = run.path/'indicadores.json'
            markdown = run.path/'indicadores.md'
            result = {'ok': True, 'stage': '08', 'case': case, 'run_id': run.run_id,
                'domain': domain.metadata, 'mask': mask, 'units': units, 'parameters': config.indicators.model_dump(mode='json'),
                'QC': qc, 'rows': len(table), 'columns': len(table.columns), 'products_root': str(directory),
                'products': [str(p) for p in outputs], 'mask_validated': False,
                'B_available': bool(table.eligible_B.any()), 'rankings_computed': False,
                'elapsed_seconds': time.monotonic()-started,
                'peak_process_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'limitations': dictionary['rules']+[
                    'Exploratory pilot only; no municipal estimates, human labels, accuracy metrics or advantage of C claimed.',
                    'Primary height estimand is original normalized vegetation return distribution, not per-tree or canopy-surface height.',
                    'Auxiliary physical values in ineligible units remain reported with support and reasons; not automatically comparable.',
                    'B availability remains subject to axis, areal and longitudinal observation; no substitute from uncovered area.',
                    'No recalculation of frozen terrain, canopy, units or thresholds; I8/I9/I10 excluded from core.']}
            atomic_write_json(report, result)
            lines = [f'# Indicadores físicos — {domain.corridor_id}', '', f'Execução `{run.run_id}`; máscara candidata não validada.', '',
                     '|Família|Escala|Unidades|Elegíveis A|Elegíveis A+3D|Elegíveis B|', '|---|---:|---:|---:|---:|---:|']
            for group in qc['groups']:
                lines.append(f"|{group['family']}|{group['scale_m']:g}|{group['rows']}|{group['eligible_A']}|{group['eligible_A_plus_3D']}|{group['eligible_B']}|")
            lines += ['', '## Limitações', '']+['- '+s for s in result['limitations']]
            markdown.write_text('\n'.join(lines)+'\n', encoding='utf-8')
            outputs = [report, markdown, *outputs]
            save_cache(cache_root, key, run.run_id, outputs)
            run.finish(outputs)
            return {'ok': True, 'case': case, 'run_id': run.run_id, 'cache_hit': False,
                'manifest': str(run.path/'manifest.json'), 'report': str(report), 'products_root': str(directory)}
        except BaseException as error:
            run.fail(error, interrupted=isinstance(error, KeyboardInterrupt))
            raise
