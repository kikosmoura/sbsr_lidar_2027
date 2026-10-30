"""Conferência descritiva de retornos e listas; sem validação semântica externa."""
import math
import numpy as np


def retained_returns(frame, classes=(3,4,5), minimum_height=3.):
    valid = ((frame.qc_flags.to_numpy() & 2)==0) & frame.terrain_status.eq(0).to_numpy() & np.isfinite(frame.h)
    return (valid & frame.classification.isin(classes).to_numpy() & (frame.h>=minimum_height)
            & frame.observed.to_numpy(bool) & frame.inside_estimated_canopy.to_numpy(bool))


def describe_returns(frame, tolerance=1e-9):
    if frame.empty: return {'n':0, 'P95_m':None, 'IQR_m':None, 'quantiles_m':None}
    if frame.duplicated(['source_tile','source_point_index']).any(): raise ValueError('Registro de origem duplicado')
    h=frame.h.to_numpy(float)
    if not np.isfinite(h).all(): raise ValueError('Altura não finita entre retornos selecionados')
    error=float(np.max(np.abs(h-(frame.z_absolute-frame.terrain_z))))
    if error>tolerance: raise ValueError('H difere de Z absoluto menos terreno')
    q=np.quantile(h,[0,.05,.25,.5,.75,.95,1.],method='linear')
    above=h>=q[5]
    return {'n':len(frame),'P95_m':float(q[5]),'IQR_m':float(q[4]-q[2]),
        'quantiles_m':dict(zip(['min','p05','p25','median','p75','p95','max'],map(float,q))),
        'height_identity_max_error_m':error,'records_at_or_above_P95':int(above.sum()),
        'one_metre_cells_at_or_above_P95':int(frame.loc[above,['raster_row','raster_col']].drop_duplicates().shape[0]),
        'candidate_classes':{str(int(k)):int(v) for k,v in frame.classification.value_counts().sort_index().items()},
        'uncertain_pixel_records':int(frame.uncertain_pixel.sum()),
        'records_are_not_independent_trees':True}


def top_turnover(base, scenario, fraction=.2):
    if base.unit_id.duplicated().any() or scenario.unit_id.duplicated().any(): raise ValueError('IDs de ranking repetidos')
    if set(base.unit_id)!=set(scenario.unit_id) or not len(base): raise ValueError('Listas precisam do mesmo universo não vazio')
    k=math.ceil(len(base)*fraction)
    left=set(base.sort_values('rank_ordinal').head(k).unit_id)
    right=set(scenario.sort_values('rank_ordinal').head(k).unit_id)
    shared=left&right
    return {'n':len(base),'k':k,'shared_n':len(shared),'lost_n':len(left-right),'gained_n':len(right-left),
        'replacement_fraction':len(left-right)/k,'retained_fraction':len(shared)/k,
        'jaccard':len(shared)/len(left|right),'shared_ids':sorted(shared),'lost_ids':sorted(left-right),'gained_ids':sorted(right-left),
        'selection_rule':'exact_k_ordinal_with_ID_tie_breaking_not_ecological_priority'}
