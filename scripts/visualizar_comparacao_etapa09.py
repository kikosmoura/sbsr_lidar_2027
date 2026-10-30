"""Figuras descritivas de rankings, pareamentos de cobertura e pesos predefinidos."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/sbsr_mpl_etapa09')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.patches import Patch
import geopandas as gpd
import numpy as np
import pandas as pd

from sbsr_lidar.storage import read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(); report = read_json(args.report)
    root = Path(report['products_root']); args.output_dir.mkdir(parents=True, exist_ok=True)
    universe = gpd.read_parquet(root/'universo_unidades.parquet')
    universe = universe.loc[(universe.family == 'grid') & (universe.nominal_size_m == 50)]
    ranks = pd.read_parquet(root/'escores_rankings.parquet')
    ranks = ranks.loc[(ranks.family == 'grid') & (ranks.scale_m == 50) & (ranks.scope == 'conditional_canopy')]
    a = ranks.loc[ranks.variant_id == 'A'].set_index('unit_id')
    b = ranks.loc[ranks.variant_id == report['primary_variant']].set_index('unit_id')
    selected = universe.loc[universe.unit_id.isin(a.index)].copy()
    if selected.empty:
        raise ValueError('Sem universo pareado na grade de 50 m para mapa comparativo')
    selected['rank_A'] = selected.unit_id.map(a.rank_mean)
    selected['rank_A3D'] = selected.unit_id.map(b.rank_mean)
    selected['shift'] = selected.rank_A3D-selected.rank_A
    spatial = gpd.read_parquet(root/'desacordos_espaciais.parquet')
    top = spatial.loc[(spatial.family == 'grid') & (spatial.scale_m == 50)
        & (spatial.scope == 'conditional_canopy') & (spatial.top_fraction == report['primary_top_fraction'])]
    n, k = len(selected), int(np.ceil(len(selected)*report['primary_top_fraction']))
    fig, axes = plt.subplots(1, 4, figsize=(17, 8 if report['case'] == 'main' else 5.5))
    fig.subplots_adjust(left=.045, right=.94, bottom=.17, top=.84, wspace=.6)
    for ax in axes:
        universe.plot(ax=ax, color='#e0e1e2', edgecolor='#666f75', linewidth=.4)
        absent = universe.loc[universe.comparison_role == 'common_no_detected_canopy_stratum']
        if len(absent): absent.plot(ax=ax, color='#f1ce83', hatch='///', edgecolor='#77684d', linewidth=.5)
        ax.set_aspect('equal'); ax.set_xlabel('E (m)'); ax.set_ylabel('N (m)')
        ax.ticklabel_format(useOffset=False, style='plain'); ax.tick_params(axis='x', rotation=40, labelsize=7); ax.tick_params(axis='y', labelsize=7)
    specs = [('rank_A', 'Postos médios de A', 'viridis_r', 1, max(2, n)),
             ('rank_A3D', 'Postos médios de A+3D', 'viridis_r', 1, max(2, n)),
             ('shift', 'Deslocamento de posição\nA+3D − A', 'RdBu_r', -max(1., selected['shift'].abs().max()), max(1., selected['shift'].abs().max()))]
    for ax, (key, title, palette, lower, upper) in zip(axes, specs):
        selected.plot(ax=ax, column=key, cmap=palette, vmin=lower, vmax=upper, edgecolor='#677077', linewidth=.4)
        bar = fig.colorbar(ScalarMappable(norm=Normalize(lower, upper), cmap=palette), ax=ax, shrink=.55, fraction=.05, pad=.03)
        bar.ax.tick_params(labelsize=7); ax.set_title(title, fontsize=9)
    colors = {'kept': '#4b8b73', 'gained': '#4f7fb2', 'lost': '#cf7b54', 'neither': '#d4d4d4'}
    for category, color in colors.items():
        g = top.loc[top.disagreement == category]
        if len(g): g.plot(ax=axes[3], color=color, edgecolor='#677077', linewidth=.4)
    left, bottom, right, top_bound = universe.total_bounds
    pad_x, pad_y = (right-left)*.04, (top_bound-bottom)*.04
    for ax in axes:
        ax.set_xlim(left-pad_x, right+pad_x); ax.set_ylim(bottom-pad_y, top_bound+pad_y)
    axes[3].set_title(f'Top {100*report["primary_top_fraction"]:g}% — k={k}\n'+('Lista pequena; desempate operacional' if k < 5 else 'Mesmo universo e cardinalidade'), fontsize=9)
    weight = report['score_protocol']['parameters']['primary_vertical_weight']
    fig.suptitle(f"{report['source_indicators']['corridor_id']} — comparação exploratória em {n} unidades de 50 m\nA+3D: w={weight:g} e V+ · menor posto = maior contraste numérico · máscara não validada", fontsize=12)
    labels = [('kept', 'Em ambas as listas'), ('gained', 'Entrou em A+3D'), ('lost', 'Saiu em A+3D'), ('neither', 'Fora das duas')]
    handles = [Patch(color=colors[c], label=label) for c, label in labels]
    handles += [Patch(facecolor='#f1ce83', hatch='///', label='Sem copa detectada: estrato comum separado'), Patch(color='#e0e1e2', label='Fora do universo pareado')]
    fig.legend(handles=handles, loc='lower center', ncol=3, fontsize=8)
    fig.savefig(args.output_dir/f"rankings_50m_{report['case']}.png", dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    fig.subplots_adjust(left=.055, right=.98, bottom=.17, top=.78, wspace=.42)
    dots = axes[0].scatter(selected.I1, selected.I6, c=selected.I7, cmap='magma', s=28, edgecolors='#555555', linewidths=.35)
    bar = fig.colorbar(dots, ax=axes[0], shrink=.75); bar.set_label('IQR dos retornos H (m)', fontsize=8)
    axes[0].set_xlabel('I1 — T/O'); axes[0].set_ylabel('I6 — P95 dos retornos H (m)')
    axes[0].set_title(f'Indicadores separados · n={n}', fontsize=10)
    pairs = pd.read_parquet(root/'pares_cobertura_semelhante.parquet')
    pairs = pairs.loc[(pairs.family == 'grid') & (pairs.scale_m == 50)]
    if len(pairs):
        axes[1].hist(pairs.absolute_P95_difference_m, bins=min(12, max(3, len(pairs))), color='#477f8e', edgecolor='white')
    else:
        axes[1].text(.5, .5, 'Nenhum par atende aos critérios\nde cobertura/área observada', ha='center', va='center', transform=axes[1].transAxes, fontsize=9)
    axes[1].set_title(f'H1: {len(pairs)} pares · unidades compartilhadas', fontsize=10)
    axes[1].set_xlabel('|Diferença de P95| (m)'); axes[1].set_ylabel('Pares — não réplicas independentes')
    agreement = pd.read_parquet(root/'concordancia_ablacao.parquet')
    agreement = agreement.loc[(agreement.family == 'grid') & (agreement.scale_m == 50)
        & (agreement.scope == 'conditional_canopy') & (agreement.top_fraction == report['primary_top_fraction'])]
    plotted = False
    for features, orientation, label in [('I6_I7', 'Vplus', 'Altura + IQR, V+'), ('I6_I7', 'Vminus', 'Altura + IQR, V−'), ('I6_only', 'height_only', 'Somente altura')]:
        curve = agreement.loc[(agreement.features == features) & (agreement.orientation == orientation)].sort_values('vertical_weight')
        finite = curve.loc[curve.spearman_rho.notna()]
        if len(finite):
            axes[2].plot(finite.vertical_weight, finite.spearman_rho, marker='o', label=label); plotted = True
    if plotted: axes[2].legend(fontsize=7)
    else: axes[2].text(.5, .5, 'Spearman indisponível:\namostra pequena ou variável constante', ha='center', va='center', transform=axes[2].transAxes, fontsize=9)
    axes[2].set_xlim(-.025, .775); axes[2].set_ylim(-.05, 1.05)
    axes[2].set_xlabel('Peso vertical predefinido'); axes[2].set_ylabel('Spearman em relação a A')
    axes[2].set_title('Ablações de pesos/orientação', fontsize=10)
    fig.suptitle(f"{report['source_indicators']['corridor_id']} — descritores e escolhas do protocolo\nSem alvo externo, p-valores ou conclusão de benefício ecológico; duplicar I6 reproduz altura isolada", fontsize=11)
    fig.savefig(args.output_dir/f"altura_pesos_50m_{report['case']}.png", dpi=170)
    plt.close(fig)


if __name__ == '__main__': main()
