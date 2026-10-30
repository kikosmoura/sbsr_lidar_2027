"""Métricas no suporte exato, universos fixos e transferência espacial de ranks."""
from __future__ import annotations

import itertools
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.stats import rankdata

from .comparison_scores import (compare_rankings, primary_variant, rank_normalize,
    ranked_variant, score_variants, top_selection, descriptive_spearman)
from .indicator_metrics import area_metrics, height_metrics
from .spatial_units import polygonal


def area_support(geometry):
    """V é areal: contatos isolados por linhas/pontos não criam observação."""
    return geometry if geometry.geom_type in {'Polygon', 'MultiPolygon'} else polygonal(geometry)


def metrics(config, product, owners, raw, common=None):
    observed = product['observed'] if common is None else area_support(product['observed'].intersection(common))
    patches = product['patches']
    crown = area_support(patches.geometry.union_all().intersection(product['domain'].measurement)) if len(patches) else shapely.GeometryCollection()
    x, y = raw.x.to_numpy(), raw.y.to_numpy()
    shapely.prepare(crown)
    support = product['support']; rr, cc = product['rr'], product['cc']
    vegetation = (product['inside'] & product['retained'] & product['candidate']
        & (support.observation[rr, cc] == 1) & (support.canopy[rr, cc] == 1))
    idx = np.flatnonzero(vegetation)
    vegetation[idx] &= shapely.intersects_xy(crown, x[idx], y[idx])
    if common is not None:
        shapely.prepare(observed)
        vegetation[idx] &= shapely.intersects_xy(observed, x[idx], y[idx])
    empty = shapely.GeometryCollection()
    # Demais estados permanecem nos rasters; estas áreas auxiliares não são estimadas a partir de pontos.
    geoms = {key: empty for key in ['area_no_MDS_m2', 'area_no_terrain_or_point_H_m2',
        'area_only_QC_excluded_m2', 'area_outside_observation_context_m2', 'area_classification_uncertain_m2']}
    geoms.update(area_MDS_observed_m2=empty, area_MDS_usable_m2=empty, area_valid_terrain_m2=empty)
    if product['scenario'].mask_version == 'refined':
        geoms['area_classification_uncertain_m2'] = support.geometry(support.canopy == 2, product['domain'].measurement)
    result = []
    for scale, (units, owner) in owners.items():
        use = vegetation & (owner >= 0)
        ids, heights = owner[use], product['h'][use]
        order = np.argsort(ids, kind='stable'); ids, heights = ids[order], heights[order]
        bounds = np.searchsorted(ids, np.arange(len(units)+1))
        total_use = product['inside'] & product['retained'] & (owner >= 0)
        totals = np.bincount(owner[total_use], minlength=len(units))
        for i, unit in enumerate(units.itertuples()):
            # Cortar pela caixa é uma aceleração; a interseção poligonal exata
            # ainda é realizada em area_metrics. Evita reprocessar todo V para
            # cada área auxiliar e cada mancha em uma unidade pequena.
            local_v = observed
            if common is not None:
                x0, y0, x1, y1 = unit.geometry.bounds
                local_v = shapely.clip_by_rect(observed, x0-1e-7, y0-1e-7, x1+1e-7, y1+1e-7)
                if not local_v.is_valid: local_v = shapely.make_valid(local_v)
            local_patches = patches
            if common is not None:
                indices = patches.sindex.query(unit.geometry, predicate='intersects')
                local_patches = patches.iloc[indices].copy()
                local_patches.geometry = local_patches.geometry.intersection(local_v)
                local_patches = local_patches.loc[~local_patches.is_empty & (local_patches.area > 0)]
            area, _ = area_metrics(unit.geometry, local_v, local_patches, geoms, config)
            values = heights[bounds[i]:bounds[i+1]]
            hm = height_metrics(values, area, product['config'])
            result.append({'scenario_id': product['scenario'].scenario_id, 'axis': product['scenario'].axis,
                'unit_id': unit.unit_id, 'case': product['domain'].case, 'corridor_id': unit.corridor_id,
                'scale_m': scale, 'geometry': unit.geometry,
                **{k: area[k] for k in ['area_total_m2', 'area_observed_m2', 'area_canopy_m2', 'fraction_observed',
                    'I1', 'I4', 'n_patches', 'eligible_A', 'exclusion_reason_A', 'classification_uncertainty_present']},
                **hm, 'n_vegetation_records': len(values), 'n_mds_records': int(totals[i]),
                'density_vegetation_records_per_canopy_m2': len(values)/area['area_canopy_m2'] if area['area_canopy_m2'] > 0 else None,
                'auxiliary_support_areas_omitted': True})
    return gpd.GeoDataFrame(result, geometry='geometry', crs=config.grid.epsg)


def rank_table(table, config, method='primary'):
    if table.empty: return pd.DataFrame()
    normal, variants = score_variants(table, config)
    wanted = 'A' if method == 'A' else primary_variant(config)
    variant = next(v for v in variants if v['variant_id'] == wanted)
    return ranked_variant(table, table.iloc[:0], variant, normal, config, 'conditional_canopy')


def paired_comparison(base, candidate, config, scenario, common_area):
    summaries, changes = [], []
    for scale in [25, 50, 100]:
        b = base.loc[(base.scale_m == scale) & base.eligible_A_plus_3D].set_index('unit_id')
        c = candidate.loc[(candidate.scale_m == scale) & candidate.eligible_A_plus_3D].set_index('unit_id')
        ids = sorted(set(b.index) & set(c.index))
        meta = {'scenario_id': scenario.scenario_id, 'axis': scenario.axis, 'scale_m': scale,
            'common_observed_area_m2': common_area, 'n': len(ids), 'support': 'pairwise_intersection_exact_geometry',
            'primary_eligible_in_pair_support': len(b), 'scenario_eligible_in_pair_support': len(c)}
        if not ids:
            summaries.append(dict(meta, missing_reason='no_common_eligible_canopy_units')); continue
        b, c = b.loc[ids].reset_index(), c.loc[ids].reset_index()
        rb, rc = rank_table(b, config), rank_table(c, config)
        agreement, _, _ = compare_rankings(rb, rc, config.comparison.primary_top_fraction, config)
        summaries.append(dict(meta, **agreement, missing_reason=None))
        rb, rc = rb.set_index('unit_id').loc[ids], rc.set_index('unit_id').loc[ids]
        for i, uid in enumerate(ids):
            w = config.comparison.primary_vertical_weight
            terms = {key: coefficient*(rc.iloc[i]['R_'+key]-rb.iloc[i]['R_'+key])
                     for key, coefficient in [('I1', -(1-w)/2), ('I4', (1-w)/2), ('I6', -w/2), ('I7', -w/2)]}
            delta = float(rc.iloc[i].score-rb.iloc[i].score)
            if not np.isclose(sum(terms.values()), delta, atol=1e-12):
                raise ValueError('Decomposição do escore não fecha')
            changes.append({'unit_id': uid, **meta, 'rank_primary': rb.iloc[i].rank_mean,
                'rank_scenario': rc.iloc[i].rank_mean, 'rank_shift': rc.iloc[i].rank_mean-rb.iloc[i].rank_mean,
                'score_difference': delta, **{'score_contribution_'+k: v for k, v in terms.items()},
                **{'delta_'+k: float(c.iloc[i][k]-b.iloc[i][k]) for k in ['I1', 'I4', 'I6', 'I7']},
                'delta_vegetation_density': float(c.iloc[i].density_vegetation_records_per_canopy_m2-b.iloc[i].density_vegetation_records_per_canopy_m2),
                'retained_record_ratio': float(c.iloc[i].n_vegetation_records/b.iloc[i].n_vegetation_records)})
    return pd.DataFrame(summaries), pd.DataFrame(changes)


def stability(rankings, units, config, ensemble):
    """Somente listas do mesmo universo contribuem para uma frequência."""
    if not rankings: return pd.DataFrame()
    universes = [set(r.unit_id) for _, _, r in rankings]
    if any(u != universes[0] for u in universes): raise ValueError('Universos diferentes na frequência')
    records = []
    for scenario_id, axis, ranking in rankings:
        top = top_selection(ranking, config.comparison.primary_top_fraction)
        for row in ranking.itertuples():
            records.append({'unit_id': row.unit_id, 'scenario_id': scenario_id, 'axis': axis,
                'rank_mean': row.rank_mean, 'rank_ordinal': row.rank_ordinal,
                'top_exact': row.unit_id in top['exact'], 'top_inclusive': row.unit_id in top['inclusive'],
                'cutoff_tie': top['tie_crosses_cut']})
    votes = pd.DataFrame(records)
    rows = []
    for uid, v in votes.groupby('unit_id'):
        rows.append({'unit_id': uid, 'ensemble': ensemble, 'n_scenarios': len(v),
            'priority_frequency': float(v.top_exact.mean()), 'priority_frequency_including_cutoff_ties': float(v.top_inclusive.mean()),
            'axis_balanced_priority_frequency': float(v.groupby('axis').top_exact.mean().mean()),
            'rank_min': float(v.rank_mean.min()), 'rank_max': float(v.rank_mean.max()),
            'rank_range': float(v.rank_mean.max()-v.rank_mean.min()), 'rank_ordinal_min': int(v.rank_ordinal.min()),
            'rank_ordinal_max': int(v.rank_ordinal.max()), 'cohort_n': len(universes[0]),
            'uncertainty_interval_type': 'empirical_scenario_range_not_confidence_interval',
            'frequency_is_intervention_probability': False})
    out = units[['unit_id', 'scale_m', 'geometry']].merge(pd.DataFrame(rows), on='unit_id')
    return gpd.GeoDataFrame(out, geometry='geometry', crs=units.crs)


def strict_ensemble(tables, specs, config, ensemble='physical_global_common_support'):
    summaries, maps = [], []
    primary = tables['primary']
    for scale in [25, 50, 100]:
        groups = {key: t.loc[(t.scale_m == scale) & t.eligible_A_plus_3D].set_index('unit_id') for key, t in tables.items()}
        ids = sorted(set.intersection(*(set(g.index) for g in groups.values())))
        summaries.append({'ensemble': ensemble, 'scale_m': scale, 'n_common_eligible_all_scenarios': len(ids), 'n_scenarios': len(groups),
            'missing_reason': None if ids else 'no_common_eligible_units_global_observation_and_all_scenarios'})
        if not ids: continue
        ranks = [(key, specs[key].axis, rank_table(g.loc[ids].reset_index(), config)) for key, g in groups.items()]
        units = primary.loc[(primary.scale_m == scale) & primary.unit_id.isin(ids)]
        maps.append(stability(ranks, units, config, ensemble))
    return pd.DataFrame(summaries), gpd.GeoDataFrame(pd.concat(maps, ignore_index=True), crs=primary.crs) if maps else primary.iloc[:0][['unit_id', 'scale_m', 'geometry']]


def recipe_stability(canonical, config):
    outputs = []
    for scale in [25, 50, 100]:
        t = canonical.loc[(canonical.nominal_size_m == scale) & canonical.family.eq('grid') & canonical.eligible_A_plus_3D].copy()
        if t.empty: continue
        normal, variants = score_variants(t, config)
        ranks = []
        for v in variants:
            if v['features'] == 'I6_duplicate' or (v['method'] != 'A' and v['vertical_weight'] == 0): continue
            ranks.append((v['variant_id'], v['features'], ranked_variant(t, t.iloc[:0], v, normal, config, 'conditional_canopy')))
        t['scale_m'] = scale
        outputs.append(stability(ranks, t, config, 'score_recipes_frozen_physical_support'))
    return gpd.GeoDataFrame(pd.concat(outputs, ignore_index=True), crs=canonical.crs) if outputs else canonical.iloc[:0][['unit_id', 'geometry']]


def weighted_correlation(x, y, weights):
    w = np.asarray(weights, dtype=float)
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if not len(w) or w.sum() <= 0: return None
    x = x-np.average(x, weights=w); y = y-np.average(y, weights=w)
    den = math.sqrt(np.sum(w*x*x)*np.sum(w*y*y))
    return float(np.clip(np.sum(w*x*y)/den, -1, 1)) if den > 1e-14 else None


def cross_scale_transfer(canonical, observed, config):
    """Percentil nativo constante por polígono, transferido à interseção exata W."""
    summaries, cells = [], []
    for method in ['A', 'primary']:
        for sa, sb in itertools.combinations([25, 50, 100], 2):
            tables = [canonical.loc[canonical.family.eq('grid') & (canonical.nominal_size_m == s) & canonical.eligible_A_plus_3D].copy() for s in [sa, sb]]
            if any(t.empty for t in tables):
                summaries.append({'method': method, 'scale_from': sa, 'scale_to': sb, 'missing_reason': 'empty_native_cohort'}); continue
            ranks = [rank_table(t, config, method).set_index('unit_id') for t in tables]
            tops = [top_selection(r.reset_index(), config.comparison.primary_top_fraction) for r in ranks]
            pair = []
            for a in tables[0].itertuples():
                for idx in tables[1].sindex.query(a.geometry, predicate='intersects'):
                    b = tables[1].iloc[idx]
                    g = a.geometry.intersection(b.geometry).intersection(observed)
                    if g.area <= 1e-8: continue
                    pair.append({'method': method, 'scale_from': sa, 'scale_to': sb,
                        'unit_from': a.unit_id, 'unit_to': b.unit_id,
                        'priority_percentile_from': 1-(ranks[0].loc[a.unit_id, 'rank_mean']-.5)/len(ranks[0]),
                        'priority_percentile_to': 1-(ranks[1].loc[b.unit_id, 'rank_mean']-.5)/len(ranks[1]),
                        'top_from': a.unit_id in tops[0]['exact'], 'top_to': b.unit_id in tops[1]['exact'],
                        'top_inclusive_from': a.unit_id in tops[0]['inclusive'], 'top_inclusive_to': b.unit_id in tops[1]['inclusive'],
                        'area_m2': g.area, 'geometry': g})
            if not pair:
                summaries.append({'method': method, 'scale_from': sa, 'scale_to': sb, 'missing_reason': 'no_spatial_intersection'}); continue
            f = pd.DataFrame(pair); valid = all(t['k'] >= config.comparison.minimum_top_k_for_jaccard for t in tops)
            def jaccard(a, b):
                union = f.loc[f[a] | f[b], 'area_m2'].sum()
                return float(f.loc[f[a] & f[b], 'area_m2'].sum()/union) if valid and union else None
            summaries.append({'method': method, 'scale_from': sa, 'scale_to': sb, 'n_from': len(ranks[0]), 'n_to': len(ranks[1]),
                'k_from': tops[0]['k'], 'k_to': tops[1]['k'], 'common_area_m2': f.area_m2.sum(),
                'fraction_of_observed_P': f.area_m2.sum()/observed.area,
                'area_weighted_percentile_correlation': weighted_correlation(f.priority_percentile_from, f.priority_percentile_to, f.area_m2),
                'area_jaccard_top': jaccard('top_from', 'top_to'),
                'area_jaccard_top_inclusive': jaccard('top_inclusive_from', 'top_inclusive_to'),
                'missing_reason': None if valid else 'top_k_below_5_or_no_top_footprint',
                'transfer': 'native_rank_percentile_constant_within_unit_to_exact_overlap; area_weighted; not_independent_samples'})
            cells += pair
    return pd.DataFrame(summaries), gpd.GeoDataFrame(cells, geometry='geometry', crs=canonical.crs) if cells else canonical.iloc[:0][['geometry']]


def density_diagnostics(native, changes):
    rows = []
    for (sid, scale), g in native.groupby(['scenario_id', 'scale_m']):
        if sid != 'primary' and not sid.startswith(('thin_', 'first_')): continue
        eligible = g.loc[g.eligible_A_plus_3D]
        for metric in ['I6', 'I7']:
            rho, reason = descriptive_spearman(eligible.density_vegetation_records_per_canopy_m2, eligible[metric])
            rows.append({'scenario_id': sid, 'scale_m': scale, 'metric': metric, 'n': len(eligible),
                'density_metric_spearman': rho, 'missing_reason': reason,
                'interpretation': 'cross_unit_descriptive_association_not_causal_density_effect'})
    if len(changes):
        for (sid, scale), g in changes.loc[changes.scenario_id.str.startswith(('thin_', 'first_'))].groupby(['scenario_id', 'scale_m']):
            for metric in ['I6', 'I7']:
                rows.append({'scenario_id': sid, 'scale_m': scale, 'metric': metric, 'n': len(g),
                    'median_paired_delta_m': float(g['delta_'+metric].median()),
                    'median_absolute_paired_delta_m': float(g['delta_'+metric].abs().median()),
                    'maximum_absolute_paired_delta_m': float(g['delta_'+metric].abs().max()),
                    'median_retained_vegetation_ratio': float(g.retained_record_ratio.median()),
                    'interpretation': 'paired_common_support; first_returns_changes_estimand; thinning_is_record_not_pulse'})
    return pd.DataFrame(rows)
