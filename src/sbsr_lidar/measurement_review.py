"""Descrições de distribuição e QC interno; não estima acurácia externa."""
import numpy as np
import pandas as pd


def pair_distribution(pairs, expected=16):
    if len(pairs) != expected:
        raise ValueError('Seleção de pares mudou')
    ids = list(pairs.unit_i)+list(pairs.unit_j)
    if len(ids) != len(set(ids)):
        raise ValueError('Pares reutilizam IDs')
    if not pairs.corridor_i.eq(pairs.corridor_j).all():
        raise ValueError('Par entre corredores no conjunto principal')
    rows = []
    for descriptor in ['P95', 'IQR']:
        values = pairs[f'absolute_{descriptor}_difference_m'].to_numpy(float)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError('Diferenças ausentes, negativas ou não finitas')
        rows.append({'descriptor': descriptor, 'n_pairs': len(pairs), 'quantile_method': 'linear',
            **{name: float(np.quantile(values, q, method='linear')) for name, q in
               [('minimum_m', 0), ('q25_m', .25), ('median_m', .5), ('q75_m', .75), ('maximum_m', 1)]}})
    return pd.DataFrame(rows)


def terrain_holdouts(document, corridor_id, method='tin', radius=5.):
    if document.get('external_accuracy_validated') is not False:
        raise ValueError('QC deve ser identificado como consistência interna')
    rows, unavailable = [], []
    for window in document['terrain_holdout']:
        for split in ['reserved_points', 'reserved_blocks']:
            selected = [x for x in window.get('metrics', []) if x['method'] == method
                        and abs(x['radius_m']-radius) <= 1e-12 and x['split'] == split]
            if len(selected) > 1: raise ValueError('QC repetido por janela/método/raio/divisão')
            if not selected:
                unavailable.append({'corridor_id': corridor_id, 'wx': window['wx'], 'wy': window['wy'],
                    'split': split, 'reason': window.get('status', 'metric_not_available')})
                continue
            metric = selected[0]
            n, evaluated = int(metric['n']), int(metric['evaluated'])
            if evaluated <= 0 or not 0 <= n <= evaluated or not np.isclose(metric['valid_fraction'], n/evaluated, atol=1e-12, rtol=0):
                raise ValueError('Fração válida incompatível com contagens')
            if n == 0 or metric['rmse_m'] is None:
                unavailable.append({'corridor_id': corridor_id, 'wx': window['wx'], 'wy': window['wy'], 'split': split, 'reason': 'no_valid_residuals'})
            rows.append({'corridor_id': corridor_id, 'wx': window['wx'], 'wy': window['wy'],
                'method': method, 'radius_m': radius, 'split': split, 'n_valid': n, 'n_evaluated': evaluated,
                **{key: metric[key] for key in ['rmse_m', 'mae_m', 'bias_m', 'p95_abs_m', 'valid_fraction']},
                'scope': 'held_out_same_sensor_MDT_interpolation_not_external_H_accuracy'})
    return rows, unavailable


def summarize_terrain(rows):
    frame = pd.DataFrame(rows)
    if frame.empty: raise ValueError('Nenhuma métrica interna disponível')
    if frame.duplicated(['corridor_id', 'wx', 'wy', 'split']).any():
        raise ValueError('Janelas repetidas na síntese')
    result = {}
    for split, group in frame.groupby('split'):
        valid = group.loc[group.n_valid.gt(0) & group.rmse_m.notna()]
        result[split] = {'n_windows': len(group), 'n_corridors': int(group.corridor_id.nunique()),
            'n_windows_with_valid_residuals': len(valid),
            'n_evaluated_records': int(group.n_evaluated.sum()), 'n_valid_records': int(group.n_valid.sum()),
            'valid_record_fraction': float(group.n_valid.sum()/group.n_evaluated.sum()),
            'window_rmse_m': {name: float(np.quantile(valid.rmse_m, q, method='linear')) if len(valid) else None for name, q in
                [('minimum', 0), ('q25', .25), ('median', .5), ('q75', .75), ('maximum', 1)]},
            'not_external_accuracy': True, 'window_summary_weighting': 'one_weight_per_window_not_per_return',
            'records_not_independent_replicates': True}
    return result
