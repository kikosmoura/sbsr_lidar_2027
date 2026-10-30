"""Auditoria independente de áreas, eixos, seções, correspondências e entradas reais."""
import argparse
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import Polygon

from sbsr_lidar.config import load_config
from sbsr_lidar.domain import build_domain
from sbsr_lidar.environment import source_digest
from sbsr_lidar.schemas import RunManifest
from sbsr_lidar.storage import atomic_write_json, fingerprint, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/terreno_congelado_etapa04.yaml'))
    parser.add_argument('--reports', type=Path, default=Path('relatorios/etapa07'))
    args = parser.parse_args()
    config = load_config(args.config)
    checks, summaries = {}, {}
    for case in ['main', 'adversarial']:
        entry = read_json(args.reports/f'execucao_{case}.json')
        r = read_json(Path(entry['report']))
        manifest = RunManifest.model_validate(read_json(Path(entry['manifest'])))
        d = build_domain(config, case)
        tolerance = config.segmentation.area_tolerance_m2
        gpkg = Path(entry['products_root'])/'unidades_multiescala.gpkg'
        checks[f'{case}:manifest_code_and_inputs'] = (manifest.status == 'completed' and manifest.stage == '07'
            and manifest.code_sha256 == source_digest()
            and all(fingerprint(Path(p.path)) == p.model_dump() for p in manifest.inputs))
        parts = gpd.read_file(gpkg, layer='partes')
        observed = gpd.read_file(r['frozen_mask']['patches'], layer=r['frozen_mask']['observed_layer']).union_all()
        crown = gpd.read_file(r['frozen_mask']['patches'], layer=r['frozen_mask']['measurement_layer']).union_all()
        target_long = parts.loc[parts.axis_accepted.astype(bool)].union_all() if parts.axis_accepted.any() else Polygon()
        axes = gpd.read_file(gpkg, layer='eixos_candidatos')
        checks[f'{case}:axes_inside_domain'] = all(g.difference(d.measurement).length < 1e-6 for g in axes.geometry)
        checks[f'{case}:no_forced_route'] = (all(not review['axis_accepted'] or review['retained_branches'] == 1
            for review in r['summary']['part_reviews']) and
            abs(r['summary']['grid_fallback_area_m2'] + target_long.area-d.measurement.area) < tolerance)
        all_grid, all_long = {}, {}
        partitions_ok, observation_ok, ids_ok, residuals_ok, lengths_ok = True, True, True, True, True
        crossed_tiles = 0
        for scale in r['summary']['scales_m']:
            grid = gpd.read_file(gpkg, layer=f'grade_{scale:g}m')
            regions = gpd.read_file(gpkg, layer=f'influencia_{scale:g}m')
            segments = gpd.read_file(gpkg, layer=f'segmentos_{scale:g}m')
            all_grid[scale], all_long[scale] = grid, regions
            for units, target in [(grid, d.measurement), (regions, target_long)]:
                union = units.union_all() if len(units) else Polygon()
                partitions_ok &= (units.geometry.is_valid.all() and union.symmetric_difference(target).area < tolerance
                                  and abs(units.geometry.area.sum()-union.area) < tolerance)
                ids_ok &= units.unit_id.is_unique
                if len(units):
                    actual = np.array([g.intersection(observed).area for g in units.geometry])
                    observation_ok &= np.allclose(actual, units.area_observed_m2, rtol=0, atol=tolerance)
                    observation_ok &= abs(actual.sum()-target.intersection(observed).area) < tolerance
                    residuals_ok &= np.array_equal(units.area_effective_m2 < config.support.minimum_unit_area_m2,
                                                   units.residual_below_minimum_area.astype(bool))
            if len(segments):
                lengths_ok &= np.allclose(segments.geometry.length, segments.length_m, atol=1e-6, rtol=0)
                lengths_ok &= np.allclose(segments.end_m-segments.start_m, segments.length_m)
                lengths_ok &= np.array_equal(segments.short_remainder.astype(bool), segments.length_m < scale-1e-8)
                for bid, group in segments.groupby('branch_id'):
                    group = group.sort_values('start_m')
                    lengths_ok &= abs(group.start_m.iloc[0]) < 1e-8
                    lengths_ok &= np.allclose(group.end_m.to_numpy()[:-1], group.start_m.to_numpy()[1:])
                    length = axes.loc[axes.branch_id == bid].length_m.iloc[0]
                    lengths_ok &= abs(group.length_m.sum()-length) < 1e-6
            crossed_tiles += int(grid.tiles.fillna('').str.contains(',').sum())
        checks[f'{case}:partitions_conserve_area_no_overlap'] = bool(partitions_ok)
        checks[f'{case}:exact_observed_support'] = bool(observation_ok)
        checks[f'{case}:unique_unit_ids'] = bool(ids_ok)
        checks[f'{case}:residuals_retained_and_flagged'] = bool(residuals_ok)
        checks[f'{case}:true_lengths_continuity_and_short_ends'] = bool(lengths_ok)
        sections = gpd.read_file(gpkg, layer='secoes')
        section_ok = True
        for s in sections.itertuples():
            width = s.geometry.length
            observed_width = s.geometry.intersection(observed).length
            candidate_width = s.geometry.intersection(crown).length
            observable = width > 0 and observed_width/width >= config.support.minimum_observed_fraction
            section_ok &= abs(s.section_width_m-width) < 1e-6 and abs(s.observed_width_m-observed_width) < 1e-6
            section_ok &= abs(s.candidate_width_m-candidate_width) < 1e-6
            section_ok &= bool(s.full_section_observable) == observable
            if not observable:
                section_ok &= s.state == 'unknown_support'
        checks[f'{case}:full_width_support_unknown_not_gap'] = bool(section_ok)
        sequences = gpd.read_file(gpkg, layer='sequencias_ramo')
        sequence_ok = True
        for bid, stations in sections.groupby('branch_id') if len(sections) else []:
            group = sequences.loc[sequences.branch_id == bid].sort_values('start_m')
            sequence_ok &= abs(group.length_m.sum()-stations.interval_length_m.sum()) < 1e-6
            for q in group.itertuples():
                matching = stations.loc[(stations.position_m >= q.start_m) & (stations.position_m < q.end_m)]
                sequence_ok &= matching.state.eq(q.state).all() and len(matching) > 0
                if pd.notna(q.gap_id):
                    sequence_ok &= q.state == 'candidate_gap'
        checks[f'{case}:sequences_on_whole_branch'] = bool(sequence_ok)
        mapping = pd.read_csv(Path(entry['products_root'])/'correspondencia_suporte.csv')
        correspondence_ok = True
        for (family, sa, sb), rows in mapping.groupby(['family', 'scale_from_m', 'scale_to_m']):
            a = all_grid[sa] if family != 'longitudinal' else all_long[sa]
            b = all_grid[sb] if family == 'grid' else all_long[sb]
            left, right = a.set_index('unit_id'), b.set_index('unit_id')
            for row in rows.itertuples():
                intersection = left.loc[row.unit_from].geometry.intersection(right.loc[row.unit_to].geometry)
                correspondence_ok &= abs(intersection.area-row.intersection_area_m2) < tolerance
                correspondence_ok &= abs(intersection.intersection(observed).area-row.observed_intersection_area_m2) < tolerance
            target = d.measurement if family == 'grid' else target_long
            correspondence_ok &= abs(rows.intersection_area_m2.sum()-target.area) < tolerance
            correspondence_ok &= abs(rows.observed_intersection_area_m2.sum()-target.intersection(observed).area) < tolerance
        checks[f'{case}:cross_scale_common_spatial_support'] = bool(correspondence_ok)
        layer_names = set(pyogrio.list_layers(gpkg)[:, 0])
        checks[f'{case}:required_layers_and_tables'] = {'juncoes', 'regioes_juncao', 'secoes',
            'sequencias_ramo', 'influencia_estacoes', 'ligacoes_lacunas', 'vizinhos_segmentos',
            'correspondencia_suporte', 'sobreposicoes_corredores'}.issubset(layer_names)
        cache = read_json(args.reports/f'cache_{case}.json')
        checks[f'{case}:cache_same_products'] = cache['cache_hit'] and cache['report'] == entry['report']
        checks[f'{case}:mask_still_unvalidated'] = r['summary']['mask_validated'] is False
        summaries[case] = {'run_id': entry['run_id'], 'summary': r['summary'],
            'grid_units_crossing_tiles': crossed_tiles, 'intercorridor_overlaps': r['intercorridor_overlaps'],
            'elapsed_seconds': r['elapsed_seconds'], 'peak_process_rss_mib': r['peak_process_rss_mib']}
    logs = [(args.reports/file).read_text() for file in ['testes_cientificos.log', 'downloader_regressao.log']]
    checks['test_logs_success'] = all(re.search(r'\d+ passed', log) and not re.search(r'\b\d+ (?:failed|errors?)\b', log) for log in logs)
    tests = {name: int(re.search(r'(\d+) passed', (args.reports/file).read_text()).group(1))
             for name, file in [('scientific_passed', 'testes_cientificos.log'), ('downloader_passed', 'downloader_regressao.log')]}
    result = {'ok': all(checks.values()), 'checks': {k: bool(v) for k, v in checks.items()},
              'summary': summaries, 'tests': tests}
    atomic_write_json(args.reports/'verificacoes.json', result)
    print(f'{sum(checks.values())}/{len(checks)} verificações dos produtos reais passaram.')
    if not result['ok']:
        print([k for k, v in checks.items() if not v])
        raise SystemExit(1)


if __name__ == '__main__':
    main()
