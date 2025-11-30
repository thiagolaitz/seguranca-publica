#!/usr/bin/env python3
"""
Gera visualizações a partir de graph_analysis_results.json.
"""

import argparse
import json
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import seaborn as sns

plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


def load_results(results_file: Path) -> List[dict]:
    if not results_file.exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    with results_file.open("r") as f:
        data = json.load(f)
    results = [r for r in data.get("results", []) if "error" not in r]
    if not results:
        raise ValueError("No valid results found in file.")
    return results


def plot_average_degree_vs_threshold(results, output_path: Path, show: bool) -> None:
    thresholds = [r["threshold_km"] for r in results]
    avg_degrees = [r["average_degree"] for r in results]

    plt.figure(figsize=(12, 8))
    plt.plot(
        thresholds,
        avg_degrees,
        "o-",
        linewidth=2.5,
        markersize=8,
        color="#2E86AB",
        markerfacecolor="#A23B72",
        markeredgecolor="white",
        markeredgewidth=2,
        label="Grau Médio",
    )
    plt.grid(True, alpha=0.3, linestyle="--")
    plt.xlabel("Threshold (km)", fontsize=14, fontweight="bold")
    plt.ylabel("Grau Médio", fontsize=14, fontweight="bold")
    plt.title("Evolução do Grau Médio vs Threshold", fontsize=16, fontweight="bold", pad=20)

    for x, y in zip(thresholds, avg_degrees):
        plt.annotate(
            f"{y:.0f}",
            (x, y),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
        )

    stats_text = f"""Estatísticas:
Min: {min(avg_degrees):.1f}
Max: {max(avg_degrees):.1f}
Variação: {max(avg_degrees) - min(avg_degrees):.1f}
Pontos: {len(results)}"""
    plt.text(
        0.02,
        0.98,
        stats_text,
        transform=plt.gca().transAxes,
        verticalalignment="top",
        fontsize=11,
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.8),
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close()


def plot_multiple_metrics(results, output_path: Path, show: bool) -> None:
    thresholds = [r["threshold_km"] for r in results]
    avg_degrees = [r["average_degree"] for r in results]
    edges = [r["edges"] for r in results]
    components = [r["connected_components"] for r in results]
    largest_component = [r["largest_component_size"] for r in results]

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

    ax1.plot(thresholds, avg_degrees, "o-", linewidth=2, markersize=6, color="#2E86AB")
    ax1.set_title("Grau Médio vs Threshold", fontweight="bold")
    ax1.set_xlabel("Threshold (km)")
    ax1.set_ylabel("Grau Médio")
    ax1.grid(True, alpha=0.3)

    ax2.plot(thresholds, edges, "o-", linewidth=2, markersize=6, color="#A23B72")
    ax2.set_title("Arestas vs Threshold", fontweight="bold")
    ax2.set_xlabel("Threshold (km)")
    ax2.set_ylabel("Número de Arestas")
    ax2.grid(True, alpha=0.3)
    ax2.ticklabel_format(style="scientific", axis="y", scilimits=(0, 0))

    ax3.plot(thresholds, components, "o-", linewidth=2, markersize=6, color="#F18F01")
    ax3.set_title("Componentes Conectados", fontweight="bold")
    ax3.set_xlabel("Threshold (km)")
    ax3.set_ylabel("Número de Componentes")
    ax3.grid(True, alpha=0.3)
    ax3.set_yscale("log")

    ax4.plot(thresholds, largest_component, "o-", linewidth=2, markersize=6, color="#C73E1D")
    ax4.set_title("Maior Componente vs Threshold", fontweight="bold")
    ax4.set_xlabel("Threshold (km)")
    ax4.set_ylabel("Tamanho do Maior Componente")
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(fig)


def plot_connectivity_analysis(results, output_path: Path, show: bool) -> None:
    thresholds = [r["threshold_km"] for r in results]
    components = [r["connected_components"] for r in results]
    largest_component = [r["largest_component_size"] for r in results]
    total_nodes = results[0]["nodes"]
    largest_pct = [(size / total_nodes) * 100 for size in largest_component]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    ax1.semilogy(
        thresholds,
        components,
        "o-",
        linewidth=2.5,
        markersize=8,
        color="#E63946",
        markerfacecolor="#F77F00",
        markeredgecolor="white",
        markeredgewidth=2,
    )
    ax1.set_title("Componentes Conectados", fontweight="bold", fontsize=14)
    ax1.set_xlabel("Threshold (km)")
    ax1.set_ylabel("Componentes (log)")
    ax1.grid(True, alpha=0.3)

    for x, y in zip(thresholds, components):
        ax1.annotate(
            f"{y}",
            (x, y),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8),
        )

    ax2.plot(
        thresholds,
        largest_pct,
        "o-",
        linewidth=2.5,
        markersize=8,
        color="#2A9D8F",
        markerfacecolor="#264653",
        markeredgecolor="white",
        markeredgewidth=2,
    )
    ax2.set_title("Maior Componente (% de nós)", fontweight="bold", fontsize=14)
    ax2.set_xlabel("Threshold (km)")
    ax2.set_ylabel("Porcentagem (%)")
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=90, color="red", linestyle="--", alpha=0.7, label="90% conectado")
    ax2.legend()

    for x, y in zip(thresholds, largest_pct):
        ax2.annotate(
            f"{y:.1f}%",
            (x, y),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="lightgreen", alpha=0.8),
        )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera gráficos para as métricas de grafos.")
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("build/graph_analysis_results.json"),
        help="Arquivo JSON com resultados (default: build/graph_analysis_results.json).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("plots"),
        help="Diretório onde os gráficos serão salvos (default: plots/).",
    )
    parser.add_argument("--average-degree", action="store_true", help="Gera gráfico de grau médio vs threshold.")
    parser.add_argument("--multi-metrics", action="store_true", help="Gera painel com múltiplas métricas.")
    parser.add_argument("--connectivity", action="store_true", help="Gera gráfico de conectividade.")
    parser.add_argument("--show", action="store_true", help="Mostra os gráficos na tela além de salvar os arquivos.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.results = args.results.resolve()
    args.output_dir = args.output_dir.resolve()

    results = load_results(args.results)
    print(f"Loaded {len(results)} valid thresholds from {args.results}")

    # Caso nenhum gráfico específico tenha sido pedido, gera todos.
    generate_all = not any([args.average_degree, args.multi_metrics, args.connectivity])

    if args.average_degree or generate_all:
        output_path = args.output_dir / "plot_average_degree_vs_threshold.png"
        print(f"Creating average degree plot -> {output_path}")
        plot_average_degree_vs_threshold(results, output_path, show=args.show)

    if args.multi_metrics or generate_all:
        output_path = args.output_dir / "plot_multiple_metrics.png"
        print(f"Creating multi-metric plot -> {output_path}")
        plot_multiple_metrics(results, output_path, show=args.show)

    if args.connectivity or generate_all:
        output_path = args.output_dir / "plot_connectivity_analysis.png"
        print(f"Creating connectivity plot -> {output_path}")
        plot_connectivity_analysis(results, output_path, show=args.show)

    print("Plots generated successfully.")


if __name__ == "__main__":
    main()
