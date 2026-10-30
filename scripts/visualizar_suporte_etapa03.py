"""Visão geral do suporte XY já auditado; não recalcula nuvens ou indicadores."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sbsr_mpl_etapa03")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.plot import plotting_extent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="qc_insumos.json da execução")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    products = {Path(p).name: Path(p) for p in report["products"]}
    measurement = gpd.read_file(products["dominios.gpkg"], layer="medicao")
    tiles = gpd.read_file(products["dominios.gpkg"], layer="quadriculas")
    colors = ["#2b806b", "#d65b50", "#dedbd5", "#ffffff"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 8), constrained_layout=True)
    for ax, product in zip(axes, ["MDT", "MDS"]):
        with rasterio.open(products[f"{product}_suporte_xy.tif"]) as ds:
            values = ds.read(1)
            codes = np.full(values.shape, 3, dtype=np.uint8)
            for label in [1, 2, 3]:
                codes[values == label] = label - 1
            extent = plotting_extent(ds)
            ax.imshow(codes, cmap=ListedColormap(colors), vmin=0, vmax=3,
                      extent=extent, interpolation="nearest")
            measurement.boundary.plot(ax=ax, color="#1b1b1b", linewidth=0.7)
            tiles.boundary.plot(ax=ax, color="#84909c", linewidth=0.6, linestyle="--")
            ax.set_xlim(extent[:2])
            ax.set_ylim(extent[2:])
        stats = report["support"][product]["medicao"]
        percent = f"{100*stats['occupied_fraction']:.4f}".replace(".", ",")
        missing = f"{stats['no_return_cells']:,}".replace(",", ".")
        ax.set_title(f"{product}: {percent}% com retorno após QC\n"
                     f"{missing} células de medição sem retorno", fontsize=11)
        ax.set_xlabel("E (m)")
        ax.set_ylabel("N (m)")
        ax.ticklabel_format(useOffset=False, style="plain")
        ax.tick_params(labelsize=8, axis="x", labelrotation=30)
        ax.set_aspect("equal")
    domain = report["domain"]
    fig.suptitle(f"Suporte XY — {domain['corridor_id']} / {domain['case']}\n"
                 f"EPSG:{domain['epsg']} · célula {report['resolution_m']:g} m · linha preta: medição", fontsize=13)
    fig.legend(handles=[Patch(color=colors[0], label="Retorno após QC"),
                        Patch(color=colors[1], label="Somente excluídos"),
                        Patch(color=colors[2], label="Sem retorno"),
                        Patch(facecolor="white", edgecolor="#cccccc", label="Fora do contexto (NoData)")],
               loc="outside lower center", ncol=2, fontsize=9,
               title="Ocupação XY não é cobertura arbórea nem validação do terreno. Visão geral; consultar GeoTIFF.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
