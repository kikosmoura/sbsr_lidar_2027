"""Mapas dos valores físicos e suporte; não são escores ou prioridades."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/sbsr_mpl_etapa08')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.patches import Patch
import geopandas as gpd

from sbsr_lidar.storage import read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    r = read_json(args.report)
    table = gpd.read_parquet(Path(r['products_root'])/'indicadores.parquet')
    grid = table.loc[(table.family == 'grid') & (table.nominal_size_m == 50)].copy()
    fig, axes = plt.subplots(1, 4, figsize=(17, 9 if r['case'] == 'main' else 6))
    fig.subplots_adjust(left=.045, right=.99, bottom=.16, top=.85, wspace=.65)
    specs = [('fraction_observed', 'Área observada / área total', 'Blues', 0, 1, None),
             ('I1', 'I1 — copa candidata / observado', 'YlGn', 0, 1, 'eligible_A'),
             ('I6', 'I6 — P95 dos retornos H (m)', 'viridis', 3, 30, 'eligible_A_plus_3D'),
             ('I7', 'I7 — IQR dos retornos H (m)', 'magma', 0, 15, 'eligible_A_plus_3D')]
    for ax, (column, title, cmap, lower, upper, eligibility) in zip(axes, specs):
        grid.plot(ax=ax, color='#d4d8db', edgecolor='#57616a', linewidth=.5)
        finite = grid.loc[grid[column].notna()]
        if len(finite):
            finite.plot(ax=ax, column=column, cmap=cmap, vmin=lower, vmax=upper,
                        edgecolor='#57616a', linewidth=.4)
        colorbar = fig.colorbar(ScalarMappable(norm=Normalize(lower, upper), cmap=cmap), ax=ax,
                               shrink=.55, fraction=.05, pad=.03)
        colorbar.set_label('fração' if column in ['I1', 'fraction_observed'] else 'm', fontsize=8)
        colorbar.ax.tick_params(labelsize=7)
        if eligibility:
            invalid = grid.loc[~grid[eligibility]]
            if len(invalid): invalid.plot(ax=ax, facecolor='none', edgecolor='#707070', linewidth=.5, hatch='///')
        ax.set_title(title, fontsize=9)
        ax.set_aspect('equal'); ax.set_xlabel('E (m)'); ax.set_ylabel('N (m)')
        ax.ticklabel_format(useOffset=False, style='plain')
        ax.tick_params(axis='x', rotation=40, labelsize=7); ax.tick_params(axis='y', labelsize=7)
    fig.suptitle(f"{r['domain']['corridor_id']} — indicadores físicos na grade de 50 m\nMáscara candidata não validada; alturas dos retornos, sem escores ou rankings", fontsize=12)
    fig.legend(handles=[Patch(facecolor='#d4d8db', label='Métrica ausente: consultar motivo na tabela'),
                        Patch(facecolor='none', edgecolor='#707070', hatch='///', label='Unidade inelegível para a comparação indicada')],
               loc='lower center', ncol=2, fontsize=8)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output_dir/f"indicadores_50m_{r['case']}.png", dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    main()
