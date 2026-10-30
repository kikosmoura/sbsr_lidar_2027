"""Quadro e escolha intencional de janelas; proxies nunca são rótulos humanos."""
import hashlib
import math

import geopandas as gpd
import numpy as np
import pyarrow.parquet as pq
import rasterio
import shapely
from rasterio.features import geometry_mask
from shapely.geometry import box


def stable_id(prefix,*values):
    return prefix+hashlib.sha256('|'.join(map(str,values)).encode()).hexdigest()[:14]


def corridor_groups(config):
    frame=gpd.read_file(config.paths.corridors)
    field=config.pilot.corridor_field
    if frame.crs is None or frame.crs.to_epsg()!=config.grid.epsg or not frame.geometry.is_valid.all():
        raise ValueError('Corredores inválidos ou CRS incompatível para reservar grupos')
    if field not in frame or frame[field].isna().any() or frame[field].duplicated().any():
        raise ValueError('Identificador de corredor precisa ser único e não nulo')
    ids=frame[field].astype(str).tolist()
    parent=list(range(len(ids)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    pairs=frame.sindex.query(frame.geometry,predicate='intersects')
    for a,b in zip(*pairs):
        if a<b: parent[find(a)]=find(b)
    members={}
    for i,code in enumerate(ids): members.setdefault(find(i),[]).append(code)
    mapping={code:stable_id('G05_',*sorted(group)) for group in members.values() for code in group}
    main=mapping[config.pilot.corridor_id];test=mapping[config.pilot.adversarial_corridor]
    if main==test: raise ValueError('Principal e adverso pertencem ao mesmo grupo: não criar divisão treino/teste com vazamento')
    rows=[{'corridor_id':code,'group_id':mapping[code],
           'fold':'treino' if mapping[code]==main else 'teste' if mapping[code]==test else 'nao_atribuido'} for code in sorted(ids)]
    return rows,mapping


def make_frame(config,domain,products,group_id,fold):
    size=config.reference.window_size_m
    xmin,ymin,xmax,ymax=domain.context.bounds
    rows=[]
    for ix in range(math.floor((xmin-config.grid.origin_x)/size),math.ceil((xmax-config.grid.origin_x)/size)):
        for iy in range(math.floor((ymin-config.grid.origin_y)/size),math.ceil((ymax-config.grid.origin_y)/size)):
            left=config.grid.origin_x+ix*size;bottom=config.grid.origin_y+iy*size
            rectangle=box(left,bottom,left+size,bottom+size)
            context=rectangle.intersection(domain.context)
            if context.area<config.reference.minimum_context_area_m2: continue
            rows.append({'window_id':stable_id('W05_',domain.corridor_id,config.grid.epsg,size,ix,iy),
                'case':domain.case,'corridor_id':domain.corridor_id,'group_id':group_id,'fold':fold,
                'grid_col':ix,'grid_row':iy,'context_area_m2':context.area,
                'measurement_area_m2':rectangle.intersection(domain.measurement).area,
                'edge':bool(rectangle.intersects(domain.measurement.boundary)),
                'points':0,'valid_h_points':0,'low_h_points':0,'high_h_points':0,'negative_alert_points':0,
                **{f'class_{code}':0 for code in [1,2,3,4,5,6,8]},'geometry':rectangle})
    frame=gpd.GeoDataFrame(rows,crs=config.grid.epsg)
    if frame.empty: raise ValueError('Quadro de janelas vazio')
    frame['regular_eligible']=(frame.context_area_m2>=size**2*config.reference.minimum_regular_context_fraction) & (
        frame.measurement_area_m2>=size**2*config.reference.minimum_regular_measurement_fraction)
    lookup={(int(r.grid_col),int(r.grid_row)):i for i,r in frame.iterrows()}
    numeric=['points','valid_h_points','low_h_points','high_h_points','negative_alert_points']+[f'class_{k}' for k in [1,2,3,4,5,6,8]]
    values=np.zeros((len(frame),len(numeric)),dtype=np.int64)
    for batch in pq.ParquetFile(products['alturas_pontos.parquet']).iter_batches(batch_size=65536,columns=['x','y','h','classification']):
        b=batch.to_pandas()
        ix=np.floor((b.x.to_numpy()-config.grid.origin_x)/size).astype(np.int64)
        iy=np.floor((b.y.to_numpy()-config.grid.origin_y)/size).astype(np.int64)
        index=np.fromiter((lookup.get((int(x),int(y)),-1) for x,y in zip(ix,iy)),dtype=np.int64)
        h=b.h.to_numpy();cls=b.classification.to_numpy()
        masks=[np.ones(len(b),dtype=bool),np.isfinite(h),
               (h>=config.reference.low_height_range_m[0]) & (h<config.reference.low_height_range_m[1]),
               h>=config.reference.high_height_m,h<config.terrain.negative_warning_m]+[cls==k for k in [1,2,3,4,5,6,8]]
        for column,mask in enumerate(masks):
            use=mask & (index>=0)
            values[:,column]+=np.bincount(index[use],minlength=len(frame))
    frame[numeric]=values
    frame['density_records_m2']=frame.points/frame.context_area_m2
    with rasterio.open(products['contagens_altura.tif']) as density,rasterio.open(products['primary_validity']) as validity:
        observation=density.read(1,masked=True)
        valid=validity.read(1)
        for i,row in frame.iterrows():
            effective=row.geometry.intersection(domain.context)
            mask=geometry_mask([effective],density.shape,density.transform,invert=True) & ~observation.mask
            frame.loc[i,'context_cells']=int(mask.sum())
            frame.loc[i,'empty_cells']=int(np.sum(mask & (observation.data==0)))
            frame.loc[i,'invalid_terrain_cells']=int(np.sum(mask & (valid!=0)))
    return frame


def targets(row,low_density,high_density):
    tags={f'class_{code}' for code in [1,2,3,4,5,6,8] if row[f'class_{code}']>0}
    for key in ['low_h_points','high_h_points','negative_alert_points','empty_cells','invalid_terrain_cells']:
        if row[key]>0: tags.add(key)
    if row['edge']:tags.add('edge')
    if row['density_records_m2']<=low_density:tags.add('low_density')
    if row['density_records_m2']>=high_density:tags.add('high_density')
    return tags


def select_windows(frame,count,seed):
    data=frame.loc[frame.regular_eligible | (frame.negative_alert_points>0)].sort_values('window_id').copy()
    if len(data)<count: raise ValueError('Quadro elegível menor que o número solicitado de janelas')
    low,high=np.quantile(data.density_records_m2,[.25,.75])
    tags={i:targets(row,low,high) for i,row in data.iterrows()}
    available=set().union(*tags.values())
    covered=set();chosen=[]
    rng=np.random.default_rng(seed)
    random_priority={i:float(rng.random()) for i in data.index}
    frequency={tag:sum(tag in t for t in tags.values()) for tag in available}
    mandatory=list(data.index[data.negative_alert_points>0])
    if len(mandatory)>count: raise ValueError('Alertas ocupam mais janelas que a cota: revisar plano explicitamente')
    for step in range(count):
        remaining=[i for i in data.index if i not in chosen]
        def score(i):
            unseen=tags[i]-covered
            weight=sum((10 if tag=='negative_alert_points' else 1)/frequency[tag] for tag in unseen)
            if not chosen:distance=0
            else:
                center=data.loc[i].geometry.centroid
                distance=min(center.distance(data.loc[j].geometry.centroid) for j in chosen)
            return (weight,distance,random_priority[i])
        selected=mandatory[step] if step<len(mandatory) else max(remaining,key=score)
        chosen.append(selected)
        data.loc[selected,'selection_step']=step+1
        data.loc[selected,'selection_new_targets']=';'.join(sorted(tags[selected]-covered))
        covered.update(tags[selected])
    selected=data.loc[chosen].copy()
    selected['selection_proxies']=[';'.join(sorted(tags[i])) for i in chosen]
    selected['inclusion_probability']=np.nan
    selected['design']='intentional_coverage_spatial_spread_seeded_ties'
    selected['intended_use']=np.where(selected.negative_alert_points>0,'qa',selected.fold)
    return selected,{'available_proxy_targets':sorted(available),'covered_proxy_targets':sorted(covered),
        'all_frame_windows':len(frame),'regular_eligible_windows':int(frame.regular_eligible.sum()),
        'eligible_including_mandatory_qa':len(data),
        'not_covered_proxy_targets':sorted(available-covered),'inclusion_probabilities_known':False,
        'design':'intentional_coverage_spatial_spread_seeded_ties; no_population_weights',
        'density_quartiles_records_m2':[float(low),float(high)],'seed':seed}
