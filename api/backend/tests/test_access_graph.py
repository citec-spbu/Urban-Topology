import pytest

from infrastructure.osm.osm_handler import (
    _AccessGraphAssembler,
    RawBuilding,
    RawNode,
    RawRoad,
    _polygon_centroid,
)


def _make_nodes():
    nodes = {
        1: RawNode(lon=30.0, lat=60.0),
        2: RawNode(lon=30.001, lat=60.0),
        3: RawNode(lon=30.002, lat=60.0),
        4: RawNode(lon=30.001, lat=60.001),
    }
    nodes[1].neighbors.update({2})
    nodes[1].ways.add(101)

    nodes[2].neighbors.update({1, 3, 4})
    nodes[2].ways.update({101, 102})

    nodes[3].neighbors.update({2})
    nodes[3].ways.add(101)

    nodes[4].neighbors.update({2})
    nodes[4].ways.add(102)
    return nodes


def _make_roads():
    road_main = RawRoad(
        way_id=101,
        node_ids=[1, 2, 3],
        highway="residential",
        name="Main",
        tags={"highway": "residential"},
    )
    road_branch = RawRoad(
        way_id=102,
        node_ids=[2, 4],
        highway="service",
        name="Branch",
        tags={"highway": "service"},
    )
    return [road_main, road_branch]


def test_builds_access_graph_with_building_links():
    nodes = _make_nodes()
    roads = _make_roads()
    building = RawBuilding(
        osm_id=5001,
        longitude=30.0022,
        latitude=60.0,
        name="House",
        tags={"building": "house"},
    )
    assembler = _AccessGraphAssembler(
        nodes=nodes,
        roads=roads,
        buildings=[building],
        snap_distance_m=500,
    )

    node_payloads, edge_payloads = assembler.build()

    building_nodes = [n for n in node_payloads if n["node_type"] == "building"]
    assert len(building_nodes) == 1
    assert any(edge.get("is_building_link") for edge in edge_payloads)
    road_edges = [e for e in edge_payloads if not e.get("is_building_link")]
    assert len(road_edges) >= 2


def test_building_ignored_when_too_far():
    nodes = _make_nodes()
    roads = _make_roads()
    far_building = RawBuilding(
        osm_id=6001,
        longitude=35.0,
        latitude=65.0,
        name=None,
        tags={"building": "house"},
    )
    assembler = _AccessGraphAssembler(
        nodes=nodes,
        roads=roads,
        buildings=[far_building],
        snap_distance_m=50,
    )

    node_payloads, edge_payloads = assembler.build()

    assert all(n["source_id"] != 6001 for n in node_payloads)
    assert not any(e.get("is_building_link") for e in edge_payloads)


def test_polygon_centroid_handles_square():
    coords = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    centroid = _polygon_centroid(coords)
    assert pytest.approx(centroid[0], rel=0.001) == 0.5
    assert pytest.approx(centroid[1], rel=0.001) == 0.5
