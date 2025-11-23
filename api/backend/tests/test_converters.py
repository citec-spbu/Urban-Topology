"""Tests for CSV merging and export helpers."""

from __future__ import annotations

import csv
import io
import zipfile

from application.converters import (
    graph_to_zip_archive,
    merge_edges_csv,
    merge_nodes_csv,
)
from domain.schemas import GraphBase


def _parse(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def test_merge_nodes_csv_preserves_layers():
    base_nodes = "id,longitude,latitude\n1,30.0,60.0"
    access_nodes = (
        "id,node_type,longitude,latitude,source_type,source_id,name\n"
        "a1,building,30.1,60.1,building,10,Дом"
    )

    merged = merge_nodes_csv(base_nodes, access_nodes)
    rows = _parse(merged)

    assert {row["layer"] for row in rows} == {"base", "access"}
    base_row = next(row for row in rows if row["layer"] == "base")
    assert base_row["node_type"] == "graph"
    access_row = next(row for row in rows if row["layer"] == "access")
    assert access_row["node_type"] == "building"


def test_merge_edges_csv_combines_metadata():
    base_edges = "id,source,target,id_way,name\n10,1,2,55,Main"
    access_edges = (
        "id,source,target,source_way_id,road_type,length_m,is_building_link,name\n"
        "20,a1,1,,building_link,15.5,True,Подъезд"
    )

    merged = merge_edges_csv(base_edges, access_edges)
    rows = _parse(merged)

    assert len(rows) == 2
    assert {row["layer"] for row in rows} == {"base", "access"}
    access_row = next(row for row in rows if row["layer"] == "access")
    assert access_row["road_type"] == "building_link"
    base_row = next(row for row in rows if row["layer"] == "base")
    assert base_row["is_building_link"] == "False"


def test_graph_to_zip_archive_writes_all_files():
    graph = GraphBase(
        edges_csv="id,source,target\n1,1,2",
        points_csv="id,longitude,latitude\n1,30.0,60.0",
        ways_properties_csv="id,property,value\n1,name,Main",
        points_properties_csv="id,property,value\n1,type,intersection",
        metrics_csv="id,degree,in_degree,out_degree,eigenvector,betweenness,radius,color\n1,1,1,0,0.1,0.2,0.3,#fff",
        access_nodes_csv="id,node_type,longitude,latitude,source_type,source_id,name\na1,building,30.1,60.1,building,10,Дом",
        access_edges_csv="id,source,target,source_way_id,road_type,length_m,is_building_link,name\n20,a1,1,,building_link,15.5,True,Подъезд",
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
        assert "building_link" in edges
