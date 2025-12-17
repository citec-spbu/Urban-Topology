"""Convert database objects and metrics into convenient schema/CSV payloads."""

import io
import zipfile
from typing import Iterable, List, Sequence, Optional, Dict
from collections import defaultdict

import pandas as pd
import networkx as nx

from domain.schemas import GraphBase, PointBase


NODE_EXPORT_COLUMNS = [
    "id",
    "longitude",
    "latitude",
    "node_type",
    "source_type",
    "source_id",
    "name",
    "layer",
]

EDGE_EXPORT_COLUMNS = [
    "id",
    "source",
    "target",
    "id_way",
    "source_way_id",
    "road_type",
    "length_m",
    "is_building_link",
    "name",
    "layer",
]


def list_to_csv_str(data: Iterable[Sequence], columns: List[str]):
    """Return a CSV string and DataFrame for the given rows."""
    buffer = io.StringIO()
    df = pd.DataFrame(data, columns=columns)

    # Convert ID columns to nullable integers to preserve integer types and handle NaN
    id_columns = ["id", "source", "target", "id_way", "source_way_id", "source_id"]
    for col in id_columns:
        if col in df.columns:
            # Convert to numeric, then to Int64 (nullable integer type)
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Export to CSV, replacing <NA> with empty strings
    df.to_csv(buffer, index=False, na_rep="")
    return buffer.getvalue(), df


def graph_to_scheme(
    points,
    edges,
    pprop,
    wprop,
    metrics,
    access_nodes: Optional[List[List]] = None,
    access_edges: Optional[List[List]] = None,
) -> GraphBase:
    """
    Convert graph pieces into CSV blobs ready for GraphBase.

    If points/edges contain unified format with layer information (8+ fields for nodes, 10+ for edges),
    they are used directly. Otherwise, legacy format is assumed and access_nodes/access_edges are processed separately.
    """
    # Check if we have unified format (with layer metadata)
    has_unified_nodes = points and len(points[0]) >= 8 if points else False
    has_unified_edges = edges and len(edges[0]) >= 10 if edges else False

    if has_unified_nodes and has_unified_edges:
        # New unified format with layer information
        # Points format: [id, longitude, latitude, node_type, source_type, source_id, name, layer]
        points_str, _ = list_to_csv_str(
            points,
            [
                "id",
                "longitude",
                "latitude",
                "node_type",
                "source_type",
                "source_id",
                "name",
                "layer",
            ],
        )

        # Edges format: [id, source, target, id_way, source_way_id, road_type, length_m, is_building_link, name, layer]
        edges_str, _ = list_to_csv_str(
            edges,
            [
                "id",
                "source",
                "target",
                "id_way",
                "source_way_id",
                "road_type",
                "length_m",
                "is_building_link",
                "name",
                "layer",
            ],
        )

        # In unified format, access_nodes and access_edges are already merged
        access_nodes_str = None
        access_edges_str = None
    else:
        # Legacy format - separate base and access layers
        edges_str, _ = list_to_csv_str(
            edges, ["id", "id_way", "source", "target", "name"]
        )
        points_str, _ = list_to_csv_str(points, ["id", "longitude", "latitude"])

        access_nodes_str = None
        access_edges_str = None
        if access_nodes is not None:
            access_nodes_str, _ = list_to_csv_str(
                access_nodes,
                [
                    "id",
                    "node_type",
                    "longitude",
                    "latitude",
                    "source_type",
                    "source_id",
                    "name",
                ],
            )
        if access_edges is not None:
            access_edges_str, _ = list_to_csv_str(
                access_edges,
                [
                    "id",
                    "source",
                    "target",
                    "source_way_id",
                    "road_type",
                    "length_m",
                    "is_building_link",
                    "name",
                ],
            )

    pprop_str, _ = list_to_csv_str(pprop, ["id", "property", "value"])
    wprop_str, _ = list_to_csv_str(wprop, ["id", "property", "value"])
    metrics_str, _ = list_to_csv_str(
        metrics,
        [
            "id",
            "degree",
            "in_degree",
            "out_degree",
            "eigenvector",
            "betweenness",
            "radius",
            "color",
        ],
    )

    return GraphBase(
        edges_csv=edges_str,
        points_csv=points_str,
        ways_properties_csv=wprop_str,
        points_properties_csv=pprop_str,
        metrics_csv=metrics_str,
        access_nodes_csv=access_nodes_str,
        access_edges_csv=access_edges_str,
    )


def point_obj_to_list(db_record) -> List:
    """Return the point record as a list for serialization."""
    return [db_record.id, db_record.longitude, db_record.latitude]


def edge_obj_to_list(db_record) -> List:
    """Return the edge record as a list for serialization."""
    return [
        db_record.id,
        db_record.id_way,
        db_record.id_src,
        db_record.id_dist,
        db_record.name,
    ]


def record_obj_to_wprop(record) -> List:
    """Convert a way property record into a serializable list."""
    return [record.id_way, record.property, record.value]


def record_obj_to_pprop(record) -> List:
    """Convert a point property record into a serializable list."""
    return [record.id_point, record.property, record.value]


def access_node_obj_to_list(record) -> List:
    """Convert an access-node row into a serializable list."""
    return [
        record.id,
        record.node_type,
        record.longitude,
        record.latitude,
        record.source_type,
        record.source_id,
        record.name,
    ]


def access_edge_obj_to_list(record) -> List:
    """Convert an access-edge row into a serializable list."""
    return [
        record.id,
        record.id_src,
        record.id_dst,
        record.source_way_id,
        record.road_type,
        record.length_m,
        record.is_building_link,
        record.name,
    ]


def point_to_scheme(point) -> Optional[PointBase]:
    """Convert a point ORM object into a PointBase schema."""
    if point is None:
        return None

    return PointBase(latitude=point.latitude, longitude=point.longitude)


def _csv_to_dataframe(csv_content: Optional[str]) -> Optional[pd.DataFrame]:
    """Return a DataFrame for a CSV string, if content is present."""
    if not csv_content:
        return None

    stripped = csv_content.strip()
    if not stripped:
        return None

    return pd.read_csv(io.StringIO(stripped), dtype=str)


def _export_csv_from_frames(frames: List[pd.DataFrame]) -> str:
    """Serialize concatenated frames into a CSV string."""
    valid_frames: List[pd.DataFrame] = []
    for frame in frames:
        if frame is None or frame.empty:
            continue
        if frame.dropna(how="all").empty:
            continue
        valid_frames.append(frame)

    if not valid_frames:
        return ""

    merged = pd.concat(valid_frames, ignore_index=True, copy=False)
    buffer = io.StringIO()
    merged.to_csv(buffer, index=False)
    return buffer.getvalue()


def merge_nodes_csv(points_csv: str, access_nodes_csv: Optional[str]) -> str:
    """Combine base graph nodes with optional access-layer nodes."""
    frames: List[pd.DataFrame] = []

    base_df = _csv_to_dataframe(points_csv)
    if base_df is not None and not base_df.empty:
        base_df = base_df.copy()
        for column in NODE_EXPORT_COLUMNS:
            if column not in base_df.columns:
                base_df[column] = pd.NA
        base_df["node_type"] = "graph"
        base_df["source_type"] = "point"
        base_df["source_id"] = pd.NA
        base_df["name"] = pd.NA
        base_df["layer"] = "base"
        frames.append(base_df[NODE_EXPORT_COLUMNS])

    access_df = _csv_to_dataframe(access_nodes_csv)
    if access_df is not None and not access_df.empty:
        access_df = access_df.copy()
        for column in NODE_EXPORT_COLUMNS:
            if column not in access_df.columns:
                access_df[column] = pd.NA
        access_df["layer"] = "access"
        frames.append(access_df[NODE_EXPORT_COLUMNS])

    return _export_csv_from_frames(frames)


def merge_edges_csv(edges_csv: str, access_edges_csv: Optional[str]) -> str:
    """Combine base edges with optional access-layer edges."""
    frames: List[pd.DataFrame] = []

    base_df = _csv_to_dataframe(edges_csv)
    if base_df is not None and not base_df.empty:
        base_df = base_df.copy()
        for column in EDGE_EXPORT_COLUMNS:
            if column not in base_df.columns:
                base_df[column] = pd.NA
        base_df["source_way_id"] = pd.NA
        base_df["road_type"] = pd.NA
        base_df["length_m"] = pd.NA
        base_df["is_building_link"] = False
        base_df["layer"] = "base"
        frames.append(base_df[EDGE_EXPORT_COLUMNS])

    access_df = _csv_to_dataframe(access_edges_csv)
    if access_df is not None and not access_df.empty:
        access_df = access_df.copy()
        for column in EDGE_EXPORT_COLUMNS:
            if column not in access_df.columns:
                access_df[column] = pd.NA
        access_df["layer"] = "access"
        frames.append(access_df[EDGE_EXPORT_COLUMNS])

    return _export_csv_from_frames(frames)


def graph_to_zip_archive(graph: GraphBase) -> io.BytesIO:
    """Pack merged CSV payloads into an in-memory ZIP archive."""
    buffer = io.BytesIO()
    nodes_csv = merge_nodes_csv(graph.points_csv, graph.access_nodes_csv)
    edges_csv = merge_edges_csv(graph.edges_csv, graph.access_edges_csv)

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nodes.csv", nodes_csv)
        archive.writestr("edges.csv", edges_csv)
        archive.writestr("points_properties.csv", graph.points_properties_csv or "")
        archive.writestr("ways_properties.csv", graph.ways_properties_csv or "")
        archive.writestr("metrics.csv", graph.metrics_csv or "")

    buffer.seek(0)
    return buffer


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters using Haversine formula."""
    from math import radians, cos, sin, asin, sqrt

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r


def _normalize_node(node: List) -> tuple[int | str, float, float]:
    """
    Extract node id, longitude, and latitude from node representation.

    Handles both formats:
    - points: [id, longitude, latitude]
    - access_nodes: [id, node_type, longitude, latitude, source_type, source_id, name]
    """
    if len(node) == 3:
        # points format: [id, lon, lat]
        return node[0], float(node[1]), float(node[2])
    elif len(node) >= 4:
        # access_nodes format: [id, node_type, lon, lat, ...]
        return node[0], float(node[2]), float(node[3])
    else:
        raise ValueError(f"Invalid node format: {node}")


def _snap_nearby_nodes(
    points: List[List],
    edges: List[List],
    snap_distance_m: float = 10.0,
    edge_metadata: Optional[Dict] = None,
) -> tuple[List[List], List[List], dict]:
    """
    Snap nearby nodes together and update edges accordingly.

    Handles mixed node formats (points and access_nodes with different structures).

    Returns:
        - merged_points: list of merged point coordinates
        - updated_edges: list of edges with updated node IDs
        - node_mapping: dict mapping old node IDs to new merged node IDs
    """
    if not points:
        return points, edges, {}

    # Build node index by extracting coordinates
    nodes_by_id = {}
    node_formats = {}  # Track original node format for each id

    for node in points:
        node_id, lon, lat = _normalize_node(node)
        nodes_by_id[node_id] = (lon, lat)
        node_formats[node_id] = node  # Store original node

    node_list = list(nodes_by_id.items())

    # Union-Find structure to group nearby nodes
    parent = {node_id: node_id for node_id, _ in node_list}

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Find nearby nodes and merge them
    for i in range(len(node_list)):
        id1, (lon1, lat1) = node_list[i]
        for j in range(i + 1, len(node_list)):
            id2, (lon2, lat2) = node_list[j]
            distance = _haversine_distance_m(lat1, lon1, lat2, lon2)
            if distance <= snap_distance_m:
                union(id1, id2)

    # Build mapping from old IDs to representative IDs
    node_mapping = {}
    merged_nodes = {}
    for node_id in nodes_by_id:
        representative = find(node_id)
        node_mapping[node_id] = representative
        if representative not in merged_nodes:
            merged_nodes[representative] = node_formats[representative]

    # Create new points list with merged nodes (preserving original format)
    merged_points = list(merged_nodes.values())

    # Update edges to use merged node IDs
    updated_edges = []
    for edge in edges:
        edge_copy = edge.copy()

        # Detect edge format using metadata if available
        # Base edges: [id, id_way, source, target, name] - source at index 2, target at index 3
        # Access edges: [id, source, target, ...] - source at index 1, target at index 2

        if edge_metadata:
            is_base_edge = edge_metadata.get(edge[0], {}).get("layer") == "base"
        else:
            # Fallback to isinstance if metadata not available
            is_base_edge = isinstance(edge[0], (int, float))

        if is_base_edge:
            # Base edge format: [id, id_way, source, target, name, ...]
            if len(edge) > 2:
                edge_copy[2] = node_mapping.get(edge[2], edge[2])
            if len(edge) > 3:
                edge_copy[3] = node_mapping.get(edge[3], edge[3])
        else:
            # Access edge format: [id, source, target, ...]
            if len(edge) > 1:
                edge_copy[1] = node_mapping.get(edge[1], edge[1])
            if len(edge) > 2:
                edge_copy[2] = node_mapping.get(edge[2], edge[2])

        updated_edges.append(edge_copy)

    return merged_points, updated_edges, node_mapping


def _keep_largest_component(
    points: List[List],
    edges: List[List],
    metrics: List[List],
    node_metadata: Optional[Dict] = None,
    edge_metadata: Optional[Dict] = None,
    node_mapping: Optional[Dict] = None,
) -> tuple[List[List], List[List], List[List]]:
    """
    Filter graph to keep only the largest connected component and access nodes.

    Keeps:
    - The largest road network component (base layer)
    - All access nodes/edges (buildings, pedestrian links) even if disconnected

    Uses node_metadata to identify access nodes instead of relying on unified format field.

    Returns:
        - filtered_points: nodes in the largest component + all access nodes
        - filtered_edges: edges in the largest component + all access edges
        - filtered_metrics: metrics for remaining nodes
    """
    if not points or not edges:
        return points, edges, metrics

    # Default empty metadata if not provided
    if node_metadata is None:
        node_metadata = {}
    if edge_metadata is None:
        edge_metadata = {}

    # Identify access layer nodes/edges using metadata
    access_node_ids = set()
    access_edge_ids = set()
    base_node_ids = set()

    for point in points:
        node_id = point[0]
        metadata = node_metadata.get(node_id, {})
        if metadata.get("layer") == "access":
            access_node_ids.add(node_id)
        else:
            base_node_ids.add(node_id)

    for edge in edges:
        edge_id = edge[0]
        metadata = edge_metadata.get(edge_id, {})
        if metadata.get("layer") == "access":
            access_edge_ids.add(edge_id)

    # Determine edge format from first edge
    if edges:
        first_edge = edges[0]
        is_unified_format = len(first_edge) >= 10
    else:
        is_unified_format = False

    # Build graph ONLY from base edges to find largest component
    G = nx.Graph()
    G.add_nodes_from(base_node_ids)

    for edge in edges:
        if edge[0] not in access_edge_ids:  # Only base edges
            if is_unified_format:
                # Unified format: [id, source, target, ...]
                # Source is at index 1, target is at index 2
                if len(edge) > 2:
                    source, target = edge[1], edge[2]
                    if source in base_node_ids and target in base_node_ids:
                        G.add_edge(source, target)
            else:
                # Legacy format: [id, id_way, source, target, name]
                # Source is at index 2, target is at index 3
                if len(edge) > 3:
                    source, target = edge[2], edge[3]
                    if source in base_node_ids and target in base_node_ids:
                        G.add_edge(source, target)

    # Find connected components in base network only
    if G.number_of_nodes() > 0:
        components = list(nx.connected_components(G))
        if components:
            # Keep the largest component
            largest_component = max(components, key=len)
            largest_component_set = set(largest_component)
        else:
            largest_component_set = set()
    else:
        largest_component_set = set()

    # Identify which access nodes have edges
    # Collect ALL nodes used by access edges, regardless of connectivity
    access_nodes_with_edges = set()

    for edge in edges:
        if edge[0] in access_edge_ids:
            # For access edges: [id, source, target, ...]
            if len(edge) > 2:
                source, target = edge[1], edge[2]
                access_nodes_with_edges.add(source)
                access_nodes_with_edges.add(target)

    print(f"DEBUG: access_node_ids count: {len(access_node_ids)}")
    print(f"DEBUG: access_edge_ids count: {len(access_edge_ids)}")
    print(f"DEBUG: access_nodes_with_edges count: {len(access_nodes_with_edges)}")

    # Filter points: keep largest component + all nodes referenced by access edges
    filtered_points = [
        point
        for point in points
        if point[0] in largest_component_set or point[0] in access_nodes_with_edges
    ]

    # Filter edges: keep base edges in largest component + access edges with valid endpoints
    filtered_point_ids = {point[0] for point in filtered_points}
    filtered_edges = []
    access_edges_rejected = 0
    missing_sources = set()
    missing_targets = set()
    for edge in edges:
        if edge[0] in access_edge_ids:
            # Keep access edges only if both endpoints exist in filtered points
            if is_unified_format:
                if (
                    len(edge) > 2
                    and edge[1] in filtered_point_ids
                    and edge[2] in filtered_point_ids
                ):
                    filtered_edges.append(edge)
                else:
                    access_edges_rejected += 1
                    if len(edge) > 2:
                        if edge[1] not in filtered_point_ids:
                            missing_sources.add(edge[1])
                        if edge[2] not in filtered_point_ids:
                            missing_targets.add(edge[2])
            else:
                if (
                    len(edge) > 2
                    and edge[1] in filtered_point_ids
                    and edge[2] in filtered_point_ids
                ):
                    filtered_edges.append(edge)
                else:
                    access_edges_rejected += 1
                    if len(edge) > 2:
                        if edge[1] not in filtered_point_ids:
                            missing_sources.add(edge[1])
                        if edge[2] not in filtered_point_ids:
                            missing_targets.add(edge[2])
        else:
            # Base edge: check both source and target endpoints
            if is_unified_format:
                # Unified format: source at index 1, target at index 2
                if (
                    len(edge) > 2
                    and edge[1] in largest_component_set
                    and edge[2] in largest_component_set
                ):
                    filtered_edges.append(edge)
            else:
                # Legacy format: source at index 2, target at index 3
                if (
                    len(edge) > 3
                    and edge[2] in largest_component_set
                    and edge[3] in largest_component_set
                ):
                    filtered_edges.append(edge)

    print(f"DEBUG: access_edges_rejected: {access_edges_rejected}")
    print(
        f"DEBUG: missing_sources count: {len(missing_sources)}, sample: {list(missing_sources)[:5]}"
    )
    print(
        f"DEBUG: missing_targets count: {len(missing_targets)}, sample: {list(missing_targets)[:5]}"
    )

    # Check if missing nodes exist in original points list
    all_point_ids = {point[0] for point in points}
    missing_in_points = (missing_sources | missing_targets) - all_point_ids
    print(
        f"DEBUG: missing nodes not in points at all: {len(missing_in_points)}, sample: {list(missing_in_points)[:5]}"
    )

    # Check if these nodes exist in node_mapping (as keys - they were merged)
    if node_mapping:
        missing_as_keys = missing_in_points & set(node_mapping.keys())
        missing_as_values = missing_in_points & set(node_mapping.values())
        truly_missing = (
            missing_in_points - set(node_mapping.keys()) - set(node_mapping.values())
        )
        print(
            f"DEBUG: missing nodes that were merged (in keys): {len(missing_as_keys)}"
        )
        print(
            f"DEBUG: missing nodes that are representatives (in values): {len(missing_as_values)}"
        )
        print(
            f"DEBUG: truly missing nodes (not in mapping at all): {len(truly_missing)}, sample: {list(truly_missing)[:5] if truly_missing else []}"
        )

    # Filter metrics - only for nodes in filtered points

    filtered_metrics = [metric for metric in metrics if metric[0] in filtered_point_ids]

    return filtered_points, filtered_edges, filtered_metrics


def filter_isolated_components(
    points: List[List],
    edges: List[List],
    metrics: List[List],
    access_nodes: Optional[List[List]] = None,
    access_edges: Optional[List[List]] = None,
    snap_distance_m: float = 10.0,
    enabled: bool = True,
) -> tuple[List[List], List[List], List[List]]:
    """
    Remove isolated components and snap nearby nodes.

    Process:
    1. Merge base graph with access nodes/edges into unified graph
    2. Add layer/type metadata to all nodes and edges
    3. Snap nearby nodes within snap_distance_m
    4. Keep only the largest connected component

    Returns unified graph with layer information embedded in nodes/edges.

    Args:
        points: base graph nodes [id, lon, lat]
        edges: base graph edges [id, id_way, source, target, name]
        metrics: node metrics
        access_nodes: optional access layer nodes [id, node_type, lon, lat, source_type, source_id, name]
        access_edges: optional access layer edges [id, source, target, source_way_id, road_type, length_m, is_building_link, name]
        snap_distance_m: distance threshold for snapping nodes (meters)
        enabled: whether to apply filtering (useful for disabling in tests)

    Returns:
        tuple of filtered (unified_points, unified_edges, metrics)
        - unified_points: [id, longitude, latitude, node_type, source_type, source_id, name, layer]
        - unified_edges: [id, source, target, id_way, source_way_id, road_type, length_m, is_building_link, name, layer]
    """
    if not enabled:
        # When disabled, still need to convert to unified format
        unified_points = _convert_nodes_to_unified_format(points, access_nodes)
        unified_edges = _convert_edges_to_unified_format(edges, access_edges)
        return unified_points, unified_edges, metrics

    # Track original node metadata
    node_metadata = {}  # Maps node ID to dict with layer, node_type, etc.
    edge_metadata = {}  # Maps edge ID to dict with layer, road_type, etc.

    # Process base graph nodes
    for point in points:
        node_metadata[point[0]] = {
            "layer": "base",
            "node_type": "graph",
            "source_type": "point",
            "source_id": None,
            "name": None,
        }

    # Process access nodes
    if access_nodes:
        for node in access_nodes:
            # Format: [id, node_type, lon, lat, source_type, source_id, name]
            node_metadata[node[0]] = {
                "layer": "access",
                "node_type": node[1] if len(node) > 1 else None,
                "source_type": node[4] if len(node) > 4 else None,
                "source_id": node[5] if len(node) > 5 else None,
                "name": node[6] if len(node) > 6 else None,
            }

    # Process base edges
    for edge in edges:
        edge_metadata[edge[0]] = {
            "layer": "base",
            "id_way": edge[1] if len(edge) > 1 else None,
            "source_way_id": None,
            "road_type": None,
            "length_m": None,
            "is_building_link": False,
            "name": edge[4] if len(edge) > 4 else None,
        }

    # Process access edges
    if access_edges:
        for edge in access_edges:
            # Format: [id, source, target, source_way_id, road_type, length_m, is_building_link, name]
            edge_metadata[edge[0]] = {
                "layer": "access",
                "id_way": None,
                "source_way_id": edge[3] if len(edge) > 3 else None,
                "road_type": edge[4] if len(edge) > 4 else None,
                "length_m": edge[5] if len(edge) > 5 else None,
                "is_building_link": edge[6] if len(edge) > 6 else True,
                "name": edge[7] if len(edge) > 7 else None,
            }

    # Combine all nodes for snapping
    all_nodes = []
    all_nodes.extend(points)
    if access_nodes:
        all_nodes.extend(access_nodes)

    # Combine all edges
    all_edges = edges.copy() if edges else []
    if access_edges:
        all_edges.extend(access_edges)

    print(
        f"Base edges: {len(edges)}, Access edges: {len(access_edges) if access_edges else 0}"
    )
    print(
        f"Base nodes: {len(points)}, Access nodes: {len(access_nodes) if access_nodes else 0}"
    )
    print(f"Total nodes before snapping: {len(all_nodes)}")
    print(f"Total edges before snapping: {len(all_edges)}")

    # Collect all node IDs referenced in edges before snapping
    nodes_in_edges_before = set()
    for edge in all_edges:
        edge_id = edge[0]
        # Use metadata to determine edge type
        is_base = edge_metadata.get(edge_id, {}).get("layer") == "base"

        if is_base and len(edge) > 3:
            # Base edge: [id, id_way, id_src, id_dst, name]
            nodes_in_edges_before.add(edge[2])
            nodes_in_edges_before.add(edge[3])
        elif not is_base and len(edge) > 2:
            # Access edge: [id, id_src, id_dst, ...]
            nodes_in_edges_before.add(edge[1])
            nodes_in_edges_before.add(edge[2])

    all_node_ids_before = {node[0] for node in all_nodes}
    missing_before_snap = nodes_in_edges_before - all_node_ids_before
    print(
        f"DEBUG: Nodes referenced in edges but not in node list BEFORE snapping: {len(missing_before_snap)}, sample: {list(missing_before_snap)[:5]}"
    )

    # Snap nearby nodes together
    merged_nodes, merged_edges, node_mapping = _snap_nearby_nodes(
        all_nodes, all_edges, snap_distance_m, edge_metadata
    )

    print(f"Total nodes after snapping: {len(merged_nodes)}")
    print(f"Total edges after snapping: {len(merged_edges)}")

    # Count access edges after snapping
    access_count_after_snap = sum(
        1
        for edge in merged_edges
        if edge[0] in edge_metadata and edge_metadata[edge[0]].get("layer") == "access"
    )
    print(f"Access edges after snapping: {access_count_after_snap}")

    # Build reverse mapping: representative ID -> list of original IDs it represents
    representative_to_originals = defaultdict(list)
    for original_id, representative_id in node_mapping.items():
        representative_to_originals[representative_id].append(original_id)

    # Merge metadata for nodes that were combined
    # Priority: base > access for layer, but preserve other metadata
    merged_node_metadata = {}
    for representative_id in {node[0] for node in merged_nodes}:
        original_ids = representative_to_originals.get(
            representative_id, [representative_id]
        )

        # Find metadata from originals
        layers = [
            node_metadata.get(oid, {}).get("layer")
            for oid in original_ids
            if oid in node_metadata
        ]

        # Base layer has priority
        if "base" in layers:
            merged_node_metadata[representative_id] = node_metadata.get(
                next(
                    oid
                    for oid in original_ids
                    if node_metadata.get(oid, {}).get("layer") == "base"
                ),
                {
                    "layer": "base",
                    "node_type": "graph",
                    "source_type": "point",
                    "source_id": None,
                    "name": None,
                },
            )
        elif original_ids and original_ids[0] in node_metadata:
            merged_node_metadata[representative_id] = node_metadata[original_ids[0]]
        else:
            merged_node_metadata[representative_id] = {
                "layer": "base",
                "node_type": "graph",
                "source_type": "point",
                "source_id": None,
                "name": None,
            }

    # Update metrics with merged node IDs
    updated_metrics = []
    seen_metric_nodes = set()
    for metric in metrics:
        metric_node_id = metric[0]
        new_node_id = node_mapping.get(metric_node_id, metric_node_id)

        # Avoid duplicate metrics for merged nodes
        if new_node_id not in seen_metric_nodes:
            metric_copy = metric.copy()
            metric_copy[0] = new_node_id
            updated_metrics.append(metric_copy)
            seen_metric_nodes.add(new_node_id)

    print(f"Total nodes before filtering largest component: {len(merged_nodes)}")
    print(f"Total edges before filtering largest component: {len(merged_edges)}")

    # Count layer distribution before filtering
    access_before = sum(
        1
        for edge in merged_edges
        if edge[0] in edge_metadata and edge_metadata[edge[0]].get("layer") == "access"
    )
    base_before = len(merged_edges) - access_before
    print(
        f"Before filtering - Base edges: {base_before}, Access edges: {access_before}"
    )

    # Keep only largest component
    filtered_nodes, filtered_edges, filtered_metrics = _keep_largest_component(
        merged_nodes,
        merged_edges,
        updated_metrics,
        merged_node_metadata,
        edge_metadata,
        node_mapping,
    )
    print(f"Total nodes after filtering largest component: {len(filtered_nodes)}")
    print(f"Total edges after filtering largest component: {len(filtered_edges)}")

    # Count layer distribution after filtering
    access_after = sum(
        1
        for edge in filtered_edges
        if edge[0] in edge_metadata and edge_metadata[edge[0]].get("layer") == "access"
    )
    base_after = len(filtered_edges) - access_after
    print(f"After filtering - Base edges: {base_after}, Access edges: {access_after}")

    # Convert to unified format with metadata
    unified_points = []
    for node in filtered_nodes:
        node_id, lon, lat = _normalize_node(node)
        metadata = merged_node_metadata.get(
            node_id,
            {
                "layer": "base",
                "node_type": "graph",
                "source_type": "point",
                "source_id": None,
                "name": None,
            },
        )

        # Format: [id, longitude, latitude, node_type, source_type, source_id, name, layer]
        unified_points.append(
            [
                node_id,
                lon,
                lat,
                metadata.get("node_type"),
                metadata.get("source_type"),
                metadata.get("source_id"),
                metadata.get("name"),
                metadata.get("layer"),
            ]
        )

    # Convert edges to unified format
    unified_edges = []
    access_edges_count = 0
    base_edges_count = 0
    for edge in filtered_edges:
        edge_id = edge[0]

        # Determine edge format based on ID type
        is_base_edge = isinstance(edge_id, (int, float))

        if is_base_edge:
            # Base edge: [id, id_way, source, target, name]
            source = edge[2] if len(edge) > 2 else None
            target = edge[3] if len(edge) > 3 else None
        else:
            # Access edge: [id, source, target, ...]
            source = edge[1] if len(edge) > 1 else None
            target = edge[2] if len(edge) > 2 else None

        metadata = edge_metadata.get(
            edge_id,
            {
                "layer": "base",
                "id_way": None,
                "source_way_id": None,
                "road_type": None,
                "length_m": None,
                "is_building_link": False,
                "name": None,
            },
        )

        # Format: [id, source, target, id_way, source_way_id, road_type, length_m, is_building_link, name, layer]
        unified_edges.append(
            [
                edge_id,
                source,
                target,
                metadata.get("id_way"),
                metadata.get("source_way_id"),
                metadata.get("road_type"),
                metadata.get("length_m"),
                metadata.get("is_building_link"),
                metadata.get("name"),
                metadata.get("layer"),
            ]
        )

        # Count by layer
        if metadata.get("layer") == "access":
            access_edges_count += 1
        else:
            base_edges_count += 1

    print(
        f"Unified format - Base edges: {base_edges_count}, Access edges: {access_edges_count}"
    )

    return unified_points, unified_edges, filtered_metrics


def _convert_nodes_to_unified_format(
    points: List[List], access_nodes: Optional[List[List]] = None
) -> List[List]:
    """Convert base and access nodes to unified format with metadata."""
    unified = []

    # Convert base nodes
    for point in points:
        # Format: [id, longitude, latitude, node_type, source_type, source_id, name, layer]
        unified.append(
            [
                point[0],
                point[1],
                point[2],
                "graph",
                "point",
                None,
                None,
                "base",
            ]
        )

    # Convert access nodes
    if access_nodes:
        for node in access_nodes:
            # Input: [id, node_type, lon, lat, source_type, source_id, name]
            unified.append(
                [
                    node[0],
                    node[2],
                    node[3],
                    node[1] if len(node) > 1 else None,
                    node[4] if len(node) > 4 else None,
                    node[5] if len(node) > 5 else None,
                    node[6] if len(node) > 6 else None,
                    "access",
                ]
            )

    return unified


def _convert_edges_to_unified_format(
    edges: List[List], access_edges: Optional[List[List]] = None
) -> List[List]:
    """Convert base and access edges to unified format with metadata."""
    unified = []

    # Convert base edges
    for edge in edges:
        # Format: [id, source, target, id_way, source_way_id, road_type, length_m, is_building_link, name, layer]
        unified.append(
            [
                edge[0],
                edge[2] if len(edge) > 2 else None,
                edge[3] if len(edge) > 3 else None,
                edge[1] if len(edge) > 1 else None,
                None,
                None,
                None,
                False,
                edge[4] if len(edge) > 4 else None,
                "base",
            ]
        )

    # Convert access edges
    if access_edges:
        for edge in access_edges:
            # Input: [id, source, target, source_way_id, road_type, length_m, is_building_link, name]
            unified.append(
                [
                    edge[0],
                    edge[1] if len(edge) > 1 else None,
                    edge[2] if len(edge) > 2 else None,
                    None,
                    edge[3] if len(edge) > 3 else None,
                    edge[4] if len(edge) > 4 else None,
                    edge[5] if len(edge) > 5 else None,
                    edge[6] if len(edge) > 6 else True,
                    edge[7] if len(edge) > 7 else None,
                    "access",
                ]
            )

    return unified
