#!/usr/bin/env python3
"""
Construção e análise de grafos a partir de distâncias pairwise em JSONL.

O script:
1. Carrega um JSONL produzido por calculate_distances.py
2. Cria um grafo não direcionado usando um limiar (threshold) máximo
3. Opcionalmente gera gráficos de distribuição de distâncias e de graus
4. Salva um resumo em JSON para alimentar etapas seguintes do pipeline
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from tqdm import tqdm


def build_graph_from_jsonl(jsonl_path: Path, threshold_km: float) -> nx.Graph:
    """Create an undirected graph keeping only edges shorter than the threshold."""
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Distances file not found: {jsonl_path}")

    graph = nx.Graph()
    with jsonl_path.open("r") as handle:
        for line in tqdm(handle, desc="Building graph"):
            row = json.loads(line)
            for u, neighbors in row.items():
                if u not in graph:
                    graph.add_node(u)

                for v, dist in neighbors.items():
                    if dist < threshold_km:
                        graph.add_edge(u, v, distance_km=float(dist))
                    else:
                        # garante que o nó exista mesmo se não possuir arestas curtas
                        if v not in graph:
                            graph.add_node(v)
    return graph


def summarize_graph(graph: nx.Graph) -> Dict[str, float]:
    """Return the main statistics required by the pipeline."""
    n = graph.number_of_nodes()
    m = graph.number_of_edges()
    avg_deg = 2.0 * m / n if n else 0.0

    components = list(nx.connected_components(graph))
    largest_cc_size = len(max(components, key=len)) if components else 0
    degrees = dict(graph.degree())
    max_deg_node = max(degrees, key=degrees.get) if degrees else None

    return {
        "nodes": n,
        "edges": m,
        "average_degree": round(avg_deg, 4),
        "max_degree": degrees[max_deg_node] if max_deg_node else 0,
        "max_degree_node": max_deg_node,
        "connected_components": len(components),
        "largest_component_size": largest_cc_size,
    }


def print_graph_summary(stats: Dict[str, float]) -> None:
    """Pretty-print the statistics to stdout."""
    print("\n=== Graph Summary ===")
    for key, value in stats.items():
        print(f"{key.replace('_', ' ').title()}: {value}")


def plot_distance_distribution(
    jsonl_path: Path,
    output_path: Path,
    threshold_km: float = None,
    bins: int = 50,
    show: bool = False,
) -> Path:
    """Plot histogram of every pairwise distance in the JSONL."""
    distances = []
    outlier_threshold = 1000  # km

    with jsonl_path.open("r") as handle:
        for line in tqdm(handle, desc="Collecting distances"):
            row = json.loads(line)
            for neighbors in row.values():
                for dist in neighbors.values():
                    if dist < outlier_threshold:
                        distances.append(float(dist))

    distances = np.array(distances)
    if distances.size == 0:
        raise ValueError("No distances available to plot.")

    print(f"Collected {len(distances)} distances | min={distances.min():.3f} km | max={distances.max():.3f} km")

    plt.figure(figsize=(12, 8))
    counts, _, _ = plt.hist(
        distances,
        bins=bins,
        alpha=0.7,
        color="skyblue",
        edgecolor="black",
        linewidth=0.5,
    )

    if threshold_km is not None:
        plt.axvline(
            x=threshold_km,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Threshold: {threshold_km} km",
        )
        below_threshold = np.sum(distances < threshold_km)
        percentage = (below_threshold / len(distances)) * 100
        plt.text(
            threshold_km + 0.5,
            max(counts) * 0.8,
            f"{percentage:.1f}% abaixo do threshold",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

    plt.axvline(
        x=distances.mean(),
        color="orange",
        linestyle="-",
        alpha=0.7,
        label=f"Média: {distances.mean():.2f} km",
    )
    plt.xlabel("Distância (km)")
    plt.ylabel("Frequência")
    plt.title("Distribuição de Distâncias")
    plt.legend()
    plt.grid(True, alpha=0.3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()
    return output_path


def plot_degree_distribution(
    graph: nx.Graph,
    output_path: Path,
    show: bool = False,
) -> Tuple[np.ndarray, Dict[int, float]]:
    """Plot both regular and log-log degree distributions."""
    degrees = [d for _, d in graph.degree()]
    if not degrees:
        raise ValueError("Graph has no nodes to plot degree distribution.")

    degree_counts = {}
    for d in degrees:
        degree_counts[d] = degree_counts.get(d, 0) + 1

    total_nodes = len(degrees)
    degree_probabilities = {k: v / total_nodes for k, v in degree_counts.items()}
    sorted_degrees = sorted(degree_probabilities.keys())
    probabilities = [degree_probabilities[d] for d in sorted_degrees]

    avg_degree = np.mean(degrees)
    max_degree = max(degrees)
    min_degree = min(degrees)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    ax1.bar(sorted_degrees, probabilities, alpha=0.7, color="lightblue", edgecolor="black", linewidth=0.5)
    ax1.set_xlabel("Degree k")
    ax1.set_ylabel("P(k)")
    ax1.set_title("Distribuição de Grau (escala normal)")
    ax1.grid(True, alpha=0.3)
    ax1.axvline(
        x=avg_degree,
        color="red",
        linestyle="--",
        linewidth=2,
        alpha=0.8,
        label=f"Média: {avg_degree:.2f}",
    )
    ax1.legend()

    nonzero_deg = [d for d, p in zip(sorted_degrees, probabilities) if p > 0]
    nonzero_prob = [p for p in probabilities if p > 0]

    if nonzero_deg and nonzero_prob:
        ax2.loglog(nonzero_deg, nonzero_prob, "o-", alpha=0.7, color="darkblue", markersize=4, linewidth=1.5)
        ax2.set_xlabel("Degree k (log)")
        ax2.set_ylabel("P(k) (log)")
        ax2.set_title("Distribuição de Grau (log-log)")
        ax2.grid(True, alpha=0.3)

    stats_text = f"""Nodes: {graph.number_of_nodes()}
Edges: {graph.number_of_edges()}
Min degree: {min_degree}
Max degree: {max_degree}
Avg degree: {avg_degree:.3f}"""
    fig.text(
        0.02,
        0.98,
        stats_text,
        transform=fig.transFigure,
        verticalalignment="top",
        fontsize=10,
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="lightgray", alpha=0.8),
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return np.array(degrees), degree_probabilities


def save_summary(stats: Dict[str, float], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(stats, f, indent=2)
    print(f"Graph summary saved to {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Constrói um grafo a partir de distâncias JSONL e gera estatísticas/plots."
    )
    parser.add_argument("--distances", type=Path, required=True, help="Arquivo JSONL com as distâncias.")
    parser.add_argument("--threshold", type=float, required=True, help="Threshold em km para adicionar arestas.")
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=Path("plots"),
        help="Diretório base para salvar plots (default: plots/).",
    )
    parser.add_argument("--summary-json", type=Path, help="Opcional: caminho para salvar estatísticas em JSON.")
    parser.add_argument("--plot-distances", action="store_true", help="Gera histograma das distâncias.")
    parser.add_argument("--plot-degree-dist", action="store_true", help="Gera plot da distribuição de graus.")
    parser.add_argument("--plot-bins", type=int, default=50, help="Bins do histograma de distâncias (default: 50).")
    parser.add_argument(
        "--show-plots",
        action="store_true",
        help="Mostra os gráficos em vez de apenas salvar os arquivos.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    graph = build_graph_from_jsonl(args.distances, args.threshold)
    stats = summarize_graph(graph)
    stats["threshold_km"] = args.threshold
    print_graph_summary(stats)

    if args.summary_json:
        save_summary(stats, args.summary_json)

    plots_dir = args.plots_dir
    plots_dir.mkdir(parents=True, exist_ok=True)

    if args.plot_distances:
        dist_plot_path = plots_dir / f"distance_distribution_{args.distances.stem}.png"
        plot_distance_distribution(
            args.distances,
            dist_plot_path,
            threshold_km=args.threshold,
            bins=args.plot_bins,
            show=args.show_plots,
        )
        print(f"Distance distribution plot saved to {dist_plot_path}")

    if args.plot_degree_dist:
        degree_plot_path = plots_dir / f"degree_distribution_threshold{args.threshold:.2f}km.png"
        plot_degree_distribution(graph, degree_plot_path, show=args.show_plots)
        print(f"Degree distribution plot saved to {degree_plot_path}")


if __name__ == "__main__":
    main()
