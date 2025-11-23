#!/usr/bin/env python3
"""Export building nodes from an OSM PBF into a CSV for quick map inspection."""

import argparse
import csv
import sys
from pathlib import Path

# Allow importing application modules without installing the package
ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "api" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.append(str(BACKEND_PATH))

from infrastructure.osm.osm_handler import build_access_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a CSV containing every building node (lon/lat) discovered "
            "by the access-graph handler."
        )
    )
    parser.add_argument(
        "pbf",
        type=Path,
        help="Path to the source .pbf file (e.g. cities_pbf/Город.pbf)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("buildings.csv"),
        help="Destination CSV path (defaults to ./buildings.csv)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.pbf.exists():
        print(f"Input PBF not found: {args.pbf}", file=sys.stderr)
        return 1

    nodes, _ = build_access_graph(str(args.pbf))
    building_nodes = [node for node in nodes if node.get("node_type") == "building"]

    if not building_nodes:
        print("No building nodes found", file=sys.stderr)
        return 2

    with args.output.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["source_id", "longitude", "latitude", "name"])
        for node in building_nodes:
            writer.writerow(
                [
                    node.get("source_id"),
                    node.get("longitude"),
                    node.get("latitude"),
                    node.get("name") or "",
                ]
            )

    print(
        f"Exported {len(building_nodes)} building nodes to {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
