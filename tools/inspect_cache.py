#!/usr/bin/env python3
"""Inspect cached graph payloads and report potential data issues."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


def _read_csv_rows(payload: str | None) -> List[Dict[str, str]]:
    if not payload:
        return []
    reader = csv.DictReader(io.StringIO(payload))
    return [dict(row) for row in reader]


def _collect_missing_edge_nodes(
    edges: Sequence[Dict[str, str]],
    node_ids: Iterable[str],
) -> List[str]:
    available = set(node_ids)
    missing: List[str] = []
    for row in edges:
        for key in ("source", "target", "from", "to", "id_src", "id_dist", "id_dst"):
            node_id = row.get(key)
            if node_id and node_id not in available:
                missing.append(node_id)
    return missing


def inspect_cache(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))

    points = _read_csv_rows(data.get("points_csv"))
    edges = _read_csv_rows(data.get("edges_csv"))
    metrics = _read_csv_rows(data.get("metrics_csv"))
    ways_props = _read_csv_rows(data.get("ways_properties_csv"))
    points_props = _read_csv_rows(data.get("points_properties_csv"))
    access_nodes = _read_csv_rows(data.get("access_nodes_csv"))
    access_edges = _read_csv_rows(data.get("access_edges_csv"))

    metrics_index = {row.get("id"): row for row in metrics if row.get("id")}
    nodes_missing_metrics = [
        row["id"] for row in points if row.get("id") not in metrics_index
    ]

    missing_edge_nodes = _collect_missing_edge_nodes(
        edges, (row.get("id") or "" for row in points)
    )

    print(f"Cache file: {path}")
    print("Summary:")
    print(f"  Points:          {len(points):6d}")
    print(f"  Edges:           {len(edges):6d}")
    print(f"  Metrics:         {len(metrics):6d}")
    print(f"  Way properties:  {len(ways_props):6d}")
    print(f"  Point properties:{len(points_props):6d}")
    print(f"  Access nodes:    {len(access_nodes):6d}")
    print(f"  Access edges:    {len(access_edges):6d}")

    if nodes_missing_metrics:
        print(
            f"\nNodes without metrics: {len(nodes_missing_metrics)} (showing up to 10)"
        )
        for node_id in nodes_missing_metrics[:10]:
            print(f"  - {node_id}")

    if missing_edge_nodes:
        print(
            f"\nEdges referencing missing nodes: {len(missing_edge_nodes)} (showing up to 10)"
        )
        for node_id in missing_edge_nodes[:10]:
            print(f"  - {node_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="Path to a cached response JSON file")
    args = parser.parse_args()

    inspect_cache(args.cache)


if __name__ == "__main__":
    main()
