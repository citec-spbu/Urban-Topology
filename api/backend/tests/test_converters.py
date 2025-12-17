"""Tests for CSV merging and export helpers."""

from __future__ import annotations

import csv
import io
import zipfile

from application.converters import (
    graph_to_zip_archive,
    merge_edges_csv,
    merge_nodes_csv,
    filter_isolated_components,
    _snap_nearby_nodes,
    _keep_largest_component,
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


def test_snap_nearby_nodes_merges_close_points():
    """Test that nodes within snap distance are merged."""
    # Two nodes very close to each other (< 15m)
    points = [
        [1, 30.0, 60.0],
        [2, 30.00009, 60.00009],  # ~11m away
        [3, 30.1, 60.1],  # ~11km away
    ]
    edges = [
        [101, 55, 1, 2, "Street1"],
        [102, 56, 2, 3, "Street2"],
    ]

    merged_points, merged_edges, node_mapping = _snap_nearby_nodes(
        points, edges, snap_distance_m=15.0
    )

    # Nodes 1 and 2 should be merged
    assert len(merged_points) == 2  # 1+2 merged, plus 3
    assert node_mapping[1] == node_mapping[2]
    assert node_mapping[3] != node_mapping[1]


def test_keep_largest_component_removes_isolated():
    """Test that isolated components are removed."""
    # Create graph with 2 components: one large (1-2-3) and one small (4-5)
    points = [
        [1, 30.0, 60.0],
        [2, 30.1, 60.1],
        [3, 30.2, 60.2],
        [4, 40.0, 70.0],
        [5, 40.1, 70.1],
    ]
    edges = [
        [101, 55, 1, 2, "Street1"],
        [102, 56, 2, 3, "Street2"],
        [103, 57, 4, 5, "Street3"],  # isolated component
    ]
    metrics = [
        [1, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(0,0,255)"],
        [2, 3, 0.6, 0.6, 0.6, 0.6, 1.0, "rgb(50,0,200)"],
        [3, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(100,0,150)"],
        [4, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(150,0,100)"],
        [5, 1, 0.3, 0.3, 0.3, 0.3, 1.0, "rgb(200,0,50)"],
    ]

    filtered_points, filtered_edges, filtered_metrics = _keep_largest_component(
        points, edges, metrics
    )

    # Only the large component should remain
    assert len(filtered_points) == 3
    assert {p[0] for p in filtered_points} == {1, 2, 3}
    assert len(filtered_edges) == 2
    assert len(filtered_metrics) == 3


def test_filter_isolated_components_full_pipeline():
    """Test complete filtering pipeline."""
    points = [
        [1, 30.0, 60.0],
        [2, 30.01, 60.01],
        [3, 40.0, 70.0],
    ]
    edges = [
        [101, 55, 1, 2, "Street1"],
        # Node 3 is isolated
    ]
    metrics = [
        [1, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(0,0,255)"],
        [2, 2, 0.6, 0.6, 0.6, 0.6, 1.0, "rgb(50,0,200)"],
        [3, 0, 0.0, 0.0, 0.0, 0.0, 1.0, "rgb(255,0,0)"],
    ]

    filtered_points, filtered_edges, filtered_metrics = filter_isolated_components(
        points, edges, metrics, snap_distance_m=20.0
    )

    # Node 3 (isolated) should be removed
    node_ids = {p[0] for p in filtered_points}
    assert 3 not in node_ids
    assert len(filtered_metrics) < len(metrics)

    # Check unified format with layer information
    assert len(filtered_points[0]) == 8  # New format with metadata


def test_filter_isolated_components_with_access_nodes_and_edges():
    """Test filtering with access nodes and edges that connect to base graph."""
    # Base graph: nodes 1-2 connected
    points = [
        [1, 30.0, 60.0],
        [2, 30.01, 60.01],
    ]
    edges = [
        [101, 55, 1, 2, "Street1"],
    ]

    # Access layer: building a1 connected to node 1, building a2 isolated
    access_nodes = [
        [
            "a1",
            "building",
            30.0001,
            60.0001,
            "building",
            100,
            "House1",
        ],  # Close to node 1
        ["a2", "building", 40.0, 70.0, "building", 200, "House2"],  # Isolated
    ]
    access_edges = [
        ["e1", "a1", 1, 999, "building_link", 15.5, True, "Link1"],
        # a2 is isolated
    ]

    metrics = [
        [1, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(0,0,255)"],
        [2, 2, 0.6, 0.6, 0.6, 0.6, 1.0, "rgb(50,0,200)"],
    ]

    filtered_points, filtered_edges, filtered_metrics = filter_isolated_components(
        points=points,
        edges=edges,
        metrics=metrics,
        access_nodes=access_nodes,
        access_edges=access_edges,
        snap_distance_m=10.0,
    )

    # All results should be in unified format
    assert len(filtered_points) >= 2

    # Check that unified format includes layer information
    for point in filtered_points:
        assert (
            len(point) == 8
        )  # [id, lon, lat, node_type, source_type, source_id, name, layer]
        assert point[7] in ["base", "access"]  # layer field

    # Isolated building a2 should be removed
    node_ids = {node[0] for node in filtered_points}
    assert "a2" not in node_ids

    # Check edges have unified format
    for edge in filtered_edges:
        assert (
            len(edge) == 10
        )  # [id, source, target, id_way, source_way_id, road_type, length_m, is_building_link, name, layer]
        assert edge[9] in ["base", "access"]  # layer field


def test_filter_isolated_components_preserves_layer_metadata():
    """Test that layer metadata is correctly preserved after filtering."""
    # Base graph nodes: [id, lon, lat]
    points = [
        [1, 30.0, 60.0],
        [2, 30.01, 60.01],
    ]
    edges = [
        [101, 55, 1, 2, "Street1"],
    ]

    # Access nodes: [id, node_type, lon, lat, source_type, source_id, name]
    access_nodes = [
        ["a1", "building", 30.0001, 60.0001, "building", 100, "House1"],
    ]
    access_edges = [
        ["e1", "a1", 1, 999, "building_link", 15.5, True, "Link1"],
    ]

    metrics = [
        [1, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(0,0,255)"],
        [2, 2, 0.6, 0.6, 0.6, 0.6, 1.0, "rgb(50,0,200)"],
    ]

    filtered_points, filtered_edges, filtered_metrics = filter_isolated_components(
        points=points,
        edges=edges,
        metrics=metrics,
        access_nodes=access_nodes,
        access_edges=access_edges,
        snap_distance_m=10.0,
    )

    # Check that we have both base and access layers
    layers = {point[7] for point in filtered_points}
    assert "base" in layers

    # Check that base nodes have correct metadata
    base_nodes = [p for p in filtered_points if p[7] == "base"]
    for node in base_nodes:
        assert node[3] == "graph"  # node_type
        assert node[4] == "point"  # source_type

    # Check that edges have layer information
    edge_layers = {edge[9] for edge in filtered_edges}
    assert "base" in edge_layers


def test_filter_isolated_components_node_merging_with_layers():
    """Test that when base and access nodes merge, metadata is handled correctly."""
    # Base node and access node very close to each other
    points = [
        [1, 30.0, 60.0],
        [2, 30.01, 60.01],
    ]
    edges = [
        [101, 55, 1, 2, "Street1"],
    ]

    # Access node very close to base node 1 (should merge)
    access_nodes = [
        [
            "a1",
            "building",
            30.00001,
            60.00001,
            "building",
            100,
            "House1",
        ],  # ~1m from node 1
    ]
    access_edges = [
        ["e1", "a1", 2, 999, "building_link", 15.5, True, "Link1"],
    ]

    metrics = [
        [1, 2, 0.5, 0.5, 0.5, 0.5, 1.0, "rgb(0,0,255)"],
        [2, 2, 0.6, 0.6, 0.6, 0.6, 1.0, "rgb(50,0,200)"],
    ]

    filtered_points, filtered_edges, filtered_metrics = filter_isolated_components(
        points=points,
        edges=edges,
        metrics=metrics,
        access_nodes=access_nodes,
        access_edges=access_edges,
        snap_distance_m=10.0,
    )

    # When base and access nodes merge, there should be fewer nodes
    assert (
        len(filtered_points) == 2
    ), "Should have 2 nodes after merging (1 merged + node 2)"

    # All nodes should have unified format
    for point in filtered_points:
        assert len(point) == 8

    # Find the merged node (should be close to coordinates of node 1 / a1)
    merged_node = next((p for p in filtered_points if abs(p[1] - 30.0) < 0.001), None)
    assert (
        merged_node is not None
    ), "Should have merged node near coordinates (30.0, 60.0)"

    # The merged node should have base layer (priority rule)
    assert (
        merged_node[7] == "base"
    ), f"Merged node should have 'base' layer, got '{merged_node[7]}'"
