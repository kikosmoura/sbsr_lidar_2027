"""Releitura independente dos indicadores, geometrias e quantis dos pontos fonte."""
import argparse
import math
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio
import shapely
from shapely.geometry import box

from sbsr_lidar.annotations import check_annotations
from sbsr_lidar.config import load_config
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json


def manual_quantile(values, fraction):
    values = sorted(values)
    position = (len(values)-1)*fraction
    a, b = math.floor(position), math.ceil(position)
    return values[a]+(values[b]-values[a])*(position-a)


def audit_source_points(table, report, config):
    units = table.loc[(table.family == 'grid') & (table.nominal_size_m == 50)].sort_values('unit_id').reset_index(drop=True)
    chosen = set(units.sort_values('n_vegetation_records').tail(2).unit_id)
    valid = units.loc[units.I6.notna()]
    chosen.update(valid.sort_values('I7').head(1).unit_id)
    chosen.update(valid.sort_values('I7').tail(1).unit_id)
    chosen.update(units.loc[units.I6.isna()].sort_values('area_total_m2').tail(2).unit_id)
    chosen.update(units.loc[units.area_canopy_m2 == 0].head(1).unit_id)
    lookup = {i: r.unit_id for i, r in enumerate(units.itertuples()) if r.unit_id in chosen}
    total = {u: 0 for u in chosen}
    heights = {u: [] for u in chosen}
    tree = shapely.STRtree(units.geometry.to_numpy())
    mask = report['mask']
    measured = units.union_all()
    crown = gpd.read_file(mask['patches'], layer=mask['measurement_layer']).union_all()
    shapely.prepare(measured); shapely.prepare(crown)
    with rasterio.open(mask['mask_context']) as ds:
        canopy, transform = ds.read(1), ds.transform
    with rasterio.open(mask['observation']) as ds:
        observation = ds.read(1)
    source = Path(units.source_height_file.iloc[0])
    for batch in pq.ParquetFile(source).iter_batches(batch_size=65536,
            columns=['x', 'y', 'h', 'classification', 'terrain_status', 'qc_flags']):
        d = batch.to_pandas()
        d = d.loc[shapely.intersects_xy(measured, d.x.to_numpy(), d.y.to_numpy())]
        if d.empty: continue
        x, y, h = d.x.to_numpy(), d.y.to_numpy(), d.h.to_numpy()
        pairs = tree.query(shapely.points(x, y), predicate='intersects')
        owners = np.full(len(d), len(units), dtype=int)
        np.minimum.at(owners, pairs[0], pairs[1])
        ids, n = np.unique(pairs[0], return_counts=True)
        rr = np.floor((transform.f-y)/(-transform.e)).astype(int)
        cc = np.floor((x-transform.c)/transform.a).astype(int)
        for index in ids[n > 1]:
            candidates = sorted(pairs[1, pairs[0] == index])
            left, top = transform.c+cc[index]*transform.a, transform.f+rr[index]*transform.e
            pixel = box(left, top+transform.e, left+transform.a, top)
            owners[index] = max(candidates, key=lambda c: (units.geometry.iloc[c].intersection(pixel).area, -c))
        inside = (rr >= 0) & (cc >= 0) & (rr < canopy.shape[0]) & (cc < canopy.shape[1])
        rr = np.clip(rr, 0, canopy.shape[0]-1); cc = np.clip(cc, 0, canopy.shape[1]-1)
        selected = (inside & np.isfinite(h) & (d.terrain_status.to_numpy() == 0)
            & ((d.qc_flags.to_numpy() & 2) == 0) & d.classification.isin([3, 4, 5]).to_numpy()
            & (h >= config.vegetation.minimum_height_m) & (canopy[rr, cc] == 1) & (observation[rr, cc] == 1)
            & shapely.intersects_xy(crown, x, y))
        for i, unit_id in lookup.items():
            total[unit_id] += int(np.sum(owners == i))
            heights[unit_id].extend(h[selected & (owners == i)].tolist())
    audits = []
    for unit_id in sorted(chosen):
        row = units.loc[units.unit_id == unit_id].iloc[0]
        values = heights[unit_id]
        ok = total[unit_id] == row.n_mds_records and len(values) == row.n_vegetation_records
        if pd.notna(row.I6):
            ok &= math.isclose(math.fsum(values)/len(values), row.I5, abs_tol=1e-9, rel_tol=0)
            ok &= math.isclose(manual_quantile(values, .95), row.I6, abs_tol=1e-9, rel_tol=0)
            ok &= math.isclose(manual_quantile(values, .75)-manual_quantile(values, .25), row.I7, abs_tol=1e-9, rel_tol=0)
        audits.append({'unit_id': unit_id, 'n_source_records': total[unit_id],
                       'n_source_vegetation_records': len(values), 'quantiles_available': pd.notna(row.I6), 'ok': bool(ok)})
    return audits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/terreno_congelado_etapa04.yaml'))
    parser.add_argument('--reports', type=Path, default=Path('relatorios/etapa08'))
    args = parser.parse_args(); config = load_config(args.config)
    checks, summaries = {}, {}
    for case in ['main', 'adversarial']:
        e = read_json(args.reports/f'execucao_{case}.json'); r = read_json(Path(e['report']))
        manifest = RunManifest.model_validate(read_json(Path(e['manifest'])))
        directory = Path(e['products_root'])
        table = gpd.read_parquet(directory/'indicadores.parquet')
        csv = pd.read_csv(directory/'indicadores.csv')
        dictionary = read_json(directory/'dicionario_dados.json')
        links = pd.read_parquet(directory/'intersecoes_manchas.parquet')
        checks[f'{case}:manifest_inputs_and_code'] = manifest.stage == '08' and manifest.status == 'completed' and manifest.code_sha256 == source_digest() and all(fingerprint(Path(p.path)) == p.model_dump() for p in manifest.inputs)
        checks[f'{case}:unique_rows_and_scenario'] = table.measurement_id.is_unique and table.scenario.nunique() == 1 and table.mask_version.eq('baseline_h3').all() and table.case.eq(case).all()
        checks[f'{case}:dictionary_covers_columns'] = set(dictionary['columns']) == set(table.columns) and all('formula' in dictionary['columns'][k] and 'estimand' in dictionary['columns'][k] and 'support' in dictionary['columns'][k] for k in ['I1', 'I2', 'I3_local_m', 'I4', 'I5', 'I6', 'I7'])
        checks[f'{case}:CSV_GeoParquet_equivalence'] = csv.measurement_id.tolist() == table.measurement_id.tolist() and all(np.allclose(csv[k].to_numpy(dtype=float), table[k].to_numpy(dtype=float), equal_nan=True, atol=1e-9, rtol=0) for k in ['area_canopy_m2', 'I1', 'I4', 'I5', 'I6', 'I7']) and table.crs.to_epsg() == config.grid.epsg
        o, t, a = table.area_observed_m2, table.area_canopy_m2, table.area_total_m2
        positive = o > 0
        checks[f'{case}:coverage_denominator_and_bounds'] = (np.allclose(table.loc[positive, 'I1'], (t/o)[positive], atol=1e-9) and table.loc[~positive, 'I1'].isna().all()
            and np.allclose(table.fraction_unobserved, 1-o/a) and np.allclose(table.canopy_total_fraction_lower_bound, t/a)
            and np.allclose(table.canopy_total_fraction_upper_bound, (t+a-o)/a) and (t <= o+1e-6).all() and (o <= a+1e-6).all())
        sum_states = o+table.area_no_MDS_m2+table.area_no_terrain_or_point_H_m2+table.area_only_QC_excluded_m2+table.area_outside_observation_context_m2
        checks[f'{case}:observation_states_conserve_area'] = np.allclose(sum_states, a, rtol=0, atol=.0001) and np.allclose(table.area_MDS_usable_m2, o+table.area_no_terrain_or_point_H_m2, rtol=0, atol=.0001) and (table.area_valid_terrain_m2 >= o-.0001).all()
        checks[f'{case}:height_minimum_support_and_nulls'] = np.array_equal(table.height_support_sufficient, (o > 0) & (t >= config.support.minimum_canopy_area_m2) & (table.n_vegetation_records >= config.support.minimum_vegetation_returns)) and table.loc[~table.height_support_sufficient, ['I5', 'I6', 'I7']].isna().all().all() and (table.loc[table.height_support_sufficient, 'I6'] >= config.vegetation.minimum_height_m).all()
        checks[f'{case}:quantile_order_and_IQR'] = (table.loc[table.height_support_sufficient, 'I6'] >= table.loc[table.height_support_sufficient, 'height_Q75_m']).all() and np.allclose(table.loc[table.height_support_sufficient, 'I7'], (table.height_Q75_m-table.height_Q25_m)[table.height_support_sufficient])
        checks[f'{case}:common_eligibility'] = np.array_equal(table.eligible_A, (a >= config.support.minimum_unit_area_m2) & (o/a >= config.support.minimum_observed_fraction)) and np.array_equal(table.eligible_A_plus_3D, table.eligible_A & table.height_support_sufficient)
        empty_canopy = positive & (t == 0)
        checks[f'{case}:no_canopy_is_not_zero_height'] = table.loc[empty_canopy, ['I5', 'I6', 'I7']].isna().all().all() and table.loc[empty_canopy, 'I1'].eq(0).all() and table.loc[~positive, ['I1', 'I4']].isna().all().all()
        checks[f'{case}:patch_density_not_raw_count'] = np.allclose(table.loc[positive, 'I4'], table.loc[positive, 'n_patches']*10000/o[positive]) and table.loc[~positive, 'I4'].isna().all()
        canopy_positive = t > 0
        checks[f'{case}:record_densities_have_explicit_area'] = (np.allclose(table.density_MDS_records_per_total_m2, table.n_mds_records/a)
            and np.allclose(table.loc[positive, 'density_valid_H_records_per_observed_m2'], table.loc[positive, 'n_records_common_valid_H']/o[positive])
            and np.allclose(table.loc[canopy_positive, 'density_vegetation_records_per_canopy_m2'], table.loc[canopy_positive, 'n_vegetation_records']/t[canopy_positive])
            and table.loc[~canopy_positive, 'density_vegetation_records_per_canopy_m2'].isna().all())
        patch_frame = gpd.read_file(r['mask']['patches'], layer=r['mask']['context_layer'])
        patch_ok = True
        for row in table.itertuples():
            actual = {p.patch_id: row.geometry.intersection(p.geometry).area for p in patch_frame.itertuples() if row.geometry.intersects(p.geometry) and row.geometry.intersection(p.geometry).area > 0}
            subset = links.loc[links.measurement_id == row.measurement_id]
            patch_ok &= len(actual) == row.n_patches == len(subset) and subset.patch_id.is_unique
            patch_ok &= math.isclose(sum(actual.values()), row.area_canopy_m2, abs_tol=.0001, rel_tol=0)
            patch_ok &= math.isclose(max(actual.values(), default=0), row.largest_patch_intersection_m2, abs_tol=.0001, rel_tol=0)
        checks[f'{case}:exact_context_patch_intersections'] = bool(patch_ok)
        geometry_ok, conservation_ok = True, True
        observed = gpd.read_file(r['mask']['patches'], layer=r['mask']['observed_layer']).union_all()
        crown = gpd.read_file(r['mask']['patches'], layer=r['mask']['measurement_layer']).union_all()
        for (family, scale), g in table.groupby(['family', 'nominal_size_m']):
            layer = f'grade_{scale:g}m' if family == 'grid' else f'influencia_{scale:g}m'
            original = gpd.read_file(r['units']['geopackage'], layer=layer).set_index('unit_id')
            geometry_ok &= all(row.geometry.equals(original.loc[row.unit_id].geometry) for row in g.itertuples())
            geometry_ok &= np.allclose(g.area_total_m2, g.geometry.area, atol=.0001, rtol=0)
            target = original.union_all()
            conservation_ok &= math.isclose(g.area_observed_m2.sum(), target.intersection(observed).area, abs_tol=.0001, rel_tol=0)
            conservation_ok &= math.isclose(g.area_canopy_m2.sum(), target.intersection(crown).area, abs_tol=.0001, rel_tol=0)
            if family == 'grid':
                conservation_ok &= g.n_mds_records.sum() == r['QC']['point_aggregation']['records_in_exact_measurement']
        checks[f'{case}:geometry_and_unit_ids_preserved'] = bool(geometry_ok)
        checks[f'{case}:area_and_point_conservation'] = bool(conservation_ok)
        checks[f'{case}:no_fabricated_longitudinal_metrics'] = not table.eligible_B.any() and table[['I2', 'I3_local_m', 'I3_branch_m']].isna().all().all() and table.loc[table.family == 'grid', 'length_m'].isna().all()
        diagnostic_ok = True
        native_sections = gpd.read_file(r['units']['geopackage'], layer='secoes')
        native_sequences = gpd.read_file(r['units']['geopackage'], layer='sequencias_ramo')
        for row in table.loc[table.family == 'longitudinal'].itertuples():
            sections = native_sections.loc[native_sections.branch_id == row.branch_id]
            observed_length = sum(max(0., min(row.end_m, s.end_m)-max(row.start_m, s.start_m)) for s in sections.itertuples() if s.full_section_observable)
            diagnostic_ok &= math.isclose(observed_length, row.length_observable_m, abs_tol=1e-8, rel_tol=0)
            if pd.notna(row.associated_gap_id):
                q = native_sequences.loc[native_sequences.gap_id == row.associated_gap_id].iloc[0]
                diagnostic_ok &= bool(row.associated_branch_gap_left_censored) == bool(q.left_censored)
                diagnostic_ok &= bool(row.associated_branch_gap_right_censored) == bool(q.right_censored)
                diagnostic_ok &= row.associated_gap_start_m == q.start_m and row.associated_gap_end_m == q.end_m
                diagnostic_ok &= bool(row.detected_gap_intersection_left_cut) == (row.start_m > q.start_m+1e-8)
                diagnostic_ok &= bool(row.detected_gap_intersection_right_cut) == (row.end_m < q.end_m-1e-8)
        checks[f'{case}:physical_gap_diagnostics_and_censor_preserved'] = bool(diagnostic_ok)
        checks[f'{case}:primary_return_estimand'] = table.height_estimand.eq('normalized_vegetation_returns').all() and table.quantile_method.eq('linear').all()
        audits = audit_source_points(table, r, config)
        checks[f'{case}:original_point_counts_and_exact_quantiles'] = bool(audits) and all(x['ok'] for x in audits)
        cache = read_json(args.reports/f'cache_{case}.json')
        checks[f'{case}:cache_same_products'] = cache['cache_hit'] and cache['report'] == e['report']
        checks[f'{case}:no_validation_or_rankings_invented'] = not table.mask_validated.any() and not r['rankings_computed'] and not any(k in table for k in ['I8', 'I9', 'I10'])
        summaries[case] = {'run_id': r['run_id'], 'rows': r['rows'], 'columns': r['columns'], 'QC': r['QC'],
            'source_point_audits': audits, 'elapsed_seconds': r['elapsed_seconds'], 'peak_process_rss_mib': r['peak_process_rss_mib']}
    logs = [(args.reports/p).read_text() for p in ['testes_cientificos.log', 'downloader_regressao.log']]
    checks['test_logs_success'] = all(re.search(r'\d+ passed', log) and not re.search(r'\b\d+ (?:failed|errors?)\b', log) for log in logs)
    assessment = check_annotations(Path(read_json(config.paths.state_file)['referencia_anotacao']['package']))
    checks['reference_preserved_and_no_human_labels_invented'] = assessment['ok'] and assessment['completed_annotations'] == 0
    tests = {'scientific_passed': int(re.search(r'(\d+) passed', logs[0]).group(1)), 'downloader_passed': int(re.search(r'(\d+) passed', logs[1]).group(1))}
    result = {'ok': all(checks.values()), 'checks': {k: bool(v) for k, v in checks.items()}, 'summary': summaries, 'tests': tests}
    atomic_write_json(args.reports/'verificacoes.json', result)
    print(f'{sum(checks.values())}/{len(checks)} verificações dos produtos reais passaram.')
    if not result['ok']:
        print([k for k, v in checks.items() if not v]); raise SystemExit(1)


if __name__ == '__main__':
    main()
