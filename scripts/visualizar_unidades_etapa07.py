"""Mapas de suporte e eixos para revisão geométrica; sem inventar rótulos humanos."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/sbsr_mpl_etapa07')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import geopandas as gpd

from sbsr_lidar.storage import read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    r = read_json(args.report)
    gpkg = Path(r['products_root'])/'unidades_multiescala.gpkg'
    parts = gpd.read_file(gpkg, layer='partes')
    axes = gpd.read_file(gpkg, layer='eixos_candidatos')
    removed = gpd.read_file(gpkg, layer='ramos_podados')
    junctions = gpd.read_file(gpkg, layer='juncoes')
    sections = gpd.read_file(gpkg, layer='secoes')
    regions = gpd.read_file(gpkg, layer='influencia_50m')
    args.output_dir.mkdir(parents=True, exist_ok=True)

    def base(ax):
        parts.plot(ax=ax, color='#ece9e1', edgecolor='#303941', linewidth=.65)
        ax.set_aspect('equal')
        ax.set_xlabel('E (m)'); ax.set_ylabel('N (m)')
        ax.ticklabel_format(useOffset=False, style='plain')
        ax.tick_params(axis='x', rotation=30, labelsize=8)
        ax.tick_params(axis='y', labelsize=8)

    fig, panels = plt.subplots(1, 2, figsize=(12, 9), layout='constrained')
    for ax in panels:
        base(ax)
    if len(axes):
        rejected = axes.loc[~axes.axis_accepted.astype(bool)]
        if len(rejected): rejected.plot(ax=panels[0], color='#687b8d', linewidth=.9)
        accepted = axes.loc[axes.axis_accepted.astype(bool)]
        if len(accepted): accepted.plot(ax=panels[0], color='#126e82', linewidth=1.7)
    if len(removed): removed.plot(ax=panels[0], color='#d68f43', linewidth=.9)
    if len(junctions): junctions.plot(ax=panels[0], color='#bd4a43', markersize=12)
    panels[0].set_title(f'Eixo de Voronoi revisável\n{len(axes)} ramos retidos · {len(removed)} podados · {len(junctions)} junções')
    if len(regions):
        regions.reset_index().plot(ax=panels[1], column='index', cmap='Pastel2', edgecolor='#535353', linewidth=.7)
        sample = sections.iloc[::10]
        for state, color in [('unknown_support', '#cf7c2f'), ('candidate_present', '#227f58'), ('candidate_gap', '#6c5aa1')]:
            selection = sample.loc[sample.state == state]
            if len(selection): selection.plot(ax=panels[1], color=color, linewidth=.7)
        panels[1].set_title('Influência de segmentos de 50 m\nSeções a cada 10 m para exibição; cálculo a cada 1 m')
    else:
        zones = gpd.read_file(gpkg, layer='regioes_juncao')
        if len(zones): zones.plot(ax=panels[1], color='#e7b66c', alpha=.65)
        panels[1].set_title('Comparação longitudinal indisponível\nParte ramificada: manter comparação em grade')
    fig.suptitle(f"{r['domain']['corridor_id']} — revisão geométrica exploratória\nMáscara de copa congelada, ainda não validada; junções não são conectividade funcional", fontsize=12)
    legend = [Line2D([0], [0], color=c, label=t) for c, t in [
        ('#126e82', 'Eixo aceito geometricamente'), ('#687b8d', 'Ramos para revisão'),
        ('#d68f43', 'Ramos terminais podados'), ('#cf7c2f', 'Seção com suporte insuficiente')]]
    fig.legend(handles=legend, loc='outside lower center', ncol=2, fontsize=8)
    fig.savefig(args.output_dir/f"eixos_unidades_{r['case']}.png", dpi=170)
    plt.close(fig)
    fig, panels = plt.subplots(1, 3, figsize=(14, 8), layout='constrained')
    for scale, ax in zip(r['summary']['scales_m'], panels):
        base(ax)
        grid = gpd.read_file(gpkg, layer=f'grade_{scale:g}m')
        grid.plot(ax=ax, column='fraction_observed', cmap='YlGnBu', vmin=0, vmax=1,
                  edgecolor='#4b555b', linewidth=.4, legend=scale == 100)
        stats = r['summary']['grids'][f'{scale:g}']
        ax.set_title(f"Grade de {scale:g} m\n{stats['units']} fragmentos; {stats['eligible_area_observation']} com área/suporte mínimos", fontsize=10)
    fig.suptitle(f"{r['domain']['corridor_id']} — grades no mesmo polígono de medição\nCor: fração observada; elegibilidade não valida a classificação da copa", fontsize=12)
    fig.savefig(args.output_dir/f"grades_multiescala_{r['case']}.png", dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    main()
