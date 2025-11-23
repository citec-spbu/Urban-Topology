"""Unit tests for infrastructure.osm.osm_handler helpers."""

from __future__ import annotations

from math import isclose

import pytest

from infrastructure.osm import osm_handler as handler


@pytest.fixture()
def node_triplet():
    return {
        101: handler.RawNode(lon=30.0, lat=60.0, ways={1}, neighbors={102}),
        102: handler.RawNode(lon=30.0005, lat=60.0005, ways={1}, neighbors={101, 103}),
        103: handler.RawNode(lon=30.001, lat=60.001, ways={1}, neighbors={102}),
    }


def _road_triplet():
    return handler.RawRoad(
        way_id=1,
        node_ids=[101, 102, 103],
        highway="residential",
        name="Main",
        tags={},
    )


def _building(osm_id: int, lon: float, lat: float):
    return handler.RawBuilding(
        osm_id=osm_id,
        longitude=lon,
        latitude=lat,
        name="Дом",
        tags={"building": "house"},
    )


def test_access_graph_assembler_builds_bidirectional_edges(node_triplet):
    assembler = handler._AccessGraphAssembler(  # pylint: disable=protected-access
        nodes=node_triplet,
        roads=[_road_triplet()],
        buildings=[_building(500, 30.0005, 60.0005)],
        snap_distance_m=200.0,
    )

    nodes_payload, edges = assembler.build()

    assert any(p["node_type"] == "building" for p in nodes_payload)
    assert any(e["road_type"] == "residential" for e in edges)
    building_edges = [e for e in edges if e["road_type"] == "building_link"]
    assert len(building_edges) == 2  # forward/backward
    assert {
        building_edges[0]["source_key"],
        building_edges[1]["source_key"],
    }.issuperset({"building:500", "node:102"})


def test_access_graph_assembler_skips_distant_buildings(node_triplet):
    assembler = handler._AccessGraphAssembler(  # pylint: disable=protected-access
        nodes=node_triplet,
        roads=[_road_triplet()],
        buildings=[_building(501, 31.5, 61.5)],
        snap_distance_m=10.0,
    )

    nodes_payload, edges = assembler.build()

    assert all(p["source_type"] != "building" for p in nodes_payload)
    assert all(e["road_type"] != "building_link" for e in edges)


def test_polygon_centroid_handles_open_ring():
    centroid = handler._polygon_centroid(  # pylint: disable=protected-access
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    )
    assert centroid is not None
    assert isclose(centroid[0], 0.5, rel_tol=1e-3)
    assert isclose(centroid[1], 0.5, rel_tol=1e-3)


def test_local_projector_projects_relative_to_origin():
    projector = handler._LocalProjector.from_nodes(  # pylint: disable=protected-access
        [handler.RawNode(lon=10.0, lat=20.0)]
    )
    assert projector is not None
    x, y = projector.project(20.0, 10.0)
    assert isclose(x, 0.0, abs_tol=1e-6)
    assert isclose(y, 0.0, abs_tol=1e-6)

    _, north_shift = projector.project(20.001, 10.0)
    assert north_shift > 0.0
