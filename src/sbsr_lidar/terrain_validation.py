"""Erro de interpolação em pontos e blocos MDT reservados, sem referência externa."""
import numpy as np

from .terrain_surface import Surface, error_metrics


def reserved_splits(xyz, config):
    n=len(xyz)
    rng=np.random.default_rng(config.resources.seed)
    count=min(config.terrain.validation_max_points,max(1,int(n*config.terrain.validation_fraction)))
    random=np.zeros(n,dtype=bool)
    random[rng.choice(n,count,replace=False)]=True
    blocks=np.floor(xyz[:,:2]/config.terrain.validation_block_m).astype(np.int64)
    hashed=(blocks[:,0]*73856093) ^ (blocks[:,1]*19349663) ^ config.resources.seed
    modulo=max(2,int(round(1/config.terrain.validation_fraction)))
    spatial=hashed % modulo == 0
    return {'reserved_points':random,'reserved_blocks':spatial}


def validate_surfaces(xyz, config, radii, event):
    rows=[]
    samples=[]
    records={}
    for split,held in reserved_splits(xyz,config).items():
        train=xyz[~held]
        test=xyz[held]
        if len(train)<3 or not len(test):
            records[split]={'status':'insufficient_support','train':len(train),'held':len(test)}
            continue
        rng=np.random.default_rng(config.resources.seed+1)
        if len(test)>config.terrain.validation_max_points:
            test=test[rng.choice(len(test),config.terrain.validation_max_points,replace=False)]
        model=Surface(train,config.terrain)
        event('validation',split=split,train=len(train),held=int(held.sum()),evaluated=len(test))
        records[split]={'status':'evaluated','train':len(train),'held':int(held.sum()),'evaluated':len(test),
                        'all_held_xy_excluded_from_training':True,'block_size_m':config.terrain.validation_block_m if split=='reserved_blocks' else None}
        for radius in radii:
            predicted=model.query(test[:,:2],radius)
            common=np.isfinite(predicted['tin']) & np.isfinite(predicted['idw'])
            for method in ['tin','idw']:
                residual=predicted[method]-test[:,2]
                row={'split':split,'method':method,'radius_m':radius,'evaluated':len(test),
                     'valid_fraction':float(np.isfinite(residual).mean()),**error_metrics(residual),
                     'common':error_metrics(residual[common])}
                rows.append(row)
            for i in range(len(test)):
                samples.append({'split':split,'radius_m':radius,'x':float(test[i,0]),'y':float(test[i,1]),'z_mdt':float(test[i,2]),
                    'tin':float(predicted['tin'][i]) if np.isfinite(predicted['tin'][i]) else None,
                    'idw':float(predicted['idw'][i]) if np.isfinite(predicted['idw'][i]) else None,
                    'tin_status':int(predicted['tin_status'][i]),'idw_status':int(predicted['idw_status'][i])})
    return {'scope':'held_out_MDT_interpolation_error_not_external_absolute_accuracy',
            'seed':config.resources.seed,'splits':records,'metrics':rows},samples


def choose_method(validation,config,requested):
    if requested in {'tin','idw'}:
        return requested,{'rule':'explicit_method','method':requested}
    if config.terrain.method in {'tin','idw'}:
        return config.terrain.method,{'rule':'configured_method','method':config.terrain.method}
    for split in ['reserved_blocks','reserved_points']:
        pair=[r for r in validation['metrics'] if r['split']==split and r['radius_m']==config.terrain.maximum_distance_m]
        if len(pair)==2 and all(r['common']['n']>=config.terrain.minimum_common_validation for r in pair):
            best=min(pair,key=lambda r:(round(r['common']['rmse_m'],8),r['method']!='tin'))
            return best['method'],{'rule':'minimum_common_support_RMSE_at_fixed_radius','split':split,
                                  'radius_m':config.terrain.maximum_distance_m,'metrics':pair}
    raise ValueError('Validação comum insuficiente para escolher TIN/IDW; revisar QC ou fixar método explicitamente')
