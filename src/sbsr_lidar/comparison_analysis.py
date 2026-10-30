"""Universos comuns, distribuições, pareamentos H1 e ablações sem inferência municipal."""
from __future__ import annotations

from itertools import combinations

import geopandas as gpd
import numpy as np
import pandas as pd

from .comparison_scores import (compare_rankings, descriptive_spearman, primary_variant,
                                ranked_variant, score_variants)


def common_membership(table):
    result = table.copy()
    roles, reasons = [], []
    for r in result.itertuples():
        longitudinal = r.family == 'longitudinal'
        base_ok = r.eligible_B if longitudinal else r.eligible_A
        paired = r.eligible_B_plus_3D if longitudinal else r.eligible_A_plus_3D
        if paired:
            role, reason = 'paired_canopy', None
        elif base_ok and r.area_canopy_m2 == 0:
            role, reason = 'common_no_detected_canopy_stratum', 'altura_indefinida_sem_imputacao'
        elif not longitudinal and r.eligible_A:
            role, reason = 'A_only_descriptor', r.exclusion_reason_A_plus_3D
        else:
            role = 'excluded'
            reason = r.longitudinal_missing_reason if longitudinal else r.exclusion_reason_A
        roles.append(role); reasons.append(reason)
    result['comparison_role'] = roles
    result['comparison_exclusion_reason'] = reasons
    return result


def similar_cover_pairs(cohort, config):
    n = len(cohort)
    if n*(n-1)//2 > config.comparison.maximum_pair_candidates:
        raise ValueError('Pareamentos H1 excedem orçamento do piloto')
    rows = []
    units = list(cohort.sort_values('unit_id').itertuples())
    for a, b in combinations(units, 2):
        difference = abs(a.I1-b.I1)
        ratio = max(a.area_observed_m2, b.area_observed_m2)/min(a.area_observed_m2, b.area_observed_m2)
        if (difference > config.comparison.similar_cover_tolerance+config.comparison.pair_boundary_epsilon
                or ratio > config.comparison.maximum_observed_area_ratio+config.comparison.pair_boundary_epsilon):
            continue
        rows.append({'unit_i': a.unit_id, 'unit_j': b.unit_id, 'coverage_i': a.I1, 'coverage_j': b.I1,
            'absolute_coverage_difference': difference, 'observed_area_ratio': ratio,
            'P95_i_m': a.I6, 'P95_j_m': b.I6, 'absolute_P95_difference_m': abs(a.I6-b.I6),
            'IQR_i_m': a.I7, 'IQR_j_m': b.I7, 'absolute_IQR_difference_m': abs(a.I7-b.I7),
            'centroid_distance_m': a.geometry.centroid.distance(b.geometry.centroid),
            'units_touch': a.geometry.touches(b.geometry), 'pairs_are_not_independent_replicates': True})
    return rows


def physical_descriptions(cohort, eligible_A, config):
    statistics, correlations = [], []
    variables = ['I1', 'I4', 'I5', 'I6', 'I7']
    for scope, data in [('paired_canopy', cohort), ('eligible_A_descriptors', eligible_A)]:
        for variable in variables:
            x = pd.to_numeric(data[variable], errors='coerce').dropna().to_numpy(dtype=float)
            statistics.append({'scope': scope, 'variable': variable, 'n_universe': len(data), 'n_finite': len(x),
                'minimum': float(np.min(x)) if len(x) else None,
                'Q25': float(np.quantile(x, .25)) if len(x) else None,
                'median': float(np.median(x)) if len(x) else None,
                'Q75': float(np.quantile(x, .75)) if len(x) else None,
                'maximum': float(np.max(x)) if len(x) else None})
    for a, b in combinations(variables, 2):
        x, y = (pd.to_numeric(cohort[v], errors='coerce').to_numpy(dtype=float) for v in [a, b])
        finite = np.isfinite(x) & np.isfinite(y)
        rho, reason = descriptive_spearman(x, y, config.comparison.minimum_spearman_units)
        correlations.append({'variable_x': a, 'variable_y': b, 'n_pairs': int(finite.sum()),
            'spearman_rho': rho, 'missing_reason': reason,
            'used_in_primary_score': a != 'I5' and b != 'I5',
            'selection_rule': 'I5_auxiliary_I6_I7_fixed_by_protocol_not_selected_from_correlations'})
    return statistics, correlations


def group_metadata(case, family, scale):
    return {'case': case, 'family': family, 'scale_m': float(scale)}


def analyze_comparisons(table, config, corridor_group_id):
    membership = common_membership(table)
    ranks, agreements, top_rows, shifts, normalizers = [], [], [], [], []
    pairs, statistics, correlations, availability, cohorts, controls = [], [], [], [], [], []
    for (case, family, scale), all_units in membership.groupby(['case', 'family', 'nominal_size_m'], sort=True):
        meta = group_metadata(case, family, scale)
        cohort = all_units.loc[all_units.comparison_role == 'paired_canopy'].sort_values('unit_id').reset_index(drop=True)
        absent = all_units.loc[all_units.comparison_role == 'common_no_detected_canopy_stratum'].sort_values('unit_id').reset_index(drop=True)
        if len(cohort) > config.comparison.maximum_units_per_cohort:
            raise ValueError('Universo comparativo excede orçamento de unidades do piloto')
        longitudinal = family == 'longitudinal'
        original_eligible = all_units.eligible_A.astype(bool)
        cohort_record = {**meta, 'total_units': len(all_units), 'eligible_A': int(original_eligible.sum()),
            'paired_canopy': len(cohort), 'common_no_canopy_stratum': len(absent),
            'A_only_descriptors': int(all_units.comparison_role.eq('A_only_descriptor').sum()),
            'excluded_units': int(all_units.comparison_role.eq('excluded').sum()),
            'total_area_m2': float(all_units.area_total_m2.sum()),
            'paired_observed_area_m2': float(cohort.area_observed_m2.sum()),
            'eligible_A_observed_area_m2': float(all_units.loc[original_eligible].area_observed_m2.sum()),
            'no_canopy_observed_area_m2': float(absent.area_observed_m2.sum()),
            'normalizer_scope': 'same_paired_canopy_cohort_for_all_variants; absence_is_separate_common_stratum'}
        cohorts.append(cohort_record)
        for method, n, reason in [
            ('A_descriptors', int(original_eligible.sum()), 'nenhuma_unidade_areal_elegivel'),
            ('A', len(cohort), 'nenhuma_unidade_pareada_com_altura'),
            ('A_plus_3D', len(cohort), 'nenhuma_unidade_pareada_com_altura'),
            ('B', int(all_units.eligible_B.sum()), 'sem_eixo_ou_suporte_longitudinal'),
            ('C', int(all_units.eligible_B_plus_3D.sum()), 'sem_suporte_pareado_B_e_altura')]:
            availability.append({**meta, 'method': method, 'available_units': n,
                'available': n > 0, 'unavailable_reason': None if n else reason,
                'small_cohort': n < config.comparison.minimum_spearman_units})
        stats, corr = physical_descriptions(cohort, all_units.loc[original_eligible], config)
        statistics.extend({**meta, **r} for r in stats)
        correlations.extend({**meta, **r} for r in corr)
        matched = similar_cover_pairs(cohort, config)
        pairs.extend({**meta, **r} for r in matched)
        independent_groups = 1 if len(cohort) else 0
        centroids = cohort.geometry.centroid
        block_m = config.comparison.diagnostic_spatial_block_m
        spatial_cells = set(zip(np.floor(centroids.x/block_m), np.floor(centroids.y/block_m)))
        controls.append({**meta, 'corridor_group_id': corridor_group_id,
            'independent_corridor_groups_in_paired_cohort': independent_groups,
            'diagnostic_spatial_cells': len(spatial_cells), 'diagnostic_block_size_m': block_m,
            'minimum_independent_groups_required': config.comparison.minimum_independent_groups_for_surrogates,
            'surrogate_permutations_performed': False,
            'surrogate_status': 'insufficient_independent_exchangeable_groups' if independent_groups < config.comparison.minimum_independent_groups_for_surrogates else 'exchangeability_not_established',
            'p_values_computed': False, 'predictive_models_trained': False,
            'deterministic_weight_and_duplicate_feature_controls': bool(len(cohort)),
            'note': 'Diagnostic spatial cells are not certified independent or exchangeable replicates.'})
        if not len(cohort):
            continue
        normal, variants = score_variants(cohort, config, longitudinal=longitudinal)
        for variable in ['I1', 'I4', 'I6', 'I7']+(['I2', 'I3_local_over_observable_length'] if longitudinal else []):
            x = cohort[variable].to_numpy(dtype=float)
            normalizers.append({**meta, 'variable': variable, 'n': len(x), 'minimum': float(x.min()),
                'maximum': float(x.max()), 'constant': bool(np.ptp(x) == 0),
                'method': '(average_rank-0.5)/n', 'fit_scope': 'paired_canopy_descriptive_not_predictive_training'})
        for scope in ['conditional_canopy', 'joint_strata']:
            ranked = {v['variant_id']: ranked_variant(cohort, absent, v, normal, config, scope) for v in variants}
            for variant in variants:
                key = variant['variant_id']
                ranking = ranked[key]
                ranks.append(ranking.assign(**meta, normalizer_n=len(cohort)))
                if variant['baseline_id'] is None:
                    continue
                base = ranked[variant['baseline_id']]
                b = base.set_index('unit_id')
                for row in ranking.itertuples():
                    original = b.loc[row.unit_id]
                    shifts.append({**meta, 'scope': scope, 'variant_id': key, 'baseline_id': variant['baseline_id'],
                        'unit_id': row.unit_id, 'stratum': row.stratum,
                        'baseline_rank_mean': original.rank_mean, 'variant_rank_mean': row.rank_mean,
                        'rank_shift': row.rank_mean-original.rank_mean,
                        'absolute_rank_shift': abs(row.rank_mean-original.rank_mean),
                        'operational_ordinal_shift': row.rank_ordinal-original.rank_ordinal})
                for fraction in config.comparison.top_fractions:
                    result, a, c = compare_rankings(base, ranking, fraction, config)
                    agreements.append({**meta, 'scope': scope, 'variant_id': key,
                        'baseline_id': variant['baseline_id'], 'vertical_weight': variant['vertical_weight'],
                        'features': variant['features'], 'orientation': variant['orientation'], **result})
                    for row in ranking.itertuples():
                        in_a, in_c = row.unit_id in a['exact'], row.unit_id in c['exact']
                        top_rows.append({**meta, 'scope': scope, 'variant_id': key,
                            'baseline_id': variant['baseline_id'], 'top_fraction': fraction,
                            'unit_id': row.unit_id, 'stratum': row.stratum,
                            'top_baseline_exact': in_a, 'top_variant_exact': in_c,
                            'top_baseline_including_ties': row.unit_id in a['inclusive'],
                            'top_variant_including_ties': row.unit_id in c['inclusive'],
                            'disagreement': 'kept' if in_a and in_c else 'lost' if in_a else 'gained' if in_c else 'neither',
                            'small_list': a['k'] < config.comparison.minimum_top_k_for_jaccard})
    score_table = pd.concat(ranks, ignore_index=True) if ranks else pd.DataFrame(columns=['unit_id', 'variant_id', 'scope', 'case', 'family', 'scale_m'])
    top_table = pd.DataFrame(top_rows)
    if len(top_table):
        spatial = top_table.loc[top_table.variant_id == primary_variant(config)].merge(
            membership[['unit_id', 'geometry']], on='unit_id', validate='many_to_one')
        spatial = gpd.GeoDataFrame(spatial, geometry='geometry', crs=table.crs)
    else:
        spatial = gpd.GeoDataFrame({'unit_id': []}, geometry=[], crs=table.crs)
    pair_columns = ['case', 'family', 'scale_m', 'unit_i', 'unit_j', 'coverage_i', 'coverage_j',
        'absolute_coverage_difference', 'observed_area_ratio', 'P95_i_m', 'P95_j_m', 'absolute_P95_difference_m',
        'IQR_i_m', 'IQR_j_m', 'absolute_IQR_difference_m', 'centroid_distance_m', 'units_touch', 'pairs_are_not_independent_replicates']
    outputs = {'universo_unidades': membership, 'escores_rankings': score_table,
        'concordancia_ablacao': pd.DataFrame(agreements), 'membros_top': top_table,
        'deslocamentos': pd.DataFrame(shifts), 'normalizadores': pd.DataFrame(normalizers),
        'pares_cobertura_semelhante': pd.DataFrame(pairs, columns=pair_columns),
        'estatisticas_indicadores': pd.DataFrame(statistics), 'correlacoes_indicadores': pd.DataFrame(correlations),
        'disponibilidade_metodos': pd.DataFrame(availability), 'universos_comparacao': pd.DataFrame(cohorts),
        'controles': pd.DataFrame(controls), 'desacordos_espaciais': spatial}
    return outputs
