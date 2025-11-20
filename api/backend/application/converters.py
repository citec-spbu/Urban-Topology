"""Convert database objects and metrics into convenient schema/CSV payloads."""

import io
from typing import Iterable, List, Sequence, Optional

import pandas as pd

from domain.schemas import GraphBase, PointBase


def list_to_csv_str(data: Iterable[Sequence], columns: List[str]):
    """Return a CSV string and DataFrame for the given rows."""
    buffer = io.StringIO()
    df = pd.DataFrame(data, columns=columns)
    df.to_csv(buffer, index=False)
    return buffer.getvalue(), df


def graph_to_scheme(points, edges, pprop, wprop, metrics) -> GraphBase:
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


def point_to_scheme(point) -> Optional[PointBase]:
    """Convert a point ORM object into a PointBase schema."""
    if point is None:
        return None

    return PointBase(latitude=point.latitude, longitude=point.longitude)
