#!/usr/bin/env python3
"""
Gera um heatmap/Mapa interativo a partir das coordenadas do dataset bruto.

Este script é independente do cálculo de distâncias. Ele lê o mesmo arquivo
informado via DATA_FILE, limpa coordenadas inválidas e produz um HTML com
camada de calor + marcadores de contagem agregada.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import folium
import pandas as pd
from folium.plugins import HeatMap


def load_dataframe(input_path: Path, sheet_name: str | None, max_rows: int | None) -> pd.DataFrame:
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


def sanitize_coordinates(df: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    coords = df[[lat_col, lon_col]].copy()
    coords[lat_col] = pd.to_numeric(coords[lat_col], errors="coerce")
    coords[lon_col] = pd.to_numeric(coords[lon_col], errors="coerce")
    coords = coords.dropna(subset=[lat_col, lon_col])
    coords = coords[(coords[lat_col] != 0) & (coords[lon_col] != 0)]

    if coords.empty:
        raise ValueError(f"No valid coordinates found in columns {lat_col}, {lon_col}.")

    return coords.reset_index(drop=True)


def compute_center(points: pd.DataFrame, lat_col: str, lon_col: str) -> Tuple[float, float]:
    return float(points[lat_col].mean()), float(points[lon_col].mean())


def aggregate_counts(points: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    return (
        points.groupby([lat_col, lon_col])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )


def prepare_heatmap_payload(counts: pd.DataFrame, lat_col: str, lon_col: str) -> List[List[float]]:
    return counts[[lat_col, lon_col, "count"]].to_numpy().tolist()


def build_heatmap(
    heat_data: Iterable[Iterable[float]],
    center: Tuple[float, float],
    radius: int,
    blur: int,
    max_zoom: int,
    tiles: str,
    zoom_start: int,
) -> folium.Map:
    fmap = folium.Map(location=center, zoom_start=zoom_start, tiles=tiles)
    HeatMap(list(heat_data), radius=radius, blur=blur, max_zoom=max_zoom, min_opacity=0.4).add_to(fmap)
    return fmap


def add_markers(
    fmap: folium.Map,
    counts: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    tooltip_template: str,
) -> None:
    marker_layer = folium.FeatureGroup(name="Ocorrências (agregadas)")
    for _, row in counts.iterrows():
        count = int(row["count"])
        radius = min(4 + (count ** 0.5) * 2, 30)
        folium.CircleMarker(
            location=(row[lat_col], row[lon_col]),
            radius=radius,
            color="crimson",
            fill=True,
            fill_color="crimson",
            fill_opacity=0.7,
            weight=1,
            tooltip=tooltip_template.format(count=count),
        ).add_to(marker_layer)
    marker_layer.add_to(fmap)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera um heatmap interativo das ocorrências geolocalizadas.")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Arquivo Excel/CSV com colunas de latitude/longitude.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("plots/heatmap.html"),
        help="HTML de saída (default: plots/heatmap.html).",
    )
    parser.add_argument("--lat-col", default="LATITUDE", help="Coluna de latitude (default: LATITUDE).")
    parser.add_argument("--lon-col", default="LONGITUDE", help="Coluna de longitude (default: LONGITUDE).")
    parser.add_argument("--sheet-name", help="Nome da planilha (quando input for Excel).")
    parser.add_argument("--max-rows", type=int, help="Limita o número de linhas lidas (opcional).")

    parser.add_argument("--radius", type=int, default=12, help="Raio do ponto na camada de calor (default: 12).")
    parser.add_argument("--blur", type=int, default=18, help="Fator de blur da camada de calor (default: 18).")
    parser.add_argument("--max-zoom", type=int, default=18, help="Zoom máximo para o heatmap (default: 18).")
    parser.add_argument("--zoom-start", type=int, default=12, help="Zoom inicial do mapa (default: 12).")
    parser.add_argument("--tiles", default="CartoDB positron", help="Camada base de tiles (default: CartoDB positron).")
    parser.add_argument(
        "--disable-markers",
        action="store_true",
        help="Não adiciona marcadores de contagem (layer adicional).",
    )
    parser.add_argument(
        "--tooltip-template",
        default="{count} ocorrências",
        help="Template de tooltip para marcadores (default: '{count} ocorrências').",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = load_dataframe(args.input, sheet_name=args.sheet_name, max_rows=args.max_rows)
    coords = sanitize_coordinates(df, args.lat_col, args.lon_col)
    center = compute_center(coords, args.lat_col, args.lon_col)
    aggregated = aggregate_counts(coords, args.lat_col, args.lon_col)
    heatmap_payload = prepare_heatmap_payload(aggregated, args.lat_col, args.lon_col)

    fmap = build_heatmap(
        heatmap_payload,
        center=center,
        radius=args.radius,
        blur=args.blur,
        max_zoom=args.max_zoom,
        tiles=args.tiles,
        zoom_start=args.zoom_start,
    )

    if not args.disable_markers:
        add_markers(fmap, aggregated, args.lat_col, args.lon_col, args.tooltip_template)

    folium.LayerControl(collapsed=False).add_to(fmap)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(args.output))
    print(f"Heatmap salvo em: {args.output}")


if __name__ == "__main__":
    main()
