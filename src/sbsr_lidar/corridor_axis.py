"""Voronoi de borda: grafo revisável e aceitação geométrica conservadora por parte."""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import Voronoi, cKDTree
from shapely.geometry import LineString, Point

from .spatial_units import stable_geometry_id


def boundary_sites(polygon, spacing, maximum):
    points = []
    for ring in [polygon.exterior, *polygon.interiors]:
        coords = list(ring.coords)
        for a, b in zip(coords, coords[1:]):
            a, b = np.array(a), np.array(b)
            count = max(1, math.ceil(np.linalg.norm(b-a)/spacing))
            if len(points)+count > maximum:
                raise ValueError('Borda excede orçamento Voronoi do piloto')
            points.extend(a+(b-a)*t/count for t in range(count))
    return np.unique(np.round(points, 8), axis=0)


def adjacency(edges):
    result = {}
    for a, b in edges:
        result.setdefault(a, set()).add(b)
        result.setdefault(b, set()).add(a)
    return result


def graph_chains(edges, coordinates):
    graph = adjacency(edges)
    seen = set()
    chains = []

    def walk(start, follow):
        chain = [start, follow]
        seen.add(tuple(sorted((start, follow))))
        while len(graph[chain[-1]]) == 2 and chain[-1] != start:
            nxt = next(n for n in graph[chain[-1]] if n != chain[-2])
            seen.add(tuple(sorted((chain[-1], nxt))))
            chain.append(nxt)
        if tuple(coordinates[chain[0]]) > tuple(coordinates[chain[-1]]):
            chain.reverse()
        return chain

    for start in sorted(graph):
        if len(graph[start]) == 2:
            continue
        for follow in sorted(graph[start]):
            if tuple(sorted((start, follow))) not in seen:
                chains.append(walk(start, follow))
    for a, b in sorted(edges):
        if tuple(sorted((a, b))) not in seen:
            chains.append(walk(a, b))
    return chains


def extract_axis(polygon, part_id, parameters):
    sites = boundary_sites(polygon, parameters.boundary_spacing_m, parameters.maximum_boundary_sites)
    origin = sites.mean(axis=0)
    vor = Voronoi(sites-origin)
    coords = vor.vertices+origin
    edges = set()
    for ridge in vor.ridge_vertices:
        if len(ridge) == 2 and min(ridge) >= 0:
            line = LineString(coords[ridge])
            if line.length > 1e-7 and polygon.covers(line):
                edges.add(tuple(sorted(ridge)))
    # Qhull pode produzir vértices distintos separados por ruído submilimétrico.
    # Contrair somente coincidências numéricas antes de medir graus do grafo.
    nodes = sorted({n for e in edges for n in e})
    parent = {n: n for n in nodes}

    def root(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    if nodes:
        for a, b in sorted(cKDTree(coords[nodes]).query_pairs(parameters.axis_node_snap_tolerance_m)):
            a, b = root(nodes[a]), root(nodes[b])
            parent[max(a, b)] = min(a, b)
    merged = sum(root(n) != n for n in nodes)
    edges = {tuple(sorted((root(a), root(b)))) for a, b in edges if root(a) != root(b)}
    edges = {e for e in edges if polygon.covers(LineString(coords[list(e)]))}
    original = graph_chains(edges, coords)
    graph = adjacency(edges)
    pruned = []
    # Uma passagem, sem descascar recursivamente ramos mais longos.
    for chain in original:
        a, b = chain[0], chain[-1]
        terminal = len(graph[a]) == 1 or len(graph[b]) == 1
        if not terminal or (len(graph[a]) == len(graph[b]) == 1):
            continue
        joint = b if len(graph[a]) == 1 else a
        radius = polygon.boundary.distance(Point(coords[joint]))
        line = LineString(coords[chain])
        if (line.length <= parameters.terminal_spur_maximum_m
                and line.length <= parameters.terminal_spur_radius_factor*radius):
            pruned.append({'branch_id': part_id+'_R'+stable_geometry_id(line),
                           'length_m': line.length, 'join_radius_m': radius,
                           'reason': 'short_terminal_corner_bisector_single_pass', 'geometry': line})
            for a, b in zip(chain, chain[1:]):
                edges.discard(tuple(sorted((a, b))))
    graph = adjacency(edges)
    chains = graph_chains(edges, coords)
    rows = []
    for chain in chains:
        line = LineString(coords[chain])
        widths = [2*polygon.boundary.distance(line.interpolate(t, normalized=True))
                  for t in np.linspace(.05, .95, 19)]
        median_width = float(np.median(widths))
        rows.append({'branch_id': part_id+'_R'+stable_geometry_id(line), 'part_id': part_id,
            'length_m': line.length, 'start_degree': len(graph[chain[0]]),
            'end_degree': len(graph[chain[-1]]), 'median_width_m': median_width,
            'aspect_ratio': line.length/median_width if median_width > 0 else 0.,
            'closed': chain[0] == chain[-1], 'geometry': line})
    rows.sort(key=lambda r: r['branch_id'])
    acceptable = (len(rows) == 1 and not rows[0]['closed'] and not polygon.interiors
                  and rows[0]['length_m'] >= parameters.minimum_axis_length_m
                  and rows[0]['aspect_ratio'] >= parameters.minimum_axis_aspect_ratio)
    reason = ('single_open_elongated_chain_geometric_QC' if acceptable else
              'non_unique_branched_or_short_broad_or_closed_axis_use_grid')
    for row in rows:
        row.update(axis_accepted=acceptable, review_reason=reason,
                   review_kind='computational_geometric_QC_not_independent_human_validation')
    junctions = []
    for node, neighbors in sorted(graph.items()):
        if len(neighbors) > 2:
            point = Point(coords[node])
            junctions.append({'junction_id': part_id+'_J'+stable_geometry_id(point),
                'part_id': part_id, 'degree': len(neighbors),
                'radius_m': polygon.boundary.distance(point), 'geometry': point})
    return rows, pruned, junctions, {'part_id': part_id, 'boundary_sites': len(sites),
        'numerically_coincident_vertices_merged': merged,
        'original_branches': len(original), 'pruned_terminal_branches': len(pruned),
        'retained_branches': len(rows), 'junctions': len(junctions),
        'axis_accepted': acceptable, 'reason': reason, 'holes': len(polygon.interiors),
        'policy': 'single_open_elongated_chain_only; branched_parts_remain_grid'}
