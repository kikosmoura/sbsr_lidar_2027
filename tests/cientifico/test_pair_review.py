import pandas as pd
import pytest
from sbsr_lidar.pair_review import retained_returns,describe_returns,top_turnover


def records():
    return pd.DataFrame({'source_tile':['t']*6,'source_point_index':range(6),
        'h':[3.,10.,15.,20.,25.,30.], 'z_absolute':[103.,110.,115.,120.,125.,130.],
        'terrain_z':[100.]*6, 'qc_flags':[0,2,0,0,0,0], 'terrain_status':[0,0,1,0,0,0],
        'classification':[3,4,5,6,5,5], 'observed':[True,True,True,True,False,True],
        'inside_estimated_canopy':[True,True,True,True,True,False],
        'raster_row':[0,0,1,1,2,2], 'raster_col':[0,1,0,1,0,1], 'uncertain_pixel':[False]*6})


def test_retention_respects_QC_support_classes_mask_and_original_threshold():
    f=records();assert list(f.loc[retained_returns(f),'source_point_index'])==[0]


def test_repeated_origin_cannot_inflate_the_upper_tail():
    f=records().iloc[[0,0]]
    with pytest.raises(ValueError,match='duplicado'):describe_returns(f)


def test_double_normalization_or_absolute_Z_as_H_is_rejected():
    f=records().iloc[:1].copy();f.h=f.z_absolute
    with pytest.raises(ValueError,match='Z absoluto'):describe_returns(f)


def test_empty_stress_subset_is_not_zero_height():
    r=describe_returns(records().iloc[:0]);assert r['P95_m'] is None and r['n']==0


def test_jaccard_loss_is_not_fraction_of_replaced_units():
    base=pd.DataFrame({'unit_id':range(68),'rank_ordinal':range(1,69)})
    alt=base.copy();order=list(range(10))+list(range(14,18))+list(range(10,14))+list(range(18,68))
    alt['rank_ordinal']=alt.unit_id.map({u:i+1 for i,u in enumerate(order)})
    r=top_turnover(base,alt)
    assert r['k']==14 and r['shared_n']==10 and r['lost_n']==r['gained_n']==4
    assert r['jaccard']==pytest.approx(10/18)
    assert r['replacement_fraction']==pytest.approx(4/14)
    assert r['replacement_fraction']!=pytest.approx(1-r['jaccard'])


def test_changed_universe_cannot_be_reported_as_selection_instability():
    a=pd.DataFrame({'unit_id':['a','b'],'rank_ordinal':[1,2]})
    with pytest.raises(ValueError,match='universo'):top_turnover(a,a.iloc[:1])
