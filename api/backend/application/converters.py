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
    "layer",
    "node_type",
    "source_type",
    "source_id",
    "name",
]

EDGE_EXPORT_COLUMNS = [
    "id",
    "id_way",
    "source",
    "target",
    "name",
    "layer",
    "source_way_id",
    "road_type",
    "length_m",
    "is_building_link",
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
    # points: [id, longitude, latitude]
    # need: [id, longitude, latitude, layer, node_type, source_type, source_id, name]
    base_points_with_layer = [p + ["base", "", "", "", ""] for p in points]

    combined_points = base_points_with_layer[:]
    if access_nodes:
        for node in access_nodes:
            # node: [id, node_type, longitude, latitude, source_type, source_id, name]
            # need: [id, longitude, latitude, layer, node_type, source_type, source_id, name]
            combined_points.append(
                [
                    node[0],  # id
                    node[2],  # longitude
                    node[3],  # latitude
                    "access",  # layer
                    node[1],  # node_type
                    node[4] if len(node) > 4 else "",  # source_type
                    node[5] if len(node) > 5 else "",  # source_id
                    node[6] if len(node) > 6 else "",  # name
                ]
            )

    points_str, _ = list_to_csv_str(
        combined_points,
        [
            "id",
            "longitude",
            "latitude",
            "layer",
            "node_type",
            "source_type",
            "source_id",
            "name",
        ],
    )

    base_edges_with_layer = [e + ["base", "", "", "", ""] for e in edges]

    combined_edges = base_edges_with_layer[:]
    if access_edges:
        for edge in access_edges:
            # edge: [id, source, target, source_way_id, road_type, length_m, is_building_link, name]
            # need: [id, id_way, source, target, name, layer, source_way_id, road_type, length_m, is_building_link]
            combined_edges.append(
                [
                    edge[0],  # id
                    "",  # id_way (пусто для access)
                    edge[1],  # source
                    edge[2],  # target
                    edge[7] if len(edge) > 7 else "",  # name
                    "access",  # layer
                    edge[3] if len(edge) > 3 else "",  # source_way_id
                    edge[4] if len(edge) > 4 else "",  # road_type
                    edge[5] if len(edge) > 5 else "",  # length_m
                    edge[6] if len(edge) > 6 else "",  # is_building_link
                ]
            )

    edges_str, _ = list_to_csv_str(
        combined_edges,
        [
            "id",
            "id_way",
            "source",
            "target",
            "name",
            "layer",
            "source_way_id",
            "road_type",
            "length_m",
            "is_building_link",
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


def graph_to_zip_archive(graph: GraphBase) -> io.BytesIO:
    """Pack CSV payloads into an in-memory ZIP archive."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nodes.csv", graph.points_csv or "")
        archive.writestr("edges.csv", graph.edges_csv or "")
        archive.writestr("points_properties.csv", graph.points_properties_csv or "")
        archive.writestr("ways_properties.csv", graph.ways_properties_csv or "")
        archive.writestr("metrics.csv", graph.metrics_csv or "")

    buffer.seek(0)
    return buffer
