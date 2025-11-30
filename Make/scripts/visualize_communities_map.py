#!/usr/bin/env python3
"""
Visualiza comunidades em um mapa interativo (Folium) usando as coordenadas do dataset.

O script:
- Lê o dataset bruto (Excel/CSV) para obter latitude/longitude por ID
- Reconstrói o grafo a partir do JSONL de distâncias e threshold escolhido
- Detecta comunidades (mesmos algoritmos de community_analysis.py)
- Cria uma camada por comunidade (Top-N) com marcadores coloridos
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import folium
import pandas as pd

from create_graph import build_graph_from_jsonl
from community_analysis import detect_communities, filter_communities, identify_bridge_nodes

COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]
SAFE_COLORS = [
    "#27ae60",
    "#2ecc71",
    "#1abc9c",
    "#16a085",
    "#52be80",
]


def load_dataframe(input_path: Path, sheet_name: str | None, max_rows: int | None) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        sheet_to_read = 0 if sheet_name is None else sheet_name
        df = pd.read_excel(input_path, sheet_name=sheet_to_read, nrows=max_rows)
    elif input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path, nrows=max_rows)
    else:
        raise ValueError(f"Unsupported extension: {input_path.suffix}")
    return df


def build_coordinate_lookup(
    df: pd.DataFrame,
    id_col: str,
    lat_col: str,
    lon_col: str,
) -> Dict[str, Tuple[float, float]]:
    for col in (id_col, lat_col, lon_col):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in dataset.")

    coords = df[[id_col, lat_col, lon_col]].copy()
    coords[lat_col] = pd.to_numeric(coords[lat_col], errors="coerce")
    coords[lon_col] = pd.to_numeric(coords[lon_col], errors="coerce")
    coords = coords.dropna(subset=[lat_col, lon_col])
    coords = coords[(coords[lat_col] != 0) & (coords[lon_col] != 0)]
    coords[id_col] = coords[id_col].astype(str)

    lookup = (
        coords.drop_duplicates(subset=[id_col])
        .set_index(id_col)[[lat_col, lon_col]]
        .to_dict(orient="index")
    )
    return {node: (float(data[lat_col]), float(data[lon_col])) for node, data in lookup.items()}


def create_map(center: Tuple[float, float], zoom_start: int, tiles: str) -> folium.Map:
    return folium.Map(location=center, zoom_start=zoom_start, tiles=tiles)


def add_community_markers(
    fmap: folium.Map,
    communities: Sequence[Sequence[str]],
    coord_lookup: Dict[str, Tuple[float, float]],
    marker_radius: int,
    colors: Sequence[str] | None = None,
) -> None:
    palette = colors or COLORS
    for idx, community in enumerate(communities):
        color = palette[idx % len(palette)]
        layer = folium.FeatureGroup(name=f"Comunidade #{idx + 1} (n={len(community)})")
        for node in community:
            coord = coord_lookup.get(node)
            if not coord:
                continue
            folium.CircleMarker(
                location=coord,
                radius=marker_radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=1,
                tooltip=f"Node: {node}",
            ).add_to(layer)
        layer.add_to(fmap)


def add_bridge_markers(
    fmap: folium.Map,
    bridge_nodes: Sequence[Dict],
    coord_lookup: Dict[str, Tuple[float, float]],
    marker_radius: int,
) -> None:
    """Destaca nós que funcionam como pontes entre comunidades."""
    if not bridge_nodes:
        return

    layer = folium.FeatureGroup(name="Pontes entre comunidades")
    for bridge in bridge_nodes:
        coord = coord_lookup.get(bridge["node"])
        if not coord:
            continue
        neighbors = ", ".join(f"C{c}" for c in bridge["neighboring_communities"]) or "-"
        tooltip = (
            f"Ponte: {bridge['node']} (C{bridge['community']}) | "
            f"ext: {bridge['external_degree']}/{bridge['total_degree']} | "
            f"liga: {neighbors}"
        )
        folium.CircleMarker(
            location=coord,
            radius=marker_radius + 2,
            color="#000000",
            fill=True,
            fill_color="#f1c40f",
            fill_opacity=0.9,
            weight=2,
            tooltip=tooltip,
        ).add_to(layer)

    layer.add_to(fmap)


def add_neighborhood_boundaries(
    fmap: folium.Map,
    geojson_path: Path,
    layer_name: str = "Regiões",
) -> None:
    """Adiciona bordas de bairros/regiões (GeoJSON) ao mapa."""
    if not geojson_path.exists():
        raise FileNotFoundError(f"Arquivo GeoJSON não encontrado: {geojson_path}")

    with geojson_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    folium.GeoJson(
        data,
        name=layer_name,
        style_function=lambda _: {"color": "#444", "weight": 1.5, "fillOpacity": 0.0},
        highlight_function=lambda _: {"color": "#000", "weight": 2},
    ).add_to(fmap)


def extract_top_communities(
    communities: Sequence[Sequence[str]],
    coord_lookup: Dict[str, Tuple[float, float]],
    top_n: int,
) -> List[List[str]]:
    filtered = [sorted(list(c)) for c in communities if any(node in coord_lookup for node in c)]
    filtered.sort(key=len, reverse=True)
    return filtered[:top_n]


def extract_smallest_communities(
    communities: Sequence[Sequence[str]],
    coord_lookup: Dict[str, Tuple[float, float]],
    top_n: int,
    min_size: int,
) -> List[List[str]]:
    filtered = [
        sorted(list(c))
        for c in communities
        if len(c) >= min_size and any(node in coord_lookup for node in c)
    ]
    filtered.sort(key=len)
    return filtered[:top_n]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plota comunidades detectadas em um mapa interativo.")
    parser.add_argument("--distances", type=Path, required=True, help="Arquivo JSONL com distâncias.")
    parser.add_argument("--threshold", type=float, required=True, help="Threshold em km para construir o grafo.")
    parser.add_argument("--data-file", type=Path, required=True, help="Arquivo Excel/CSV com coordenadas por ID.")
    parser.add_argument("--id-col", default="NUM_BO", help="Coluna de ID no dataset (default: NUM_BO).")
    parser.add_argument("--lat-col", default="LATITUDE", help="Coluna de latitude (default: LATITUDE).")
    parser.add_argument("--lon-col", default="LONGITUDE", help="Coluna de longitude (default: LONGITUDE).")
    parser.add_argument("--sheet-name", help="Nome da planilha (quando input for Excel).")
    parser.add_argument("--max-rows", type=int, help="Limita o número de linhas lidas (opcional).")
    parser.add_argument(
        "--algorithm",
        choices=("greedy", "label_prop", "asyn_label_prop", "kclique"),
        default="greedy",
        help="Algoritmo de comunidades (default: greedy).",
    )
    parser.add_argument("--k-clique", type=int, help="Valor de k para o algoritmo k-clique.")
    parser.add_argument("--min-size", type=int, default=3, help="Ignora comunidades menores (default: 3).")
    parser.add_argument("--top-n", type=int, default=15, help="Número de comunidades exibidas (default: 15).")
    parser.add_argument(
        "--bridges-top",
        type=int,
        default=20,
        help="Número de nós ponte a destacar (0 desativa, default: 5).",
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
    parser.add_argument(
        "--neighborhoods-geojson",
        type=Path,
        help="Caminho para GeoJSON com polígonos dos bairros (opcional).",
    )
    parser.add_argument(
        "--safe-top",
        type=int,
        default=0,
        help="Gera também um mapa com as menores comunidades (regiões mais 'seguras'); 0 desativa.",
    )
    parser.add_argument(
        "--safe-min-size",
        type=int,
        default=100,
        help="Tamanho mínimo de comunidade para entrar no mapa seguro (default: 100 nós).",
    )
    parser.add_argument(
        "--safe-output",
        type=Path,
        help="HTML opcional para salvar o mapa das comunidades mais seguras.",
    )
    parser.add_argument("--output", type=Path, default=Path("plots/communities_map.html"), help="HTML de saída.")
    parser.add_argument("--zoom-start", type=int, default=12, help="Zoom inicial do mapa (default: 12).")
    parser.add_argument("--tiles", default="CartoDB positron", help="Layer de tiles (default: CartoDB positron).")
    parser.add_argument("--marker-radius", type=int, default=6, help="Raio dos marcadores de comunidade.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = load_dataframe(args.data_file, sheet_name=args.sheet_name, max_rows=args.max_rows)
    coord_lookup = build_coordinate_lookup(df, args.id_col, args.lat_col, args.lon_col)
    if not coord_lookup:
        raise ValueError("Nenhuma coordenada válida encontrada no dataset.")

    graph = build_graph_from_jsonl(args.distances, args.threshold)
    communities = detect_communities(graph, args.algorithm, k_clique=args.k_clique)
    communities = filter_communities(communities, min_size=max(1, args.min_size))
    top_communities = extract_top_communities(communities, coord_lookup, args.top_n)
    safe_communities: List[List[str]] = []
    if args.safe_top > 0:
        safe_communities = extract_smallest_communities(
            communities,
            coord_lookup,
            args.safe_top,
            min_size=args.safe_min_size,
        )
    bridge_nodes = []
    if args.bridges_top > 0:
        sample = args.bridges_sample if args.bridges_sample > 0 else None
        bridge_nodes = [
            b
            for b in identify_bridge_nodes(
                graph,
                communities,
                top_k=args.bridges_top,
                verbose=True,
                sample_size=sample,
                seed=args.bridges_seed,
            )
            if b["node"] in coord_lookup
        ]

    if not top_communities:
        raise ValueError("Nenhuma comunidade com coordenadas válidas para plotar.")

    center = (
        sum(lat for lat, _ in coord_lookup.values()) / len(coord_lookup),
        sum(lon for _, lon in coord_lookup.values()) / len(coord_lookup),
    )
    fmap = create_map(center, zoom_start=args.zoom_start, tiles=args.tiles)
    add_community_markers(fmap, top_communities, coord_lookup, marker_radius=args.marker_radius)
    add_bridge_markers(fmap, bridge_nodes, coord_lookup, marker_radius=args.marker_radius)
    if args.neighborhoods_geojson:
        add_neighborhood_boundaries(fmap, args.neighborhoods_geojson, layer_name="Regiões")
    folium.LayerControl(collapsed=False).add_to(fmap)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(args.output))
    print(f"Mapa de comunidades salvo em: {args.output}")

    if args.safe_output and safe_communities:
        safe_map = create_map(center, zoom_start=args.zoom_start, tiles=args.tiles)
        add_community_markers(
            safe_map,
            safe_communities,
            coord_lookup,
            marker_radius=args.marker_radius,
            colors=SAFE_COLORS,
        )
        if args.neighborhoods_geojson:
            add_neighborhood_boundaries(safe_map, args.neighborhoods_geojson, layer_name="Regiões")
        folium.LayerControl(collapsed=False).add_to(safe_map)
        args.safe_output.parent.mkdir(parents=True, exist_ok=True)
        safe_map.save(str(args.safe_output))
        print(f"Mapa de comunidades mais seguras salvo em: {args.safe_output}")


if __name__ == "__main__":
    main()
