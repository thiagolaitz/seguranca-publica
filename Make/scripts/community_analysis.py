#!/usr/bin/env python3
"""
Analisa comunidades em um grafo construído a partir do JSONL de distâncias.

Fluxo:
1. Constrói o grafo usando o mesmo threshold do create_graph.py
2. Executa um algoritmo de detecção de comunidades (greedy, label propagation, etc.)
3. Calcula métricas de qualidade (modularidade, cobertura, etc.) e estatísticas de tamanho
4. Opcionalmente salva os resultados em JSON e gera um gráfico da distribuição de tamanhos
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from networkx.algorithms import community as nx_comm

try:
    # When running as `python scripts/community_analysis.py`, the script directory is on sys.path
    from create_graph import build_graph_from_jsonl, summarize_graph
except ModuleNotFoundError:
    # Fallback when executed from elsewhere
    sys.path.append(str(Path(__file__).parent))
    from create_graph import build_graph_from_jsonl, summarize_graph


ALGORITHMS = ("greedy", "label_prop", "asyn_label_prop", "kclique")


def detect_communities(
    graph: nx.Graph,
    algorithm: str,
    k_clique: int | None = None,
) -> List[Set[str]]:
    """Run the requested community detection algorithm."""
    if graph.number_of_nodes() == 0:
        return []

    if algorithm == "greedy":
        communities = nx_comm.greedy_modularity_communities(graph)
    elif algorithm == "label_prop":
        communities = list(nx_comm.label_propagation_communities(graph))
    elif algorithm == "asyn_label_prop":
        communities = list(nx_comm.asyn_lpa_communities(graph))
    elif algorithm == "kclique":
        if not k_clique or k_clique < 3:
            raise ValueError("k-clique requer --k-clique >= 3.")
        communities = list(nx_comm.k_clique_communities(graph, k_clique))
    else:
        raise ValueError(f"Algoritmo desconhecido: {algorithm}")

    # Convert frozensets to normal sets for later manipulation/JSON
    return [set(c) for c in communities]


def filter_communities(communities: Iterable[Set[str]], min_size: int) -> List[Set[str]]:
    """Drop very small communities if requested."""
    return [c for c in communities if len(c) >= min_size]


def compute_metrics(graph: nx.Graph, communities: Sequence[Set[str]]) -> Dict:
    """Return size statistics and quality metrics."""
    if not communities:
        return {
            "num_communities": 0,
            "largest_community": 0,
            "smallest_community": 0,
            "avg_community_size": 0,
            "coverage": 0,
            "performance": 0,
            "modularity": 0,
            "fraction_in_largest": 0,
        }

    sizes = sorted([len(c) for c in communities], reverse=True)
    num_nodes = graph.number_of_nodes() or 1

    metrics = {
        "num_communities": len(communities),
        "largest_community": sizes[0],
        "smallest_community": sizes[-1],
        "avg_community_size": float(np.mean(sizes)),
        "median_community_size": float(np.median(sizes)),
        "fraction_in_largest": sizes[0] / num_nodes,
        "coverage": nx_comm.coverage(graph, communities),
        "performance": nx_comm.performance(graph, communities),
    }

    try:
        metrics["modularity"] = nx_comm.modularity(graph, communities)
    except (ZeroDivisionError, ValueError):
        metrics["modularity"] = None

    metrics["community_sizes"] = sizes
    return metrics


def identify_bridge_nodes(
    graph: nx.Graph,
    communities: Sequence[Set[str]],
    top_k: int = 5,
    verbose: bool = False,
    sample_size: int | None = None,
    seed: int | None = None,
) -> List[Dict]:
    """
    Identifica nós que servem de ponte entre comunidades.

    Critério: nó com vizinhos em outras comunidades, ranqueado por uma
    pontuação que combina betweenness centrality e fração de vizinhos externos.
    """
    if not communities or top_k <= 0 or graph.number_of_nodes() == 0:
        return []

    node_to_comm = {}
    for idx, comm in enumerate(communities):
        for node in comm:
            node_to_comm.setdefault(node, idx)

    use_approx = sample_size is not None and sample_size > 0
    if verbose and graph.number_of_nodes() > 1:
        if use_approx:
            print(
                f"Estimando betweenness centrality (amostra k={sample_size}, seed={seed}) "
                f"para {graph.number_of_nodes()} nós..."
            )
        else:
            print(f"Calculando betweenness centrality para {graph.number_of_nodes()} nós (pode demorar)...")

    betweenness: Dict[str, float] = {}
    if graph.number_of_nodes() > 1:
        if use_approx:
            k = min(sample_size, graph.number_of_nodes())
            betweenness = nx.betweenness_centrality(graph, k=k, normalized=True, seed=seed)
        else:
            betweenness = nx.betweenness_centrality(graph, normalized=True)

    if verbose and betweenness:
        print("Betweenness centrality concluída.")
    bridge_nodes = []

    for node in graph.nodes():
        comm_idx = node_to_comm.get(node)
        if comm_idx is None:
            continue

        total_degree = graph.degree(node)
        if total_degree == 0:
            continue

        external_degree = 0
        neighbor_comms = set()
        for nbr in graph.neighbors(node):
            nbr_comm = node_to_comm.get(nbr)
            if nbr_comm is None or nbr_comm == comm_idx:
                continue
            external_degree += 1
            neighbor_comms.add(nbr_comm)

        if external_degree == 0:
            continue

        external_fraction = external_degree / total_degree if total_degree else 0.0
        betweenness_score = betweenness.get(node, 0.0)
        bridge_score = betweenness_score * external_fraction

        bridge_nodes.append(
            {
                "node": node,
                "community": comm_idx + 1,
                "neighboring_communities": sorted({c + 1 for c in neighbor_comms}),
                "external_degree": external_degree,
                "total_degree": total_degree,
                "external_fraction": external_fraction,
                "betweenness": betweenness_score,
                "bridge_score": bridge_score,
            }
        )

    bridge_nodes.sort(key=lambda b: (b["bridge_score"], b["external_degree"], b["betweenness"]), reverse=True)
    return bridge_nodes[:top_k]


def save_results(output_path: Path, payload: Dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"Resultados salvos em: {output_path}")


def plot_community_sizes(
    sizes: Sequence[int],
    output_path: Path,
    top_n: int | None = None,
    show: bool = False,
) -> None:
    if not sizes:
        print("Nenhuma comunidade para plotar.")
        return

    if top_n:
        sizes = sizes[:top_n]

    plt.figure(figsize=(10, 6))
    x = np.arange(len(sizes))
    plt.bar(x, sizes, color="#5DADE2", edgecolor="black", linewidth=0.6)
    plt.xlabel("Comunidade (ordenada por tamanho)")
    plt.ylabel("Número de nós")
    plt.title("Tamanho das Comunidades (Top {})".format(len(sizes)))
    plt.grid(True, axis="y", alpha=0.2)
    plt.xticks(x, [f"C{i+1}" for i in x])
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()
    print(f"Gráfico de tamanhos salvo em: {output_path}")


def build_report(
    graph_stats: Dict,
    metrics: Dict,
    communities: Sequence[Set[str]],
    top_n: int,
    bridge_nodes: Sequence[Dict],
) -> Dict:
    """Combine base stats + community metrics into a single dict."""
    sorted_communities = sorted(communities, key=lambda c: len(c), reverse=True)
    top_communities = [
        {
            "rank": idx + 1,
            "size": len(comm),
            "fraction_of_nodes": len(comm) / graph_stats["nodes"] if graph_stats["nodes"] else 0,
            "nodes": sorted(comm),
        }
        for idx, comm in enumerate(sorted_communities[:top_n])
    ]

    return {
        "graph": graph_stats,
        "community_metrics": metrics,
        "top_communities": top_communities,
        "total_communities": len(communities),
        "bridge_nodes": bridge_nodes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analisa comunidades em um grafo construído de distâncias JSONL.")
    parser.add_argument("--distances", type=Path, required=True, help="Arquivo JSONL de distâncias.")
    parser.add_argument("--threshold", type=float, required=True, help="Threshold em km para construir o grafo.")
    parser.add_argument(
        "--algorithm",
        choices=ALGORITHMS,
        default="greedy",
        help="Algoritmo de comunidades (default: greedy).",
    )
    parser.add_argument("--k-clique", type=int, help="Valor de k para o algoritmo k-clique (quando --algorithm=kclique).")
    parser.add_argument("--min-size", type=int, default=3, help="Descarta comunidades menores que esse tamanho (default: 3).")
    parser.add_argument("--top-n", type=int, default=15, help="Quantas comunidades listar no resumo (default: 15).")
    parser.add_argument(
        "--bridges-top",
        type=int,
        default=20,
        help="Quantidade de nós ponte (entre comunidades) a exibir (default: 20).",
    )
    parser.add_argument(
        "--bridges-sample",
        type=int,
        default=0,
        help="Usa amostragem de k fontes para betweenness (0 = cálculo exato).",
    )
    parser.add_argument(
        "--bridges-seed",
        type=int,
        help="Seed opcional para a amostragem de betweenness (se --bridges-sample > 0).",
    )
    parser.add_argument("--output-json", type=Path, help="Arquivo opcional para salvar os resultados em JSON.")
    parser.add_argument(
        "--plot-path",
        type=Path,
        help="Se informado, salva um gráfico com os tamanhos das comunidades.",
    )
    parser.add_argument("--show-plot", action="store_true", help="Exibe o gráfico além de salvar o arquivo.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    graph = build_graph_from_jsonl(args.distances, args.threshold)
    graph_stats = summarize_graph(graph)

    communities = detect_communities(graph, args.algorithm, k_clique=args.k_clique)
    communities = filter_communities(communities, min_size=max(1, args.min_size))

    metrics = compute_metrics(graph, communities)
    sample = args.bridges_sample if args.bridges_sample > 0 else None
    bridge_nodes = identify_bridge_nodes(
        graph,
        communities,
        top_k=args.bridges_top,
        verbose=True,
        sample_size=sample,
        seed=args.bridges_seed,
    )
    report = build_report(
        graph_stats,
        metrics,
        communities,
        top_n=args.top_n,
        bridge_nodes=bridge_nodes,
    )

    print("\n=== Comunidades Detectadas ===")
    print(f"Algoritmo: {args.algorithm}")
    print(f"Total de comunidades: {report['total_communities']}")
    print(f"Maior comunidade: {metrics['largest_community']}")
    print(f"Modularidade: {metrics.get('modularity')}")

    for community in report["top_communities"]:
        print(
            f"[#{community['rank']}] tamanho={community['size']} "
            f"({community['fraction_of_nodes']*100:.1f}% dos nós)"
        )

    if bridge_nodes:
        print("\n=== Pontes entre Comunidades ===")
        for idx, bridge in enumerate(bridge_nodes, start=1):
            neighbors = ", ".join(f"C{c}" for c in bridge["neighboring_communities"]) or "-"
            print(
                f"[#{idx}] nó={bridge['node']} C{bridge['community']} "
                f"ext={bridge['external_degree']}/{bridge['total_degree']} "
                f"frac_ext={bridge['external_fraction']:.2f} "
                f"betweenness={bridge['betweenness']:.4f} "
                f"liga={neighbors}"
            )
    else:
        print("\nNenhuma ponte entre comunidades identificada (grau externo = 0).")

    if args.output_json:
        save_results(args.output_json, report)

    if args.plot_path and metrics.get("community_sizes"):
        plot_community_sizes(
            metrics["community_sizes"],
            args.plot_path,
            top_n=args.top_n,
            show=args.show_plot,
        )


if __name__ == "__main__":
    main()
