#!/usr/bin/env python3
"""
Executa create_graph.py para vários thresholds e agrega as métricas em JSON.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

from datetime import datetime


def generate_thresholds(args: argparse.Namespace) -> List[float]:
    """Return the list of thresholds provided explicitly or by range."""
    if args.thresholds:
        return [float(value.strip()) for value in args.thresholds.split(",")]

    thresholds = []
    current = args.min_threshold
    while current <= args.max_threshold + 1e-9:
        thresholds.append(round(current, 3))
        current += args.step
    return thresholds


def run_threshold(
    script_path: Path,
    distances_path: Path,
    threshold: float,
    summary_path: Path,
    plots_dir: Path,
    plot_degree: bool,
    plot_distances: bool,
    show_plots: bool,
    timeout: int,
) -> Dict:
    """Invoke create_graph.py for a specific threshold and return its statistics."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    python_exec = sys.executable if sys.executable else "python3"
    cmd = [
        python_exec,
        str(script_path),
        "--distances",
        str(distances_path),
        "--threshold",
        str(threshold),
        "--summary-json",
        str(summary_path),
        "--plots-dir",
        str(plots_dir),
    ]
    if plot_degree:
        cmd.append("--plot-degree-dist")
    if plot_distances:
        cmd.append("--plot-distances")
    if show_plots:
        cmd.append("--show-plots")

    print(f"Running threshold {threshold} km...")
    start = time.time()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        msg = f"Timeout após {timeout}s"
        print(f"⚠️  Threshold {threshold} km atingiu timeout de {timeout}s")
        return {"threshold_km": threshold, "error": msg, "execution_time": elapsed}

    elapsed = time.time() - start
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        return {"threshold_km": threshold, "error": result.stderr.strip(), "execution_time": elapsed}

    if not summary_path.exists():
        return {"threshold_km": threshold, "error": "summary file missing", "execution_time": elapsed}

    with summary_path.open("r") as f:
        stats = json.load(f)

    stats["threshold_km"] = threshold
    stats["execution_time"] = elapsed
    print(f"✓ Threshold {threshold} km -> nodes={stats.get('nodes')}, edges={stats.get('edges')} ({elapsed:.2f}s)")
    return stats


def write_results(output_path: Path, metadata: Dict, results: List[Dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "results": results}
    with output_path.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"Partial results stored at {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa create_graph.py para múltiplos thresholds.")
    parser.add_argument("--distances", type=Path, required=True, help="JSONL com distâncias.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/graph_analysis_results.json"),
        help="Arquivo JSON para salvar resultados agregados.",
    )
    parser.add_argument(
        "--create-graph-script",
        type=Path,
        default=Path("scripts/create_graph.py"),
        help="Caminho para create_graph.py (default: scripts/create_graph.py).",
    )
    parser.add_argument("--thresholds", help="Lista explícita: ex. '0.5,1.0,2.5'.")
    parser.add_argument("--min-threshold", type=float, default=0.5, help="Threshold mínimo (default: 0.5).")
    parser.add_argument("--max-threshold", type=float, default=5.0, help="Threshold máximo (default: 5.0).")
    parser.add_argument("--step", type=float, default=0.5, help="Incremento entre thresholds (default: 0.5).")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout por execução em segundos (default: 600).")
    parser.add_argument("--plots-dir", type=Path, default=Path("plots"), help="Onde salvar os plots (se habilitados).")
    parser.add_argument("--plot-degree-dist", action="store_true", help="Gera plot de grau por threshold.")
    parser.add_argument("--plot-distance-dist", action="store_true", help="Gera histograma das distâncias.")
    parser.add_argument("--show-plots", action="store_true", help="Abre as figuras interativamente.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.distances = args.distances.resolve()
    args.create_graph_script = args.create_graph_script.resolve()
    args.output = args.output.resolve()
    args.plots_dir = args.plots_dir.resolve()

    thresholds = generate_thresholds(args)
    if not thresholds:
        raise ValueError("No thresholds provided.")

    start_wall = time.time()
    metadata = {
        "distances_file": str(args.distances.resolve()),
        "total_thresholds": len(thresholds),
        "create_graph_script": str(args.create_graph_script.resolve()),
        "started_at": datetime.now().isoformat(),
    }

    results: List[Dict] = []
    summaries_dir = args.output.parent / "summaries"
    for idx, threshold in enumerate(thresholds, 1):
        summary_path = summaries_dir / f"summary_threshold_{threshold:.2f}.json"
        stats = run_threshold(
            script_path=args.create_graph_script,
            distances_path=args.distances,
            threshold=threshold,
            summary_path=summary_path,
            plots_dir=args.plots_dir,
            plot_degree=args.plot_degree_dist,
            plot_distances=args.plot_distance_dist,
            show_plots=args.show_plots,
            timeout=args.timeout,
        )
        results.append(stats)

        metadata.update(
            {
                "completed": idx,
                "last_threshold": threshold,
                "total_execution_time": time.time() - start_wall,
            }
        )
        write_results(args.output, metadata, results)

    metadata["finished_at"] = datetime.now().isoformat()
    metadata["total_execution_time"] = time.time() - start_wall
    write_results(args.output, metadata, results)
    print("Analysis finished.")


if __name__ == "__main__":
    main()
