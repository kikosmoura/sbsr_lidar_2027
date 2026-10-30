"""TIN/IDW locais, sem extrapolação; nuvem MDT limitada à janela do piloto."""
from __future__ import annotations

import numpy as np
from scipy.spatial import Delaunay, cKDTree, QhullError

STATUS = {0: "valid", 1: "outside_convex_hull", 2: "nearest_beyond_radius",
          3: "unsupported_triangle", 4: "too_few_idw_neighbors", 5: "one_sided_idw_neighbors"}


class Surface:
    def __init__(self, xyz: np.ndarray, parameters):
        xyz = np.asarray(xyz,dtype=np.float64)
        if xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz)<3 or not np.isfinite(xyz).all():
            raise ValueError("Terreno requer ao menos três XYZ finitos não colineares")
        self.xyz = xyz
        self.parameters = parameters
        self.origin = xyz[:,:2].mean(axis=0)
        self.xy = xyz[:,:2]-self.origin
        self.tree = cKDTree(self.xy)
        try:
            self.tri = Delaunay(self.xy)
        except QhullError as error:
            raise ValueError("MDT sem geometria suficiente para triangulação 2D") from error
        v = self.xy[self.tri.simplices]
        a = np.linalg.norm(v[:,1]-v[:,0],axis=1)
        b = np.linalg.norm(v[:,2]-v[:,1],axis=1)
        c = np.linalg.norm(v[:,0]-v[:,2],axis=1)
        cross = np.abs((v[:,1,0]-v[:,0,0])*(v[:,2,1]-v[:,0,1])-(v[:,1,1]-v[:,0,1])*(v[:,2,0]-v[:,0,0]))
        self.edges = np.maximum.reduce([a,b,c])
        self.circumradii = np.divide(a*b*c,2*cross,out=np.full_like(a,np.inf),where=cross>0)

    def query(self, xy: np.ndarray, radius: float) -> dict:
        xy = np.asarray(xy,dtype=np.float64)
        if xy.ndim != 2 or xy.shape[1] != 2 or not np.isfinite(xy).all() or radius<=0:
            raise ValueError("Consulta requer XY finitos e raio positivo")
        local = xy-self.origin
        n = len(local)
        k = self.parameters.idw_neighbors
        distances, indices = self.tree.query(local,k=list(range(1,k+1)),workers=1)
        nearest = distances[:,0]
        counts = self.tree.query_ball_point(local,radius,return_length=True,workers=1)
        simplex = self.tri.find_simplex(local)
        inside = simplex >= 0
        si = np.maximum(simplex,0)
        vertices = self.tri.simplices[si]
        vertex_distance = np.linalg.norm(self.xy[vertices]-local[:,None,:],axis=2).max(axis=1)
        edge = np.where(inside,self.edges[si],np.nan)
        circumradius = np.where(inside,self.circumradii[si],np.nan)
        supported = inside & (nearest<=radius) & (vertex_distance<=radius+1e-9) & (
            edge<=self.parameters.triangle_edge_radius_factor*radius+1e-9) & (circumradius<=radius+1e-9)
        status = np.full(n,3,dtype=np.uint8)
        status[~inside]=1
        status[inside & (nearest>radius)]=2
        status[supported]=0
        bary = np.einsum('nij,nj->ni',self.tri.transform[si,:2],local-self.tri.transform[si,2])
        bary = np.column_stack([bary,1-bary.sum(axis=1)])
        tin = np.sum(bary*self.xyz[vertices,2],axis=1)
        tin[status!=0]=np.nan
        # IDW requer o mesmo suporte geométrico do TIN e vizinhos ao redor da consulta.
        safe_indices = np.minimum(indices,len(self.xyz)-1)
        selected = (distances<=radius) & (indices<len(self.xyz))
        idw_status = status.copy()
        idw_status[(status==0)&(selected.sum(axis=1)<self.parameters.idw_min_neighbors)]=4
        vectors = self.xy[safe_indices]-local[:,None,:]
        angles = np.arctan2(vectors[:,:,1],vectors[:,:,0])
        angles[~selected]=np.inf
        angles.sort(axis=1)
        with np.errstate(invalid='ignore'):
            gaps = np.diff(angles,axis=1)
        gaps[~np.isfinite(gaps)] = 0
        last = np.maximum(selected.sum(axis=1)-1,0)
        with np.errstate(invalid='ignore'):
            wrap = 2*np.pi+angles[:,0]-angles[np.arange(n),last]
        max_gap = np.maximum(gaps.max(axis=1),wrap)
        idw_status[(idw_status==0)&(max_gap>np.pi+1e-8)]=5
        weights = np.zeros_like(distances)
        np.divide(1,np.maximum(distances,1e-12)**self.parameters.idw_power,out=weights,where=selected)
        weight_sum = weights.sum(axis=1)
        idw = np.divide(np.sum(weights*self.xyz[safe_indices,2],axis=1),weight_sum,
                        out=np.full(n,np.nan),where=weight_sum>0)
        idw[idw_status!=0]=np.nan
        # Uma observação exata é dado conhecido; não exige interpolação de triângulo.
        exact = nearest<=1e-7
        tin[exact]=idw[exact]=self.xyz[indices[exact,0],2]
        status[exact]=idw_status[exact]=0
        return {'tin':tin,'idw':idw,'tin_status':status,'idw_status':idw_status,
                'nearest':nearest,'count':counts,'triangle_edge':edge,'circumradius':circumradius}


def normalize_z(z_absolute, terrain_z):
    """Elevações absolutas decodificadas; user_data nunca participa da subtração."""
    return np.asarray(z_absolute,dtype=np.float64)-np.asarray(terrain_z,dtype=np.float64)


def error_metrics(residual):
    values=np.asarray(residual)
    values=values[np.isfinite(values)]
    if not len(values):
        return {'n':0,'bias_m':None,'mae_m':None,'rmse_m':None,'p95_abs_m':None}
    return {'n':len(values),'bias_m':float(values.mean()),'mae_m':float(np.abs(values).mean()),
            'rmse_m':float(np.sqrt(np.mean(values**2))),'p95_abs_m':float(np.quantile(np.abs(values),.95))}
