"""Convert database objects and metrics into convenient schema/CSV payloads."""

import io
import zipfile
from typing import Iterable, List, Sequence, Optional

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
    """Return a CSV string and DataFrame for the given rows."""
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
    """Convert graph pieces into CSV blobs ready for GraphBase."""
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
