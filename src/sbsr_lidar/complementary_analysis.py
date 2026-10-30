"""Extensão exploratória pós-resultados: semelhança 2D e IDs fixos.

Não lê LAZ, não altera os produtos PyCrown e não estima acurácia externa.
"""
from itertools import combinations, product

import numpy as np
import pandas as pd

from .comparison_scores import (rank_normalize, score_variants, ranked_variant,
                                primary_variant, compare_rankings)


def indexed(frame):
    if frame.unit_id.duplicated().any():
        raise ValueError('IDs duplicados na análise complementar')
    return frame.set_index('unit_id', drop=False).sort_index()


def horizontal_candidates(cohort):
    """Gera pares sem selecionar por altura; R(I4) usa só a coorte recebida."""
    data = indexed(cohort).reset_index(drop=True).copy()
    if not len(data) or not data.eligible_A_plus_3D.all():
        raise ValueError('Coorte primária vazia ou inelegível')
    if not np.isfinite(data[['I1', 'I4', 'I6', 'I7', 'area_observed_m2']]).all().all():
        raise ValueError('Indicadores ausentes; imputação não autorizada')
    if (data.area_observed_m2 <= 0).any():
        raise ValueError('Área observada deve ser positiva')
    data['R_I4_primary'] = rank_normalize(data.I4)
    rows = []
    for a, b in combinations(data.itertuples(index=False), 2):
        rows.append({'unit_i': a.unit_id, 'unit_j': b.unit_id,
            'corridor_i': a.corridor_id, 'corridor_j': b.corridor_id,
            'same_corridor': a.corridor_id == b.corridor_id,
            'I1_i': a.I1, 'I1_j': b.I1, 'I4_i': a.I4, 'I4_j': b.I4,
            'absolute_coverage_difference': abs(a.I1-b.I1),
            'absolute_fragmentation_rank_difference': abs(a.R_I4_primary-b.R_I4_primary),
            'absolute_fragmentation_difference_per_ha': abs(a.I4-b.I4),
            'observed_area_ratio': max(a.area_observed_m2, b.area_observed_m2)/min(a.area_observed_m2, b.area_observed_m2),
            'P95_i_m': a.I6, 'P95_j_m': b.I6, 'absolute_P95_difference_m': abs(a.I6-b.I6),
            'IQR_i_m': a.I7, 'IQR_j_m': b.I7, 'absolute_IQR_difference_m': abs(a.I7-b.I7),
            'units_touch': bool(a.geometry.touches(b.geometry)),
            'centroid_distance_m': float(a.geometry.centroid.distance(b.geometry.centroid)),
            'pairs_are_not_independent_replicates': True})
    return pd.DataFrame(rows)


def select_horizontal_pairs(candidates, cover_caliper, fragmentation_caliper,
                            maximum_area_ratio=2., epsilon=1e-12, scope='all'):
    keep = ((candidates.absolute_coverage_difference <= cover_caliper+epsilon)
            & (candidates.observed_area_ratio <= maximum_area_ratio+epsilon))
    if fragmentation_caliper is not None:
        keep &= candidates.absolute_fragmentation_rank_difference <= fragmentation_caliper+epsilon
    if scope == 'within_corridor': keep &= candidates.same_corridor
    elif scope == 'between_corridors': keep &= ~candidates.same_corridor
    elif scope != 'all': raise ValueError('Escopo de pareamento desconhecido')
    return candidates.loc[keep].sort_values(['unit_i', 'unit_j']).reset_index(drop=True)


def disjoint_horizontal_pairs(pairs, cover_caliper, fragmentation_caliper):
    """Guloso determinístico, sem usar I6/I7; não promete matching máximo."""
    x = pairs.copy()
    a = x.absolute_coverage_difference/cover_caliper
    b = x.absolute_fragmentation_rank_difference/fragmentation_caliper
    x['horizontal_distance_max'] = np.maximum(a, b)
    x['horizontal_distance_sum'] = a+b
    used, indices = set(), []
    for r in x.sort_values(['horizontal_distance_max', 'horizontal_distance_sum', 'unit_i', 'unit_j']).itertuples():
        if r.unit_i in used or r.unit_j in used: continue
        used.update([r.unit_i, r.unit_j]); indices.append(r.Index)
    return x.loc[indices].reset_index(drop=True)


def summarize_pairs(pairs, thresholds):
    units = set(pairs.unit_i) | set(pairs.unit_j)
    corridors = set(pairs.corridor_i) | set(pairs.corridor_j)
    result = {'n_pairs': len(pairs), 'n_unique_units': len(units),
              'n_corridors': len(corridors), 'n_touching_pairs': int(pairs.units_touch.sum())}
    for field in ['P95', 'IQR']:
        values = pairs[f'absolute_{field}_difference_m']
        for name, q in [('q25', .25), ('median', .5), ('q75', .75), ('max', 1.)]:
            result[f'{field}_difference_{name}_m'] = float(values.quantile(q)) if len(values) else None
        # Cada unidade recebe peso igual, mesmo quando participa de muitos pares.
        local = pd.concat([pairs[['unit_i', f'absolute_{field}_difference_m']].rename(columns={'unit_i': 'unit_id'}),
                           pairs[['unit_j', f'absolute_{field}_difference_m']].rename(columns={'unit_j': 'unit_id'})])
        result[f'{field}_median_of_unit_medians_m'] = float(local.groupby('unit_id').median().median().iloc[0]) if len(local) else None
        for threshold in thresholds:
            count = int((values >= threshold).sum())
            result[f'{field}_difference_ge_{threshold:g}m_n'] = count
            result[f'{field}_difference_ge_{threshold:g}m_fraction'] = count/len(values) if len(values) else None
    return result


def matching_analysis(cohort, settings):
    candidates = horizontal_candidates(cohort); rows = []
    for cover, frag in product(settings['cover_calipers'], settings['fragmentation_rank_calipers']):
        for scope in ['all', 'within_corridor', 'between_corridors']:
            p = select_horizontal_pairs(candidates, cover, frag, settings['maximum_observed_area_ratio'], settings['boundary_epsilon'], scope)
            rows.append({'cover_caliper': cover, 'fragmentation_rank_caliper': frag, 'scope': scope,
                **summarize_pairs(p, settings['height_difference_thresholds_m'])})
    cover = settings['primary_cover_caliper']; frag = settings['primary_fragmentation_rank_caliper']
    primary = select_horizontal_pairs(candidates, cover, frag, settings['maximum_observed_area_ratio'], settings['boundary_epsilon'], settings['primary_scope'])
    disjoint = disjoint_horizontal_pairs(primary, cover, frag)
    old = select_horizontal_pairs(candidates, cover, None, settings['maximum_observed_area_ratio'], settings['boundary_epsilon'])
    summaries = {}
    for name, frame in [('coverage_only_all', old), ('horizontal_within_corridor', primary), ('disjoint_within_corridor', disjoint)]:
        summaries[name] = summarize_pairs(frame, settings['height_difference_thresholds_m'])
    per_corridor = []
    for cid in sorted(cohort.corridor_id.unique()):
        for method, frame in [('all_horizontal_pairs', primary), ('disjoint_pairs', disjoint)]:
            local = frame.loc[frame.corridor_i.eq(cid)]
            per_corridor.append({'corridor_id': cid, 'method': method,
                'primary_units': int(cohort.corridor_id.eq(cid).sum()), **summarize_pairs(local, settings['height_difference_thresholds_m'])})
    return {'candidates': candidates, 'primary': primary, 'disjoint': disjoint,
            'sensitivity': pd.DataFrame(rows), 'per_corridor': pd.DataFrame(per_corridor), 'summary': summaries, 'old_pairs': old}


def strict_fixed_ids(primary_ids, scenario_pairs):
    """Uma única interseção, sem relaxar cenários ou trocar unidades excluídas."""
    fixed = set(primary_ids)
    if len(fixed) != len(primary_ids): raise ValueError('IDs primários repetidos')
    if not scenario_pairs: raise ValueError('Conjunto de cenários vazio')
    for a, b in scenario_pairs.values():
        a, b = indexed(a), indexed(b)
        if not set(primary_ids).issubset(a.index) or not set(primary_ids).issubset(b.index):
            raise ValueError('Unidade original ausente da tabela; registrar ausência antes de analisar')
        fixed &= set(a.loc[a.eligible_A_plus_3D, 'unit_id']) & set(b.loc[b.eligible_A_plus_3D, 'unit_id'])
    return sorted(fixed)


def ranking(frame, ids, config, method='A_plus_3D'):
    data = indexed(frame).loc[sorted(ids)].reset_index(drop=True)
    if not len(data) or not data.eligible_A_plus_3D.all(): raise ValueError('Ranking exige coorte elegível não vazia')
    norm, variants = score_variants(data, config)
    key = 'A' if method == 'A' else primary_variant(config)
    variant = next(v for v in variants if v['variant_id'] == key)
    return ranked_variant(data, data.iloc[:0], variant, norm, config, 'conditional_canopy')


def stability_analysis(primary, scenario_pairs, config):
    ids = sorted(primary.unit_id); fixed = strict_fixed_ids(ids, scenario_pairs)
    comparisons, ranks, eligibility, area_rows = [], [], [], []
    p = indexed(primary)
    for scenario, (left, right) in scenario_pairs.items():
        a, b = indexed(left).loc[ids], indexed(right).loc[ids]
        if not np.allclose(a.area_observed_m2, b.area_observed_m2, rtol=0, atol=1e-7):
            raise ValueError('Os dois lados não têm áreas observadas comuns')
        if not all(x.equals(y) for x, y in zip(a.geometry, b.geometry)):
            raise ValueError('Geometria de unidade mudou entre lados do par')
        surviving = sorted(set(a.loc[a.eligible_A_plus_3D, 'unit_id']) & set(b.loc[b.eligible_A_plus_3D, 'unit_id']))
        for uid in ids:
            la, rb = a.loc[uid], b.loc[uid]
            row = {'scenario_id': scenario, 'unit_id': uid, 'corridor_id': p.loc[uid, 'corridor_id'],
                   'in_fixed_cohort': uid in fixed, 'paired_eligible': uid in surviving}
            for side, r in [('primary_on_pair_support', la), ('scenario_on_pair_support', rb)]:
                for field in ['eligible_A_plus_3D', 'eligible_A', 'fraction_observed', 'area_observed_m2', 'area_canopy_m2',
                              'n_vegetation_records', 'height_missing_reason', 'exclusion_reason_A_plus_3D']:
                    row[f'{side}__{field}'] = r[field]
                row[f'{side}__observation_below_minimum'] = bool(r.fraction_observed < config.support.minimum_observed_fraction)
            eligibility.append(row)
        # Comparação publicada, para validar numericamente antes da extensão.
        if surviving:
            result, _, _ = compare_rankings(ranking(left, surviving, config), ranking(right, surviving, config), config.comparison.primary_top_fraction, config)
            comparisons.append({'scenario_id': scenario, 'cohort': 'variable_pairwise', 'method': 'A_plus_3D',
                'contrast': 'method_on_pair_support', **result})
        if not fixed: continue
        for method in ['A', 'A_plus_3D']:
            rr = {key: ranking(frame, fixed, config, method) for key, frame in [('native_primary', primary), ('primary_on_pair_support', left), ('scenario_on_pair_support', right)]}
            for key, rank in rr.items():
                ranks.append(rank.assign(scenario_id=scenario, measurement=key, analysis_method=method))
            for contrast, x, y in [('method_on_pair_support', 'primary_on_pair_support', 'scenario_on_pair_support'),
                                   ('support_only', 'native_primary', 'primary_on_pair_support'),
                                   ('total_vs_native_primary', 'native_primary', 'scenario_on_pair_support')]:
                result, _, _ = compare_rankings(rr[x], rr[y], config.comparison.primary_top_fraction, config)
                comparisons.append({'scenario_id': scenario, 'cohort': 'strict_fixed', 'method': method,
                    'contrast': contrast, **result})
        for uid in fixed:
            native = float(p.loc[uid, 'area_observed_m2']); common = float(a.loc[uid, 'area_observed_m2'])
            if common > native+1e-7: raise ValueError('Interseção observada aumentou área primária')
            area_rows.append({'scenario_id': scenario, 'unit_id': uid, 'native_observed_area_m2': native,
                'pair_observed_area_m2': common, 'area_retained_fraction': common/native})
    fixed_membership = primary.drop(columns='geometry').copy()
    fixed_membership['in_fixed_cohort'] = fixed_membership.unit_id.isin(fixed)
    ablation = None
    if fixed:
        ablation, _, _ = compare_rankings(ranking(primary, fixed, config, 'A'), ranking(primary, fixed, config), config.comparison.primary_top_fraction, config)
    return {'comparisons': pd.DataFrame(comparisons), 'rankings': pd.concat(ranks, ignore_index=True) if ranks else pd.DataFrame(),
        'eligibility': pd.DataFrame(eligibility), 'fixed_membership': fixed_membership,
        'area': pd.DataFrame(area_rows), 'fixed_ids': fixed,
        'fixed_primary_ablation': ablation, 'fixed_cohort_missing_reason': None if fixed else 'empty_strict_intersection_no_fallback'}
