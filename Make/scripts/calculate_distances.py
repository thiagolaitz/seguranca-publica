#!/usr/bin/env python3
"""
Calcula distâncias pareadas entre todos os pontos do dataset e salva em JSONL.

Este script é a primeira etapa do pipeline:
1. Lê dados brutos (Excel ou CSV)
2. Limpa coordenadas inválidas
3. Calcula as distâncias usando Haversine em paralelo
4. Escreve um JSONL onde cada linha contém as distâncias de um nó para os demais
"""

import argparse
import json
import queue
import threading
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from haversine import Unit, haversine
from tqdm import tqdm


def load_dataframe(input_path: Path, sheet_name: str = None, max_rows: int = None) -> pd.DataFrame:
    """Load the input dataset, supporting Excel and CSV formats."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        sheet_to_read = 0 if sheet_name is None else sheet_name
        df = pd.read_excel(input_path, sheet_name=sheet_to_read, nrows=max_rows)
    elif input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path, nrows=max_rows)
    else:
        raise ValueError(f"Unsupported file extension: {input_path.suffix}")

    return df


def sanitize_dataframe(
    df: pd.DataFrame,
    id_col: str,
    lat_col: str,
    lon_col: str,
) -> pd.DataFrame:
    """Keep only valid coordinates and ensure numeric dtype."""
    missing_cols = {c for c in (id_col, lat_col, lon_col) if c not in df.columns}
    if missing_cols:
        raise ValueError(f"Missing columns in dataset: {', '.join(sorted(missing_cols))}")

    df = df.dropna(subset=[id_col, lat_col, lon_col]).copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    df = df[(df[lat_col] != 0) & (df[lon_col] != 0)]
    df = df.reset_index(drop=True)
    return df


def calculate_node_distances(
    args: Tuple[int, Dict, List[Dict], str, str, str]
) -> Dict[str, Dict[str, float]]:
    """Worker function evaluating the distance from one node to every node with a higher index."""
    idx, node_data, all_nodes, id_col, lat_col, lon_col = args
    node1_id = str(node_data[id_col])
    point1 = (node_data[lat_col], node_data[lon_col])

    results: Dict[str, Dict[str, float]] = defaultdict(dict)
    for j in range(idx + 1, len(all_nodes)):
        node2 = all_nodes[j]
        node2_id = str(node2[id_col])
        point2 = (node2[lat_col], node2[lon_col])
        distance = haversine(point1, point2, unit=Unit.KILOMETERS)
        results[node1_id][node2_id] = float(distance)

    return results


def write_results_worker(result_queue: queue.Queue, output_path: Path, total_nodes: int) -> None:
    """Background thread that writes JSONL lines as soon as workers finish."""
    written = 0
    with output_path.open("w") as f_out:
        while written < total_nodes:
            try:
                result = result_queue.get(timeout=60)
            except queue.Empty:
                print("Warning: timeout while waiting for results; stopping writer thread.")
                break

            if result is not None:
                f_out.write(json.dumps(result) + "\n")
                f_out.flush()
                written += 1
            result_queue.task_done()


def calculate_all_distances(
    df: pd.DataFrame,
    output_path: Path,
    id_col: str,
    lat_col: str,
    lon_col: str,
    n_processes: int = None,
) -> None:
    """Dispatch the multiprocessing jobs and orchestrate writing to disk."""
    df = sanitize_dataframe(df, id_col=id_col, lat_col=lat_col, lon_col=lon_col)
    if df.empty:
        raise ValueError("No valid rows left after cleaning latitude/longitude columns.")

    total_pairs = len(df) * (len(df) - 1) // 2
    if n_processes is None:
        n_processes = cpu_count()

    print(f"Calculating pairwise distances for {len(df)} nodes ({total_pairs} pairs)")
    print(f"Using {n_processes} worker processes")

    all_nodes = df.to_dict("records")
    node_args: Iterable[Tuple[int, Dict, List[Dict], str, str, str]] = [
        (i, all_nodes[i], all_nodes, id_col, lat_col, lon_col) for i in range(len(all_nodes))
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_queue: queue.Queue = queue.Queue(maxsize=2 * n_processes)
    writer_thread = threading.Thread(
        target=write_results_worker, args=(result_queue, output_path, len(all_nodes)), daemon=True
    )
    writer_thread.start()

    with Pool(processes=n_processes) as pool:
        for result in tqdm(
            pool.imap(calculate_node_distances, node_args),
            total=len(all_nodes),
            desc="Processing nodes",
        ):
            result_queue.put(result)

    writer_thread.join()
    print(f"Distances saved to {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calcula distâncias pairwise entre registros e salva em JSONL."
    )
    parser.add_argument("--input", type=Path, required=True, help="Arquivo de entrada (Excel ou CSV).")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/distances.jsonl"),
        help="Arquivo JSONL de saída (default: build/distances.jsonl).",
    )
    parser.add_argument("--sheet-name", help="Nome da planilha (quando input for Excel). Default: primeira planilha.")
    parser.add_argument("--id-col", default="NUM_BO", help="Coluna com o identificador único (default: NUM_BO).")
    parser.add_argument("--lat-col", default="LATITUDE", help="Coluna de latitude (default: LATITUDE).")
    parser.add_argument("--lon-col", default="LONGITUDE", help="Coluna de longitude (default: LONGITUDE).")
    parser.add_argument(
        "--processes",
        type=int,
        help="Número de processos paralelos (default: cpu_count).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        help="Opcional: limita a quantidade de linhas carregadas (útil para testes rápidos).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    df = load_dataframe(args.input, sheet_name=args.sheet_name, max_rows=args.max_rows)
    print(f"Loaded {len(df)} rows from {args.input}")

    calculate_all_distances(
        df=df,
        output_path=args.output,
        id_col=args.id_col,
        lat_col=args.lat_col,
        lon_col=args.lon_col,
        n_processes=args.processes,
    )


if __name__ == "__main__":
    main()
