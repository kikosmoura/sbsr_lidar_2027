"""Indicadores físicos com denominadores, estimandos e ausência explícitos."""
from __future__ import annotations

import numpy as np
import pandas as pd


def area_metrics(geometry, observed, patches, support_geometries, config):
    area = geometry.area
    observation = geometry.intersection(observed).area
    intersections = []
    for index in patches.sindex.query(geometry, predicate='intersects'):
        patch = patches.iloc[index]
        overlap = geometry.intersection(patch.geometry).area
        if overlap > 0:
            intersections.append({'patch_id': patch.patch_id, 'intersection_area_m2': overlap,
                'patch_touches_context_limit': bool(patch.touches_context_limit),
                'patch_touches_invalid_support': bool(patch.touches_invalid_support),
                'patch_crosses_measurement_boundary': bool(patch.crosses_measurement_boundary)})
    if len({p['patch_id'] for p in intersections}) != len(intersections):
        raise ValueError('IDs de manchas duplicados na origem')
    canopy = sum(p['intersection_area_m2'] for p in intersections)
    if not 0 <= canopy <= observation+config.segmentation.area_tolerance_m2 <= area+2*config.segmentation.area_tolerance_m2:
        raise ValueError('Áreas de copa/observação excedem suporte da unidade')
    largest = max((p['intersection_area_m2'] for p in intersections), default=0.)
    values = {'area_total_m2': area, 'area_observed_m2': observation, 'area_canopy_m2': canopy,
        'fraction_observed': observation/area, 'fraction_unobserved': max(0., 1-observation/area),
        'I1': canopy/observation if observation > 0 else None,
        'canopy_total_fraction_lower_bound': canopy/area,
        'canopy_total_fraction_upper_bound': min(1., (canopy+area-observation)/area),
        'n_patches': len(intersections), 'I4': len(intersections)*10000/observation if observation > 0 else None,
        'largest_patch_intersection_m2': largest,
        'largest_patch_fraction_of_canopy': largest/canopy if canopy > 0 else None,
        'n_patches_context_censored': sum(p['patch_touches_context_limit'] for p in intersections),
        'n_patches_support_censored': sum(p['patch_touches_invalid_support'] for p in intersections),
        'eligible_A': area >= config.support.minimum_unit_area_m2
                      and observation/area >= config.support.minimum_observed_fraction}
    values.update({key: geometry.intersection(g).area for key, g in support_geometries.items()})
    reasons = []
    if area < config.support.minimum_unit_area_m2:
        reasons.append('area_efetiva_insuficiente')
    if observation == 0:
        reasons.append('sem_suporte_comum')
    elif observation/area < config.support.minimum_observed_fraction:
        reasons.append('fracao_observada_insuficiente')
    values['exclusion_reason_A'] = ';'.join(reasons) if reasons else None
    values['coverage_missing_reason'] = None if observation > 0 else 'sem_suporte_comum'
    if observation == 0:
        values['observation_state'] = ('sem_observacao' if values['area_MDS_observed_m2'] == 0
            else 'observacao_excluida_QC' if values['area_MDS_usable_m2'] == 0 else 'sem_suporte_terreno_ou_H')
        values['detected_canopy_state'] = 'nao_avaliavel_sem_suporte'
    else:
        values['observation_state'] = 'observado_integralmente' if observation/area >= 1-1e-9 else 'observado_parcialmente'
        values['detected_canopy_state'] = 'observado_com_vegetacao' if canopy > 0 else 'observado_sem_vegetacao'
    values['classification_uncertainty_present'] = values['area_classification_uncertain_m2'] > 0
    values['state'] = ('classificacao_incerta' if observation > 0 and values['classification_uncertainty_present']
                       else values['detected_canopy_state'] if observation > 0 else values['observation_state'])
    return values, intersections


def height_metrics(heights, area, config):
    n = len(heights)
    if n and (not np.isfinite(heights).all() or np.min(heights) < config.vegetation.minimum_height_m):
        raise ValueError('Alturas de vegetação incompatíveis com seleção congelada')
    reason = None
    if area['area_observed_m2'] == 0:
        reason = 'sem_suporte_comum'
    elif area['area_canopy_m2'] == 0:
        reason = 'classificacao_incerta_sem_copa_detectada' if area['classification_uncertainty_present'] else 'sem_vegetacao'
    elif area['area_canopy_m2'] < config.support.minimum_canopy_area_m2:
        reason = 'area_copa_insuficiente'
    elif n < config.support.minimum_vegetation_returns:
        reason = 'retornos_vegetais_insuficientes'
    result = {'I5': None, 'I6': None, 'I7': None, 'height_Q25_m': None, 'height_Q75_m': None,
        'height_missing_reason': reason, 'height_support_sufficient': reason is None,
        'eligible_A_plus_3D': bool(area['eligible_A'] and reason is None),
        'height_estimand': config.indicators.height_estimand, 'quantile_method': config.indicators.quantile_method}
    if reason is None:
        q25, q75, q95 = np.quantile(heights, [.25, .75, .95], method=config.indicators.quantile_method)
        result.update(I5=float(np.mean(heights)), I6=float(q95), I7=float(q75-q25),
                      height_Q25_m=float(q25), height_Q75_m=float(q75))
    if area['area_observed_m2'] == 0:
        stratum = 'sem_suporte_comum'
    elif area['area_canopy_m2'] == 0:
        stratum = 'sem_copa_detectada_classificacao_incerta' if area['classification_uncertainty_present'] else 'sem_copa_detectada'
    else:
        stratum = 'com_copa_altura_elegivel' if result['height_support_sufficient'] else 'com_copa_altura_insuficiente'
    result['canopy_height_stratum'] = stratum
    result['exclusion_reason_A_plus_3D'] = ';'.join(x for x in [area['exclusion_reason_A'], reason] if x) or None
    return result


def longitudinal_metrics(unit, stations, sequences, area, config):
    result = {k: None for k in ['length_observable_m', 'length_unknown_m', 'length_candidate_gap_m',
        'fraction_length_observable', 'max_detected_gap_intersection_m',
        'associated_branch_gap_detected_length_m', 'associated_gap_id',
        'associated_gap_start_m', 'associated_gap_end_m',
        'detected_gap_intersection_left_cut', 'detected_gap_intersection_right_cut',
        'associated_branch_gap_left_censored', 'associated_branch_gap_right_censored',
        'associated_gap_domain_truncated',
        'I2', 'I3_local_m', 'I3_local_over_observable_length', 'I3_branch_m', 'I3_local_censored']}
    result.update(eligible_B=False, longitudinal_missing_reason='unidade_em_grade',
                  branch_gap_missing_reason='unidade_em_grade')
    if unit['family'] != 'longitudinal':
        return result
    start, end = unit['start_m'], unit['end_m']
    length = end-start
    sections = stations.loc[stations.branch_id == unit['branch_id']]
    observed = gap_length = 0.
    for section in sections.itertuples():
        overlap = max(0., min(end, section.end_m)-max(start, section.start_m))
        if section.full_section_observable:
            observed += overlap
        if section.state == 'candidate_gap':
            gap_length += overlap
    candidates = []
    for q in sequences.loc[sequences.branch_id == unit['branch_id']].itertuples():
        if pd.isna(q.gap_id):
            continue
        a, b = max(start, q.start_m), min(end, q.end_m)
        if b > a:
            candidates.append((b-a, q.gap_id, q, a, b))
    candidates.sort(key=lambda v: (-v[0], v[1]))
    selected = candidates[0] if candidates else None
    result.update(length_observable_m=observed, length_unknown_m=max(0., length-observed),
        length_candidate_gap_m=gap_length, fraction_length_observable=observed/length,
        max_detected_gap_intersection_m=selected[0] if selected else 0.,
        associated_gap_id=selected[1] if selected else None,
        associated_branch_gap_detected_length_m=selected[2].length_m if selected else None)
    if selected:
        _, _, q, a, b = selected
        result.update(associated_gap_start_m=q.start_m, associated_gap_end_m=q.end_m,
            detected_gap_intersection_left_cut=bool(a > q.start_m+1e-8),
            detected_gap_intersection_right_cut=bool(b < q.end_m-1e-8),
            associated_branch_gap_left_censored=bool(q.left_censored),
            associated_branch_gap_right_censored=bool(q.right_censored),
            associated_gap_domain_truncated=bool(q.domain_truncated))
    axis_ok = bool(unit.get('axis_accepted_geometrically', False))
    reason = ('eixo_nao_aceito' if not axis_ok else 'suporte_areal_insuficiente' if not area['eligible_A']
              else 'suporte_longitudinal_insuficiente' if observed/length < config.support.minimum_observed_fraction else None)
    result.update(eligible_B=reason is None, longitudinal_missing_reason=reason,
                  branch_gap_missing_reason=reason)
    if reason is None:
        result.update(I2=gap_length/observed, I3_local_m=selected[0] if selected else 0.,
                      I3_local_over_observable_length=(selected[0] if selected else 0.)/observed)
        if selected:
            _, _, q, a, b = selected
            branch_censored = bool(q.left_censored or q.right_censored)
            result['I3_local_censored'] = branch_censored or a > q.start_m+1e-8 or b < q.end_m-1e-8
            result['I3_branch_m'] = None if branch_censored else q.length_m
            result['branch_gap_missing_reason'] = 'lacuna_ramo_censurada' if branch_censored else None
        else:
            result.update(I3_local_censored=False, branch_gap_missing_reason='sem_lacuna_associada')
    return result
