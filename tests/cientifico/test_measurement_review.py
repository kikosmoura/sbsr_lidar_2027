"""Guardas contra pseudo-replicação, seleção alterada e acurácia fictícia."""
import copy
import pandas as pd
import pytest
from sbsr_lidar.measurement_review import pair_distribution, terrain_holdouts, summarize_terrain


def pairs():
    return pd.DataFrame({'unit_i': ['a', 'c'], 'unit_j': ['b', 'd'], 'corridor_i': ['x', 'x'],
        'corridor_j': ['x', 'x'], 'absolute_P95_difference_m': [0., 20.], 'absolute_IQR_difference_m': [1., 2.]})


def test_distribution_does_not_drop_near_zero_values():
    r = pair_distribution(pairs(), expected=2).set_index('descriptor').loc['P95']
    assert r.minimum_m == 0.
    assert r.maximum_m == 20.
    assert r.median_m == 10.
    assert r.n_pairs == 2


def test_reused_ID_or_missing_difference_cannot_hide_pairs():
    p = pairs(); p.loc[1, 'unit_j'] = 'a'
    with pytest.raises(ValueError, match='reutilizam'): pair_distribution(p, 2)
    p = pairs(); p.loc[1, 'absolute_P95_difference_m'] = float('nan')
    with pytest.raises(ValueError, match='ausentes'): pair_distribution(p, 2)


def document():
    return {'external_accuracy_validated': False, 'terrain_holdout': [{'wx': 1, 'wy': 2, 'metrics': [
        {'method': 'tin', 'radius_m': 5., 'split': 'reserved_points', 'n': 90, 'evaluated': 100,
         'rmse_m': .1, 'mae_m': .05, 'bias_m': .01, 'p95_abs_m': .2, 'valid_fraction': .9}]}]}


def test_internal_terrain_QC_never_becomes_external_accuracy():
    rows, missing = terrain_holdouts(document(), 'c')
    result = summarize_terrain(rows)['reserved_points']
    assert result['not_external_accuracy']
    assert result['records_not_independent_replicates']
    assert missing[0]['split'] == 'reserved_blocks'
    d = document(); d['external_accuracy_validated'] = True
    with pytest.raises(ValueError, match='interna'): terrain_holdouts(d, 'c')


def test_window_summary_does_not_weight_rmse_by_point_count():
    rows, _ = terrain_holdouts(document(), 'c')
    other = dict(rows[0], wx=2, n_valid=9, n_evaluated=10, rmse_m=1.)
    result = summarize_terrain(rows+[other])['reserved_points']
    assert result['window_rmse_m']['median'] == pytest.approx(.55)
    assert result['valid_record_fraction'] == pytest.approx(.9)


def test_duplicate_window_or_invalid_support_is_rejected():
    rows, _ = terrain_holdouts(document(), 'c')
    with pytest.raises(ValueError, match='repetidas'): summarize_terrain(rows+rows)
    d = document(); d['terrain_holdout'][0]['metrics'][0]['n'] = 100
    with pytest.raises(ValueError, match='contagens'): terrain_holdouts(d, 'c')


def test_interpolator_not_in_protocol_is_not_selected_as_better():
    d = document(); alternative = copy.deepcopy(d['terrain_holdout'][0]['metrics'][0])
    alternative.update(method='idw', rmse_m=.001); d['terrain_holdout'][0]['metrics'].append(alternative)
    rows, _ = terrain_holdouts(d, 'c')
    assert len(rows) == 1
    assert rows[0]['rmse_m'] == .1


def test_zero_support_window_stays_in_coverage_denominator_without_zero_error():
    a = document(); b = document(); b['terrain_holdout'][0]['wx'] = 2
    b['terrain_holdout'][0]['metrics'][0].update(n=0, valid_fraction=0., rmse_m=None,
        mae_m=None, bias_m=None, p95_abs_m=None)
    left, _ = terrain_holdouts(a, 'c'); right, missing = terrain_holdouts(b, 'c')
    r = summarize_terrain(left+right)['reserved_points']
    assert r['n_windows'] == 2
    assert r['n_windows_with_valid_residuals'] == 1
    assert r['valid_record_fraction'] == pytest.approx(.45)
    assert r['window_rmse_m']['median'] == .1
    assert any(x['reason'] == 'no_valid_residuals' for x in missing)
