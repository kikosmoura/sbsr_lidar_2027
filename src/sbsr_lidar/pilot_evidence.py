"""Reconstrução de fontes selecionadas, não de narrativas resumidas do piloto."""
from __future__ import annotations

from pathlib import Path
import itertools

import geopandas as gpd
import numpy as np
import pandas as pd

from .schemas import RunManifest
from .storage import fingerprint, read_json


def reconstruct(config, state):
    root = config.paths.project_root
    aggregates = {f'{i:02}': read_json(root/f'docs/manifesto_etapa{i:02}.json') for i in range(1, 11)}
    inputs = {str((root/f'docs/manifesto_etapa{i:02}.json').resolve()): fingerprint(root/f'docs/manifesto_etapa{i:02}.json') for i in range(1, 11)}
    reservation = Path(state['referencia_anotacao']['group_reservation'])
    mutable = {str(Path(p).resolve()) for p in state['referencia_anotacao']['working_files']}
    checks, executions, output_inventory, reports = [], [], {}, {}
    memo = {}
    def actual(path):
        key = str(path.resolve())
        if key not in memo: memo[key] = fingerprint(path)
        return memo[key]
    # O protocolo original continua histórico; decisões/estado/código são arquivos
    # evolutivos e não são submetidos a hashes antigos como se fossem imutáveis.
    for row in aggregates['01']['entradas_locais']:
        path = root/row['arquivo']
        observed = actual(path)
        ok = observed['sha256'] == row['sha256'] and observed['bytes'] == row['bytes']
        checks.append({'stage': '01', 'kind': 'original_input', 'path': str(path), 'ok': ok})
        inputs[observed['path']] = observed
    for stage, aggregate in aggregates.items():
        if int(stage) < 3: continue
        expected = {p['path']: p for p in aggregate.get('artifacts', [])}
        wanted = ['execucao'] if stage == '05' else ['execucao_main', 'execucao_adversarial']
        for label in wanted:
            entry = aggregate['runs'][label]
            path = Path(entry['manifest'])
            manifest = RunManifest.model_validate(read_json(path))
            if manifest.stage != stage or manifest.status != 'completed' or manifest.cache_hit:
                raise ValueError(f'Execução científica selecionada inválida: {path}')
            manifest_record = actual(path)
            if expected.get(manifest_record['path']) != manifest_record:
                raise ValueError(f'Manifesto selecionado mudou: {path}')
            inputs[manifest_record['path']] = manifest_record
            for p in manifest.inputs:
                observed = actual(Path(p.path))
                ok = observed == p.model_dump() if p.path not in mutable else True
                checks.append({'stage': stage, 'kind': 'run_input' if p.path not in mutable else 'mutable_current_reference', 'path': p.path, 'ok': ok})
                inputs[observed['path']] = observed
            total = external = 0
            for filename in manifest.outputs:
                observed = actual(Path(filename)); current = str(Path(filename).resolve())
                ok = expected.get(current) == observed if current not in mutable else True
                checks.append({'stage': stage, 'kind': 'run_output' if current not in mutable else 'mutable_current_reference', 'path': current, 'ok': ok})
                inputs[current] = observed
                output_inventory[current] = observed
                total += observed['bytes']
                if Path(filename).is_relative_to(config.paths.output_root): external += observed['bytes']
            report = read_json(Path(entry['report']))
            case = 'joint_reference' if stage == '05' else label.removeprefix('execucao_')
            reports[(stage, case)] = report
            executions.append({'stage': stage, 'case': case, 'run_id': manifest.run_id,
                'command': manifest.command, 'report': entry['report'], 'manifest': str(path),
                'historical_code_sha256': manifest.code_sha256,
                'elapsed_seconds': report['elapsed_seconds'],
                'peak_rss_mib': report.get('peak_process_rss_mib', report.get('process_peak_rss_mib')),
                'output_bytes': total, 'external_output_bytes': external,
                'config_resolution_m': manifest.config['grid']['resolution_m'],
                'config_halo_m': manifest.config['pilot']['halo_m'],
                'config_height_m': manifest.config['vegetation']['minimum_height_m'],
                'config_primary_unit_m': manifest.config['segmentation']['length_m'],
                'workers': manifest.config['resources']['workers'], 'time_scope': 'reported_scientific_execution_excludes_hash_preflight_download_and_human_work'})
    for p in [reservation, *map(Path, mutable), root/'configs/terreno_congelado_etapa04.yaml']:
        inputs[str(p.resolve())] = actual(p)
    if not all(row['ok'] for row in checks):
        failed = [row['path'] for row in checks if not row['ok']]
        raise ValueError(f'Fonte científica histórica mudou: {failed[:5]}')
    return aggregates, reports, pd.DataFrame(executions), pd.DataFrame(checks), list(inputs.values()), list(output_inventory.values())


def dependence_diagnostics(config, state):
    summaries, bins = [], []
    for label, case in [('principal', 'main'), ('adverso', 'adversarial')]:
        frame = gpd.read_parquet(state['indicadores_piloto'][label]['parquet'])
        t = frame.loc[frame.family.eq('grid') & frame.nominal_size_m.eq(50) & frame.eligible_A_plus_3D].copy()
        xy = np.column_stack([t.geometry.centroid.x, t.geometry.centroid.y])
        for metric in ['I1', 'I4', 'I6', 'I7']:
            values = t[metric].to_numpy(dtype=float)
            summaries.append({'case': case, 'metric': metric, 'eligible_units': len(t),
                'mean': float(values.mean()) if len(values) else None,
                'sample_SD': float(values.std(ddof=1)) if len(values) > 1 else None,
                'Q25': float(np.quantile(values, .25)) if len(values) else None,
                'Q75': float(np.quantile(values, .75)) if len(values) else None,
                'independent_corridor_groups': 1, 'power_computed': False})
            if len(t) < 3: continue
            i, j = np.triu_indices(len(t), 1)
            distances = np.linalg.norm(xy[i]-xy[j], axis=1)
            semivariance = .5*(values[i]-values[j])**2
            variance = np.var(values, ddof=1)
            for lower, upper in zip([0, 100, 200, 400, 800, 1600], [100, 200, 400, 800, 1600, 3200]):
                use = (distances >= lower) & (distances < upper)
                bins.append({'case': case, 'metric': metric, 'distance_lower_m': lower, 'distance_upper_m': upper,
                    'pairs': int(use.sum()), 'unique_units': len(set(i[use]) | set(j[use])),
                    'mean_semivariance': float(semivariance[use].mean()) if use.any() else None,
                    'semivariance_over_sample_variance': float(semivariance[use].mean()/variance) if use.any() and variance > 0 else None,
                    'pairs_independent': False, 'range_estimated': False,
                    'limitation': 'one_corridor_irregular_clipped_grid; no stationarity_or_plateau_certified; no p_value'})
    return pd.DataFrame(summaries), pd.DataFrame(bins)


def cost_projection(executions, reports, design, proposal, tile_links, tile_files):
    """Envelopes de planejamento de dois casos; não são previsão calibrada/IC."""
    calibrations = []
    for case in ['main', 'adversarial']:
        p = reports[('03', case)]
        scanned = sum(row['points_read'] for row in p['clouds'])
        area = p['domain']['context_area_m2']
        baseline = executions.loc[executions.case.eq(case) & executions.stage.isin(['03', '04', '06', '07', '08', '09'])]
        sensitivity = executions.loc[executions.case.eq(case) & executions.stage.eq('10')].iloc[0]
        time0 = float(baseline.elapsed_seconds.sum())
        bytes0 = int(baseline.output_bytes.sum())
        calibrations.append({'case': case, 'full_file_records_scanned': scanned, 'context_area_m2': area,
            'observed_baseline_pipeline_seconds': time0, 'baseline_seconds_per_million_scanned_records': time0*1e6/scanned,
            'baseline_seconds_per_context_m2': time0/area,
            'observed_30_scenario_seconds': float(sensitivity.elapsed_seconds),
            'sensitivity_seconds_per_context_m2': float(sensitivity.elapsed_seconds)/area,
            'selected_baseline_output_bytes': bytes0, 'selected_sensitivity_output_bytes': int(sensitivity.output_bytes),
            'baseline_bytes_per_context_m2': bytes0/area,
            'sensitivity_bytes_per_context_m2': float(sensitivity.output_bytes)/area,
            'measured_peak_rss_mib': float(max(baseline.peak_rss_mib.max(), sensitivity.peak_rss_mib))})
    cal = pd.DataFrame(calibrations)
    projected = []
    selected = proposal.loc[proposal.selected_for_planning.eq(True)]
    for count in [8, 10, 12]:
        # Ordem completa de candidatos/reservas, não somente os dez da proposta principal.
        ordered = proposal.loc[proposal.candidate_order.notna()].sort_values('candidate_order').head(count)
        ids = set(ordered.corridor_id)
        tiles = set(tile_links.loc[tile_links.corridor_id.isin(ids), 'tile'])
        # Links de reservas também são planejados; registros de cabeçalho nunca decodificados.
        files = tile_files.loc[tile_files.tile.isin(tiles)]
        if len(ordered) != count: continue
        complete = len(files) == 2*len(tiles) and files.declared_points.notna().all()
        records = float(files.declared_points.sum()) if complete else None
        visits = tile_links.loc[tile_links.corridor_id.isin(ids)].merge(tile_files, on='tile')
        complete_visits = visits.declared_points.notna().all()
        visits_records = float(visits.declared_points.sum()) if complete_visits else None
        halo = reports[('03', 'main')]['domain']['halo_m']
        ctx = sum(g.buffer(halo).area for g in ordered.geometry)
        # Se cada corredor reler a folha, há visitas repetidas. O limite inferior
        # com leitura única é um cenário de agendamento, não otimização implementada.
        low = records/1e6*cal.baseline_seconds_per_million_scanned_records.min() if records is not None else None
        high = visits_records/1e6*cal.baseline_seconds_per_million_scanned_records.max()*design.cost_uncertainty_factor if visits_records is not None else None
        projected.append({'planned_corridors': count, 'primary_design': count == design.target_corridors,
            'unique_tiles': len(tiles), 'file_visits': len(visits), 'missing_files': int((~files.exists).sum()),
            'sum_context_area_m2': ctx, 'declared_records_unique_files': records, 'declared_record_visits_per_corridor': visits_records,
            'estimated_baseline_seconds_low': low, 'estimated_baseline_seconds_budget': high,
            'estimated_baseline_area_seconds_low': ctx*cal.baseline_seconds_per_context_m2.min(),
            'estimated_baseline_area_seconds_budget': ctx*cal.baseline_seconds_per_context_m2.max()*design.cost_uncertainty_factor,
            'estimated_additional_sensitivity_seconds_low': ctx*cal.sensitivity_seconds_per_context_m2.min(),
            'estimated_additional_sensitivity_seconds_budget': ctx*cal.sensitivity_seconds_per_context_m2.max()*design.cost_uncertainty_factor,
            'estimated_derived_bytes_budget': int(ctx*(cal.baseline_bytes_per_context_m2.max()+cal.sensitivity_bytes_per_context_m2.max())*design.disk_safety_factor),
            'download_seconds': None, 'human_annotation_seconds': None, 'reference_setup_seconds': None,
            'cost_type': 'uncalibrated_planning_envelope_not_CI_or_observed_duration',
            'limitations': '2_cases_only; area_model_assumes_comparable_density_and_IO; record_model_null_if_missing_headers; repeated_full_file_IO; geometric_complexity_and_chunking_unknown; downloads_human_work_excluded'})
    return cal, pd.DataFrame(projected)
