"""Adapter for original PyCrown numerical routines (GPLv3; see third_party).

Executes the pinned original methods tree_detection/_get_kernel/_to_lonlat
without importing legacy GDAL/pandas IO. Crown growth modules are unmodified.
Plateau centroids are mapped to an observed maximum belonging to that plateau;
both original and adopted locations are retained, never called ground truth.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS']:
    os.environ[name]='1'
import numpy as np
import scipy.ndimage as ndimage
from shapely.geometry import Point


def run(job):
    started=time.monotonic(); root=Path(job['upstream_root'])
    source=root/'pycrown/pycrown.py'; parsed=ast.parse(source.read_text())
    original=next(node for node in parsed.body if isinstance(node,ast.ClassDef) and node.name=='PyCrown')
    methods=[node for node in original.body if isinstance(node,ast.FunctionDef) and node.name in {'_get_kernel','tree_detection','_to_lonlat'}]
    definition=ast.ClassDef(name='OriginalPyCrownDetection',bases=[],keywords=[],body=methods,decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[definition],type_ignores=[]))
    class NoTreesException(Exception): pass
    namespace={'np':np,'ndimage':ndimage,'filters':ndimage,'Point':Point,'NoTreesException':NoTreesException}
    exec(compile(module,str(source),'exec'),namespace)
    pc=namespace['OriginalPyCrownDetection']();pc.resolution=job['resolution_m'];pc.ul_lon=pc.ul_lat=0.
    data=np.load(job['input']); chm=np.ascontiguousarray(data['chm'],dtype=np.float32);valid=data['valid']
    chm[~valid|~np.isfinite(chm)]=0.
    original_xy=np.empty((0,2)); seeds=np.empty((2,0),dtype=np.int32); corrections=[]
    try:
        effective_radius=float(np.ceil(job['detection_radius_m']/job['resolution_m'])*job['resolution_m'])
        _,original_xy=pc.tree_detection(chm,ws=effective_radius,hmin=job['height_m'],return_trees=True)
        original_xy=np.asarray(original_xy,dtype=np.float64)
        cols=np.floor(original_xy[:,0]).astype(np.int32);rows=np.floor(original_xy[:,1]).astype(np.int32)
        slices=ndimage.find_objects(pc.tree_markers)
        for i,(sl,xy) in enumerate(zip(slices,original_xy)):
            region=pc.tree_markers[sl]==i+1
            if pc.tree_markers[rows[i],cols[i]]!=i+1:
                rr,cc=np.where(region);rr+=sl[0].start;cc+=sl[1].start
                distance=(cc+.5-xy[0])**2+(rr+.5-xy[1])**2
                chosen=int(np.argmin(distance));rows[i],cols[i]=rr[chosen],cc[chosen];corrections.append(i)
        seeds=np.ascontiguousarray(np.vstack([cols,rows]),dtype=np.int32)
    except NoTreesException: pass
    labels=np.zeros(chm.shape,dtype=np.int32)
    if seeds.shape[1]:
        filename='_crown_dalponteCIRC_numba.py' if job['algorithm']=='dalponteCIRC_numba' else '_crown_dalponte_numba.py'
        spec=importlib.util.spec_from_file_location('original_pycrown_backend',root/'pycrown'/filename)
        backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
        function=backend._crown_dalponteCIRC if job['algorithm']=='dalponteCIRC_numba' else backend._crown_dalponte
        # Zero padding protects edges without filling any missing observation.
        padded=np.pad(chm,1);shifted=seeds+1
        labels=function(padded,shifted,float(job['th_seed']),float(job['th_crown']),float(job['height_m']),
            float(job['crown_radius_m']/job['resolution_m']))[1:-1,1:-1].copy()
        if np.any((labels>0)&~valid):raise ValueError('PyCrown crossed missing support')
    output=Path(job['output']);temporary=output.with_suffix('.part.npz')
    np.savez_compressed(temporary,labels=labels,seeds=seeds,original_xy=original_xy,corrections=np.asarray(corrections,dtype=np.int32))
    temporary.replace(output)
    print(json.dumps({'ok':True,'algorithm':job['algorithm'],'seeds':seeds.shape[1],
        'plateau_centroids_relocated':len(corrections),'effective_detection_radius_m':float(np.ceil(job['detection_radius_m']/job['resolution_m'])*job['resolution_m']),'seconds':time.monotonic()-started,
        'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}),flush=True)


if __name__=='__main__': run(json.loads(Path(sys.argv[1]).read_text()))
