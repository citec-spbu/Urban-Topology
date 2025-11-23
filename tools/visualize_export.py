#!/usr/bin/env python3
"""Render an exported city graph (nodes/edges CSVs) onto a Folium map."""

from __future__ import annotations

import argparse
import pathlib
from typing import Dict, Tuple

import folium
import pandas as pd

REQUIRED_FILES = [
    "nodes.csv",
    "edges.csv",
]


def read_csv(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path)


def build_node_lookup(nodes_df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    lookup: Dict[str, Tuple[float, float]] = {}
    for _, row in nodes_df.iterrows():
        node_id = str(row.get("id", "")).strip()
        lat = row.get("latitude")
        lon = row.get("longitude")
        if not node_id or pd.isna(lat) or pd.isna(lon):
            continue
        lookup[node_id] = (float(lat), float(lon))
    return lookup


def default_center(nodes_df: pd.DataFrame) -> Tuple[float, float]:
    if nodes_df.empty:
        return (55.75, 37.61)

    coords = nodes_df[["latitude", "longitude"]].dropna()
    if coords.empty:
        return (55.75, 37.61)
    lat = coords["latitude"].astype(float).mean()
    lon = coords["longitude"].astype(float).mean()
    return (float(lat), float(lon))


def add_edges_to_map(
    fmap: folium.Map,
    edges_df: pd.DataFrame,
    node_lookup: Dict[str, Tuple[float, float]],
) -> None:
    base_group = folium.FeatureGroup(name="Основной граф", show=True)
    access_group = folium.FeatureGroup(name="Придомовой слой", show=False)

    for _, row in edges_df.iterrows():
        source = str(row.get("source", row.get("from", ""))).strip()
        target = str(row.get("target", row.get("to", ""))).strip()
        if not source or not target:
            continue
        if source not in node_lookup or target not in node_lookup:
            continue
        coords = [node_lookup[source], node_lookup[target]]
        layer = str(row.get("layer", "base")).lower()
        raw_flag = row.get("is_building_link", False)
        if pd.isna(raw_flag):
            is_building_link = False
        elif isinstance(raw_flag, str):
            is_building_link = raw_flag.strip().lower() in {"1", "true", "t", "yes"}
        else:
            is_building_link = bool(raw_flag)
        color = (
            "#1f2937"
            if layer == "base"
            else ("#16a34a" if is_building_link else "#f97316")
        )
        weight = 4 if layer == "base" else (3 if is_building_link else 4)
        popup_text = (
            f"ID: {row.get('id', '')}<br>"
            f"Слой: {layer}<br>"
            f"Длина: {row.get('length_m', 'n/a')} м"
        )
        segment = folium.PolyLine(
            coords, color=color, weight=weight, opacity=0.9, popup=popup_text
        )
        if layer == "base":
            base_group.add_child(segment)
        else:
            access_group.add_child(segment)

    fmap.add_child(base_group)
    fmap.add_child(access_group)


def add_nodes_to_map(fmap: folium.Map, nodes_df: pd.DataFrame) -> None:
    for _, row in nodes_df.iterrows():
        node_id = str(row.get("id", "")).strip()
        if not node_id:
            continue
        lat = row.get("latitude")
        lon = row.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            continue
        node_type = str(row.get("node_type", "intersection"))
        layer = str(row.get("layer", "base"))
        color = (
            "#2563eb"
            if layer == "base"
            else ("#16a34a" if node_type == "building" else "#f97316")
        )
        folium.CircleMarker(
            location=(float(lat), float(lon)),
            radius=4 if layer == "base" else 5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=f"ID: {node_id}<br>Слой: {layer}<br>Тип: {node_type}",
        ).add_to(fmap)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize exported graph CSVs on a Folium map"
    )
    parser.add_argument(
        "folder",
        type=pathlib.Path,
        help="Path to directory containing nodes.csv/edges.csv",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("graph_map.html"),
        help="Path to save the resulting HTML map",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    for filename in REQUIRED_FILES:
        path = folder / filename
        if not path.exists():
            raise FileNotFoundError(f"Expected {filename} in {folder}")

    nodes_df = read_csv(folder / "nodes.csv")
    edges_df = read_csv(folder / "edges.csv")

    center_lat, center_lon = default_center(nodes_df)
    fmap = folium.Map(
        location=[center_lat, center_lon], zoom_start=13, tiles="cartodbpositron"
    )

    lookup = build_node_lookup(nodes_df)
    add_edges_to_map(fmap, edges_df, lookup)
    add_nodes_to_map(fmap, nodes_df)

    folium.LayerControl(collapsed=False).add_to(fmap)

    output_path = args.output.expanduser().resolve()
    fmap.save(str(output_path))
    print(f"Map saved to {output_path}")


if __name__ == "__main__":
    main()
