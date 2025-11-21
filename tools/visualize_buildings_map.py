#!/usr/bin/env python3
"""Render building nodes from a PBF onto an interactive Leaflet map."""

import argparse
import sys
from pathlib import Path

try:
    import folium
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "folium is required (pip install folium) to run visualize_buildings_map.py"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "api" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.append(str(BACKEND_PATH))

from infrastructure.osm.osm_handler import build_access_graph  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an HTML map showing every building node produced by "
            "the access-graph handler."
        )
    )
    parser.add_argument(
        "pbf",
        type=Path,
        help="Path to the source .pbf file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("buildings_map.html"),
        help="HTML file to write (default: buildings_map.html)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of buildings to plot (for huge cities)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.pbf.exists():
        print(f"Input PBF not found: {args.pbf}", file=sys.stderr)
        return 1

    nodes, _ = build_access_graph(str(args.pbf))
    buildings = [n for n in nodes if n.get("node_type") == "building"]
    if not buildings:
        print("No building nodes found", file=sys.stderr)
        return 2

    if args.limit is not None:
        buildings = buildings[: args.limit]

    avg_lat = sum(node.get("latitude", 0.0) for node in buildings) / len(buildings)
    avg_lon = sum(node.get("longitude", 0.0) for node in buildings) / len(buildings)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, tiles="OpenStreetMap")
    fg = folium.FeatureGroup(name="Buildings")

    for node in buildings:
        lat = node.get("latitude")
        lon = node.get("longitude")
        name = node.get("name") or f"building:{node.get('source_id')}"
        fg.add_child(
            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color="blue",
                fill=True,
                fill_opacity=0.6,
                popup=name,
            )
        )

    fg.add_to(m)
    folium.LayerControl().add_to(m)
    m.save(str(args.output))
    print(f"Saved building map with {len(buildings)} markers to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
