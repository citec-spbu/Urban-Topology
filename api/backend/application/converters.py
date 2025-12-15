import io
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd

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
        filtered_access_nodes, filtered_access_edges = _filter_access_component(
            access_nodes,
            access_edges,
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


def _largest_access_component_ids(
    access_nodes: List[List], access_edges: List[List]
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
    has_valid_edges = False
    for edge in access_edges:
        if len(edge) < 3:
            continue
        src = _normalize_identifier(edge[1])
        dst = _normalize_identifier(edge[2])
        if not src or not dst:
            continue
        if src not in node_map or dst not in node_map:
            continue
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)
        has_valid_edges = True

    if not has_valid_edges:
        return None

    visited: Set[str] = set()
    largest_component: Set[str] = set()
    largest_edge_score = -1

    for node_id in node_map:
        if node_id in visited:
            continue
        stack = [node_id]
        component: Set[str] = set()
        edge_score = 0
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            neighbors = adjacency.get(current, set())
            edge_score += len(neighbors)
            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)
        if len(component) > len(largest_component) or (
            len(component) == len(largest_component) and edge_score > largest_edge_score
        ):
            largest_component = component
            largest_edge_score = edge_score

    if not largest_component or len(largest_component) == len(node_map):
        return None

    return largest_component


def _filter_access_component(
    access_nodes: List[List], access_edges: List[List]
) -> Tuple[List[List], List[List]]:
    keep_ids = _largest_access_component_ids(access_nodes, access_edges)
    if not keep_ids:
        return access_nodes, access_edges

    filtered_nodes = [row for row in access_nodes if _normalize_identifier(row[0]) in keep_ids]
    filtered_edges: List[List] = []
    for row in access_edges:
        if len(row) < 3:
            continue
        src = _normalize_identifier(row[1])
        dst = _normalize_identifier(row[2])
        if src in keep_ids and dst in keep_ids:
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
