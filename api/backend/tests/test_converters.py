"""Tests for CSV merging and export helpers."""

from __future__ import annotations

import csv
import io
import zipfile

from application.converters import (
    graph_to_zip_archive,
    graph_to_scheme,
)
from domain.schemas import GraphBase


def _parse(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def test_graph_to_scheme_merges_base_and_access_nodes():
    base_points = [[1, 30.0, 60.0]]
    base_edges = [[10, 100, 1, 2, "Road"]]
    access_nodes = [["a1", "building", 30.1, 60.1, "building", "10", "Дом"]]
    access_edges = [["20", "a1", "1", "", "building_link", "15.5", "True", "Подъезд"]]

    result = graph_to_scheme(
        base_points,
        base_edges,
        [],
        [],
        [],
        access_nodes=access_nodes,
        access_edges=access_edges,
    )

    nodes = _parse(result.points_csv)
    assert len(nodes) == 2
    assert {row["layer"] for row in nodes} == {"base", "access"}

    base_node = next(row for row in nodes if row["layer"] == "base")
    assert base_node["id"] == "1"

    access_node = next(row for row in nodes if row["layer"] == "access")
    assert access_node["node_type"] == "building"
    assert access_node["name"] == "Дом"


def test_graph_to_scheme_merges_base_and_access_edges():
    base_points = [[1, 30.0, 60.0]]
    base_edges = [[10, 100, 1, 2, "Road"]]
    access_edges = [["20", "a1", "1", "", "building_link", "15.5", "True", "Подъезд"]]

    result = graph_to_scheme(
        base_points,
        base_edges,
        [],
        [],
        [],
        access_nodes=None,
        access_edges=access_edges,
    )

    edges = _parse(result.edges_csv)
    assert len(edges) == 2
    assert {row["layer"] for row in edges} == {"base", "access"}

    access_edge = next(row for row in edges if row["layer"] == "access")
    assert access_edge["road_type"] == "building_link"
    assert access_edge["is_building_link"] == "True"


def test_graph_to_zip_archive_writes_all_files():
    graph = GraphBase(
        edges_csv="id,id_way,source,target,name,layer,source_way_id,road_type,length_m,is_building_link\n1,100,1,2,Road,base,,,,",
        points_csv="id,longitude,latitude,layer,node_type,source_type,source_id,name\n1,30.0,60.0,base,,,,",
        ways_properties_csv="id,property,value\n1,name,Main",
        points_properties_csv="id,property,value\n1,type,intersection",
        metrics_csv="id,degree,in_degree,out_degree,eigenvector,betweenness,radius,color\n1,1,1,0,0.1,0.2,0.3,#fff",
    )

    archive = graph_to_zip_archive(graph)
    with zipfile.ZipFile(archive, "r") as zf:
        files = set(zf.namelist())
        assert files == {
            "nodes.csv",
            "edges.csv",
            "points_properties.csv",
            "ways_properties.csv",
            "metrics.csv",
        }
        nodes = zf.read("nodes.csv").decode("utf-8")
        assert "layer" in nodes
        edges = zf.read("edges.csv").decode("utf-8")
        assert "layer" in edges
