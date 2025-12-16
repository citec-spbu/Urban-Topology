import io
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd
from haversine import Unit, haversine

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
    buffer = io.StringIO()
    df = pd.DataFrame(data, columns=columns)
    df.to_csv(buffer, index=False)
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
    edges_str, _ = list_to_csv_str(edges, ["id", "id_way", "source", "target", "name"])
    points_str, _ = list_to_csv_str(points, ["id", "longitude", "latitude"])
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

    filtered_access_nodes = access_nodes
    filtered_access_edges = access_edges
    if access_nodes and access_edges:
        clustered_nodes, clustered_edges = _cluster_access_nodes(access_nodes, access_edges)
        snapped_nodes, snapped_edges = _snap_access_nodes_to_base(
            clustered_nodes,
            clustered_edges,
            points,
        )
        pruned_nodes, pruned_edges = _prune_access_spurs(snapped_nodes, snapped_edges, points)
        filtered_access_nodes, filtered_access_edges = _filter_access_component(
            pruned_nodes,
            pruned_edges,
            edges,
        )

    access_nodes_str = None
    access_edges_str = None
    if filtered_access_nodes is not None:
        access_nodes_str, _ = list_to_csv_str(
            filtered_access_nodes,
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
    if filtered_access_edges is not None:
        access_edges_str, _ = list_to_csv_str(
            filtered_access_edges,
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

    combined_nodes_str = merge_nodes_csv(points_str, access_nodes_str)
    combined_edges_str = merge_edges_csv(edges_str, access_edges_str)

    return GraphBase(
        edges_csv=edges_str,
        points_csv=points_str,
        ways_properties_csv=wprop_str,
        points_properties_csv=pprop_str,
        metrics_csv=metrics_str,
        access_nodes_csv=access_nodes_str,
        access_edges_csv=access_edges_str,
        combined_nodes_csv=combined_nodes_str,
        combined_edges_csv=combined_edges_str,
    )


def point_obj_to_list(db_record) -> List:
    """Return the point record as a list for serialization."""
    return [db_record.id, db_record.longitude, db_record.latitude]


def edge_obj_to_list(db_record) -> List:
    return [
        db_record.id,
        db_record.id_way,
        db_record.id_src,
        db_record.id_dist,
        db_record.name,
    ]


def record_obj_to_wprop(record) -> List:
    return [record.id_way, record.property, record.value]


def record_obj_to_pprop(record) -> List:
    return [record.id_point, record.property, record.value]


def access_node_obj_to_list(record) -> List:
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
    if point is None:
        return None

    return PointBase(latitude=point.latitude, longitude=point.longitude)


def _csv_to_dataframe(csv_content: Optional[str]) -> Optional[pd.DataFrame]:
    if not csv_content:
        return None

    stripped = csv_content.strip()
    if not stripped:
        return None

    return pd.read_csv(io.StringIO(stripped), dtype=str)


def _is_truthy(value: Any) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _normalize_identifier(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
def _cluster_access_nodes(
    access_nodes: List[List],
    access_edges: List[List],
    max_distance_m: float = 2.0,
) -> Tuple[List[List], List[List]]:
    """Merge nearby connector access nodes to avoid tiny dangling spurs.

    Only non-building access nodes participate. Nodes closer than ``max_distance_m``
    are unioned; a stable representative id (lexicographically smallest in the
    component) is kept. Edges are rewired to representatives; degenerate edges are
    dropped.
    """

    if not access_nodes:
        return access_nodes, access_edges

    deg_tol = max_distance_m / 111_000.0

    node_rows: Dict[str, List] = {}
    coords: Dict[str, Tuple[float, float, str]] = {}
    grid: Dict[Tuple[int, int], List[str]] = {}

    for row in access_nodes:
        if len(row) < 4:
            continue
        node_id = _normalize_identifier(row[0])
        node_type = str(row[1]).lower() if len(row) > 1 else ""
        lon = row[2]
        lat = row[3]
        if node_id is None or pd.isna(lat) or pd.isna(lon):
            continue
        if node_type == "building":
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        node_rows[node_id] = row
        coords[node_id] = (lat_f, lon_f, node_type)
        key = (int(lat_f / deg_tol), int(lon_f / deg_tol))
        grid.setdefault(key, []).append(node_id)

    if len(coords) <= 1:
        return access_nodes, access_edges

    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return parent.get(x, x)

    def union(a: str, b: str):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        rep = ra if ra < rb else rb
        other = rb if ra < rb else ra
        parent[other] = rep
        parent[rep] = rep

    # Объединяем соседние узлы в пределах max_distance_m
    for node_id, (lat, lon, _) in coords.items():
        lat_bucket = int(lat / deg_tol)
        lon_bucket = int(lon / deg_tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other_id in grid.get((lat_bucket + dx, lon_bucket + dy), []):
                    if other_id == node_id:
                        continue
                    olat, olon, _ = coords[other_id]
                    dist = haversine((lat, lon), (olat, olon), unit=Unit.METERS)
                    if dist <= max_distance_m:
                        union(node_id, other_id)

    rep_map: Dict[str, str] = {}
    for node_id in coords:
        rep = find(node_id)
        if rep not in parent:
            parent[rep] = rep
        rep_map[node_id] = rep

    kept_ids: Set[str] = set()
    clustered_nodes: List[List] = []
    for row in access_nodes:
        node_id = _normalize_identifier(row[0])
        if node_id is None:
            continue
        if node_id in rep_map:
            rep = rep_map[node_id]
            if rep in kept_ids:
                continue
            rep_row = node_rows[rep]
            clustered_nodes.append(rep_row)
            kept_ids.add(rep)
        else:
            if node_id in kept_ids:
                continue
            clustered_nodes.append(row)
            kept_ids.add(node_id)

    clustered_edges: List[List] = []
    seen_edges: Set[Tuple[str, str, str]] = set()
    for row in access_edges:
        if len(row) < 3:
            continue
        src = _normalize_identifier(row[1])
        dst = _normalize_identifier(row[2])
        if src is None or dst is None:
            continue
        new_src = rep_map.get(src, src)
        new_dst = rep_map.get(dst, dst)
        if new_src == new_dst:
            continue
        key = (row[0], new_src, new_dst)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        new_row = list(row)
        new_row[1] = new_src
        new_row[2] = new_dst
        clustered_edges.append(new_row)

    return clustered_nodes, clustered_edges


def _snap_access_nodes_to_base(
    access_nodes: List[List],
    access_edges: List[List],
    base_points: List[List],
    max_distance_m: float = 2.0,
) -> Tuple[List[List], List[List]]:
    """Merge access nodes that lie very close to base points to keep the graph connected.

    Nodes within ``max_distance_m`` to a base point are snapped to that base point id.
    Snapped access nodes are removed from the access node list; access edges are
    rewired to the base point ids. This prevents tiny gaps from breaking connectivity.
    """

    if not access_nodes:
        return access_nodes, access_edges

    deg_tol = max_distance_m / 111_000.0  # approximate degree delta for given meters

    base_index: Dict[Tuple[int, int], List[Tuple[str, float, float]]] = {}
    for row in base_points:
        if len(row) < 3:
            continue
        point_id = _normalize_identifier(row[0])
        lon = row[1]
        lat = row[2]
        if point_id is None or pd.isna(lat) or pd.isna(lon):
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        key = (int(lat_f / deg_tol), int(lon_f / deg_tol))
        base_index.setdefault(key, []).append((point_id, lat_f, lon_f))

    def _nearest_base(lat: float, lon: float) -> Optional[str]:
        lat_bucket = int(lat / deg_tol)
        lon_bucket = int(lon / deg_tol)
        best_id: Optional[str] = None
        best_dist = float("inf")
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                bucket = (lat_bucket + dx, lon_bucket + dy)
                for point_id, blat, blon in base_index.get(bucket, []):
                    dist = haversine((lat, lon), (blat, blon), unit=Unit.METERS)
                    if dist < best_dist:
                        best_dist = dist
                        best_id = point_id
        if best_id is None or best_dist > max_distance_m:
            return None
        return best_id

    snap_map: Dict[str, str] = {}
    for row in access_nodes:
        if len(row) < 4:
            continue
        node_id = _normalize_identifier(row[0])
        node_type = str(row[1]).lower() if len(row) > 1 else ""
        lon = row[2]
        lat = row[3]
        if node_id is None or pd.isna(lat) or pd.isna(lon):
            continue
        if node_type == "building":
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        target_id = _nearest_base(lat_f, lon_f)
        if target_id:
            snap_map[node_id] = target_id

    if not snap_map:
        return access_nodes, access_edges

    snapped_nodes = [row for row in access_nodes if _normalize_identifier(row[0]) not in snap_map]

    snapped_edges: List[List] = []
    for row in access_edges:
        if len(row) < 3:
            continue
        src = _normalize_identifier(row[1])
        dst = _normalize_identifier(row[2])
        new_src = snap_map.get(src, src)
        new_dst = snap_map.get(dst, dst)
        if new_src is None or new_dst is None or new_src == new_dst:
            continue
        new_row = list(row)
        new_row[1] = new_src
        new_row[2] = new_dst
        snapped_edges.append(new_row)

    return snapped_nodes, snapped_edges


def _prune_access_spurs(
    access_nodes: List[List],
    access_edges: List[List],
    base_points: List[List],
    max_length_m: float = 3.0,
) -> Tuple[List[List], List[List]]:
    """Remove short dangling access spurs that are not anchored to base or buildings.

    Iteratively drops edges shorter than ``max_length_m`` when they touch a leaf
    access node (degree 1) that is neither a base point nor a building. Removes
    orphaned nodes after edge pruning.
    """

    if not access_edges:
        return access_nodes, access_edges

    base_ids = {_normalize_identifier(row[0]) for row in base_points if row}

    node_rows: Dict[str, List] = {}
    for row in access_nodes:
        if not row:
            continue
        node_id = _normalize_identifier(row[0])
        if node_id:
            node_rows[node_id] = row

    def _length(row: List) -> Optional[float]:
        if len(row) < 6:
            return None
        try:
            return float(row[5]) if row[5] is not None else None
        except (TypeError, ValueError):
            return None

    active_edges = list(range(len(access_edges)))

    while True:
        degrees: Dict[str, int] = {}
        for idx in active_edges:
            edge = access_edges[idx]
            if len(edge) < 3:
                continue
            src = _normalize_identifier(edge[1])
            dst = _normalize_identifier(edge[2])
            if src:
                degrees[src] = degrees.get(src, 0) + 1
            if dst:
                degrees[dst] = degrees.get(dst, 0) + 1

        to_remove: List[int] = []
        for idx in active_edges:
            edge = access_edges[idx]
            if len(edge) < 3:
                continue
            length = _length(edge)
            if length is None or length > max_length_m:
                continue
            src = _normalize_identifier(edge[1])
            dst = _normalize_identifier(edge[2])

            def _is_prunable_leaf(node_id: Optional[str]) -> bool:
                if node_id is None:
                    return False
                if node_id in base_ids:
                    return False
                deg = degrees.get(node_id, 0)
                if deg != 1:
                    return False
                row = node_rows.get(node_id)
                node_type = str(row[1]).lower() if row and len(row) > 1 else ""
                return node_type != "building"

            if _is_prunable_leaf(src) or _is_prunable_leaf(dst):
                to_remove.append(idx)

        if not to_remove:
            break

        active_edges = [idx for idx in active_edges if idx not in to_remove]

    kept_edges: List[List] = []
    used_nodes: Set[str] = set()
    for idx in active_edges:
        edge = access_edges[idx]
        kept_edges.append(edge)
        if len(edge) >= 3:
            src = _normalize_identifier(edge[1])
            dst = _normalize_identifier(edge[2])
            if src:
                used_nodes.add(src)
            if dst:
                used_nodes.add(dst)

    kept_nodes: List[List] = []
    for node_id, row in node_rows.items():
        if node_id in used_nodes:
            kept_nodes.append(row)

    return kept_nodes, kept_edges


def _largest_access_component_ids(
    access_nodes: List[List], access_edges: List[List], base_edges: List[List]
) -> Optional[Set[str]]:
    node_map: Dict[str, List] = {}
    for row in access_nodes:
        if not row:
            continue
        node_id = _normalize_identifier(row[0])
        if not node_id:
            continue
        node_map[node_id] = row

    if len(node_map) <= 1:
        return None

    adjacency: Dict[str, Set[str]] = {node_id: set() for node_id in node_map}
    has_edges = False
    edges_touching_access = False
    anchor_access_nodes: Set[str] = set()

    non_access_nodes: Set[str] = set()
    for edge in base_edges:
        if len(edge) < 4:
            continue
        src = _normalize_identifier(edge[2])
        dst = _normalize_identifier(edge[3])
        if src and src not in node_map:
            non_access_nodes.add(src)
        if dst and dst not in node_map:
            non_access_nodes.add(dst)

    def _add_edge(src: Optional[str], dst: Optional[str]):
        nonlocal has_edges
        nonlocal edges_touching_access
        if not src or not dst:
            return
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)
        has_edges = True
        if src in node_map or dst in node_map:
            edges_touching_access = True
        if src in node_map and dst not in node_map:
            anchor_access_nodes.add(src)
        if dst in node_map and src not in node_map:
            anchor_access_nodes.add(dst)

    for edge in access_edges:
        if len(edge) < 3:
            continue
        src = _normalize_identifier(edge[1])
        dst = _normalize_identifier(edge[2])
        _add_edge(src, dst)

    for edge in base_edges:
        if len(edge) < 4:
            continue
        src = _normalize_identifier(edge[2])
        dst = _normalize_identifier(edge[3])
        _add_edge(src, dst)

    if not has_edges or not edges_touching_access:
        return None

    visited: Set[str] = set()
    best_component: Set[str] = set()
    best_access_count = -1
    best_edge_score = -1
    best_total_nodes = -1
    anchored_access_ids: Set[str] = set()
    has_external_touch = False

    nodes_to_visit = set(adjacency.keys()).union(node_map.keys())
    for node_id in nodes_to_visit:
        if node_id in visited:
            continue

        stack = [node_id]
        component: Set[str] = set()
        edge_score = 0
        total_nodes = 0
        access_count = 0
        has_anchor = False

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            total_nodes += 1
            if current in node_map:
                access_count += 1
            if current in anchor_access_nodes:
                has_anchor = True
            neighbors = adjacency.get(current, set())
            edge_score += len(neighbors)
            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)

        if access_count == 0:
            continue

        if has_anchor:
            anchored_access_ids.update(node_id for node_id in component if node_id in node_map)
            has_external_touch = True

        if (
            total_nodes > best_total_nodes
            or (total_nodes == best_total_nodes and access_count > best_access_count)
            or (
                total_nodes == best_total_nodes
                and access_count == best_access_count
                and edge_score > best_edge_score
            )
        ):
            best_component = component
            best_access_count = access_count
            best_edge_score = edge_score
            best_total_nodes = total_nodes

    if has_external_touch:
        return set(node_map.keys())

    if not best_component or best_access_count == len(node_map):
        return None

    return {node_id for node_id in best_component if node_id in node_map}


def _filter_access_component(
    access_nodes: List[List], access_edges: List[List], base_edges: List[List]
) -> Tuple[List[List], List[List]]:
    keep_ids = _largest_access_component_ids(access_nodes, access_edges, base_edges)
    if not keep_ids:
        return access_nodes, access_edges

    node_ids = {_normalize_identifier(row[0]) for row in access_nodes if row}
    remove_ids = {node_id for node_id in node_ids if node_id and node_id not in keep_ids}

    filtered_nodes = [row for row in access_nodes if _normalize_identifier(row[0]) in keep_ids]
    filtered_edges: List[List] = []
    for row in access_edges:
        if len(row) < 3:
            continue
        src = _normalize_identifier(row[1])
        dst = _normalize_identifier(row[2])
        if src in remove_ids or dst in remove_ids:
            continue
        filtered_edges.append(row)

    return filtered_nodes, filtered_edges


def _export_csv_from_frames(frames: List[pd.DataFrame]) -> str:
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
        access_df["layer"] = access_df["node_type"].apply(
            lambda value: "building"
            if isinstance(value, str) and value.lower() == "building"
            else "connector"
        )
        frames.append(access_df[NODE_EXPORT_COLUMNS])

    return _export_csv_from_frames(frames)


def merge_edges_csv(edges_csv: str, access_edges_csv: Optional[str]) -> str:
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
        access_df["layer"] = access_df["is_building_link"].apply(
            lambda value: "building" if _is_truthy(value) else "connector"
        )
        frames.append(access_df[EDGE_EXPORT_COLUMNS])

    return _export_csv_from_frames(frames)


def graph_to_zip_archive(graph: GraphBase) -> io.BytesIO:
    buffer = io.BytesIO()
    nodes_csv = graph.combined_nodes_csv or merge_nodes_csv(
        graph.points_csv, graph.access_nodes_csv
    )
    edges_csv = graph.combined_edges_csv or merge_edges_csv(
        graph.edges_csv, graph.access_edges_csv
    )

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nodes.csv", nodes_csv)
        archive.writestr("edges.csv", edges_csv)
        archive.writestr("points_properties.csv", graph.points_properties_csv or "")
        archive.writestr("ways_properties.csv", graph.ways_properties_csv or "")
        archive.writestr("metrics.csv", graph.metrics_csv or "")

    buffer.seek(0)
    return buffer
