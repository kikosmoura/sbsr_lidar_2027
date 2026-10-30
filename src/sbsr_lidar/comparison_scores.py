"""Escores exploratórios fixados no protocolo, empates e concordância descritiva."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def rank_normalize(values):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Normalização exige universo não vazio e valores finitos, sem imputação')
    return (rankdata(values, method='average')-.5)/len(values)


def descriptive_spearman(x, y, minimum=3):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    use = np.isfinite(x) & np.isfinite(y)
    x, y = x[use], y[use]
    if len(x) < minimum:
        return None, 'unidades_insuficientes'
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return None, 'variavel_constante'
    value = np.corrcoef(rankdata(x, method='average'), rankdata(y, method='average'))[0, 1]
    return float(np.clip(value, -1, 1)), None


def variant_id(method, features, orientation, weight):
    return f'{method}__{features}__{orientation}__w{weight:g}'


def primary_variant(config):
    return variant_id('A_plus_3D', 'I6_I7', 'Vplus', config.comparison.primary_vertical_weight)


def score_variants(cohort, config, *, longitudinal=False):
    required = ['I1', 'I4', 'I6', 'I7'] + (['I2', 'I3_local_over_observable_length'] if longitudinal else [])
    normal = pd.DataFrame({f'R_{k}': rank_normalize(cohort[k]) for k in required}, index=cohort.index)
    normal['D_cov'] = 1-normal.R_I1
    normal['D_frag'] = normal.R_I4
    normal['S_A'] = (normal.D_cov+normal.D_frag)/2
    bases = {'A': normal.S_A.to_numpy()}
    variants = [{'variant_id': 'A', 'method': 'A', 'baseline_id': None,
                 'features': 'I1_I4', 'orientation': None, 'vertical_weight': 0., 'values': bases['A']}]
    if longitudinal:
        normal['D_gap'] = (normal.R_I2+normal.R_I3_local_over_observable_length)/2
        normal['S_B'] = (normal.S_A+normal.D_gap)/2
        bases['B'] = normal.S_B.to_numpy()
        variants.append({'variant_id': 'B', 'method': 'B', 'baseline_id': 'A',
                         'features': 'I1_I4_I2_I3', 'orientation': None, 'vertical_weight': 0., 'values': bases['B']})
    height = (1-normal.R_I6).to_numpy()
    vertical = [('I6_I7', 'Vplus', (height+1-normal.R_I7.to_numpy())/2),
                ('I6_I7', 'Vminus', (height+normal.R_I7.to_numpy())/2),
                ('I6_only', 'height_only', height),
                ('I6_duplicate', 'duplicate_control', (height+height)/2)]
    for base_name, base in bases.items():
        method = 'C' if base_name == 'B' else 'A_plus_3D'
        for features, orientation, v in vertical:
            for weight in sorted(set(config.sensitivity.vertical_weights+[config.comparison.primary_vertical_weight])):
                variants.append({'variant_id': variant_id(method, features, orientation, weight),
                    'method': method, 'baseline_id': base_name, 'features': features,
                    'orientation': orientation, 'vertical_weight': weight,
                    'values': (1-weight)*base+weight*v})
    return normal, variants


def ranked_variant(cohort, absent, variant, normal, config, scope):
    n, m = len(cohort), len(absent) if scope == 'joint_strata' else 0
    score = np.round(variant['values'], config.comparison.score_tie_decimals)
    rows = []
    ordinal = np.lexsort((cohort.unit_id.to_numpy(), -score))
    positions = np.empty(n, dtype=int)
    positions[ordinal] = np.arange(1, n+1)+m
    means = rankdata(-score, method='average')+m
    for i, unit in enumerate(cohort.itertuples()):
        rows.append({'unit_id': unit.unit_id, 'stratum': 'with_candidate_canopy', 'stratum_order': 1,
            'score': float(variant['values'][i]), 'score_for_ranking': float(score[i]),
            'rank_mean': float(means[i]), 'rank_ordinal': int(positions[i]),
            'I6': float(unit.I6), 'I7': float(unit.I7),
            **{key: float(normal.iloc[i][key]) for key in normal.columns}})
    if m:
        for position, unit in enumerate(absent.sort_values('unit_id').itertuples(), 1):
            rows.append({'unit_id': unit.unit_id, 'stratum': 'no_detected_canopy', 'stratum_order': 0,
                'score': None, 'score_for_ranking': None, 'rank_mean': (m+1)/2, 'rank_ordinal': position,
                'I6': None, 'I7': None})
    result = pd.DataFrame(rows)
    for key in ['variant_id', 'method', 'baseline_id', 'features', 'orientation', 'vertical_weight']:
        result[key] = variant[key]
    result['scope'] = scope
    return result.sort_values('rank_ordinal').reset_index(drop=True)


def top_selection(ranking, fraction):
    n = len(ranking)
    if not n:
        raise ValueError('Lista superior exige universo não vazio')
    k = math.ceil(fraction*n)
    ordered = ranking.sort_values('rank_ordinal')
    cutoff = ordered.iloc[k-1]
    same = ordered.stratum.eq(cutoff.stratum)
    if cutoff.stratum_order == 1:
        same &= ordered.score_for_ranking.eq(cutoff.score_for_ranking)
    tied = ordered.loc[same]
    exact = set(ordered.head(k).unit_id)
    inclusive = exact | set(tied.unit_id)
    return {'n': n, 'k': k, 'exact': exact, 'inclusive': inclusive,
            'tie_at_cut_n': len(tied), 'tie_crosses_cut': not set(tied.unit_id).issubset(exact),
            'cut_rank_mean': float(cutoff.rank_mean)}


def compare_rankings(base, variant, fraction, config):
    a, b = top_selection(base, fraction), top_selection(variant, fraction)
    if set(base.unit_id) != set(variant.unit_id):
        raise ValueError('Rankings comparados precisam do mesmo universo de IDs')
    index = base.set_index('unit_id').index
    x, y = (g.set_index('unit_id').loc[index, 'rank_mean'].to_numpy() for g in [base, variant])
    rho, reason = descriptive_spearman(x, y, config.comparison.minimum_spearman_units)
    ok = a['k'] >= config.comparison.minimum_top_k_for_jaccard
    intersection = len(a['exact'] & b['exact'])
    inclusive_intersection = len(a['inclusive'] & b['inclusive'])
    result = {'n': a['n'], 'top_fraction': fraction, 'k': a['k'],
        'spearman_rho': rho, 'spearman_missing_reason': reason,
        'mean_absolute_rank_shift': float(np.mean(np.abs(y-x))),
        'maximum_absolute_rank_shift': float(np.max(np.abs(y-x))),
        'top_intersection_n': intersection, 'top_union_n': len(a['exact'] | b['exact']),
        'jaccard_exact': intersection/len(a['exact'] | b['exact']) if ok else None,
        'jaccard_including_cut_ties': inclusive_intersection/len(a['inclusive'] | b['inclusive']) if ok else None,
        'jaccard_missing_reason': None if ok else f'k_menor_{config.comparison.minimum_top_k_for_jaccard}_lista_pequena',
        'base_tie_at_cut_n': a['tie_at_cut_n'], 'variant_tie_at_cut_n': b['tie_at_cut_n'],
        'base_tie_crosses_cut': a['tie_crosses_cut'], 'variant_tie_crosses_cut': b['tie_crosses_cut'],
        'base_inclusive_n': len(a['inclusive']), 'variant_inclusive_n': len(b['inclusive']),
        'same_exact_top': a['exact'] == b['exact'], 'same_ranks': bool(np.array_equal(x, y))}
    return result, a, b
