"""Validate ingestion repository interactions with the database."""

from __future__ import annotations

from typing import List, Tuple

import pytest
from sqlalchemy import text

from infrastructure import database as db
from infrastructure.repositories import ingestion as ingestion_repo


@pytest.fixture()
def sqlite_access_db(tmp_path):
    """Isolated SQLite test database without mutating global configuration.

    Uses create_test_database to avoid calling configure_database twice (guarded).
    The ingestion repository's engine / SessionLocal are temporarily pointed at
    the isolated test engine for the duration of the test.
    """
    new_url = f"sqlite:///{tmp_path}/ingestion.db"
    test_engine, test_session_factory, _test_db = db.create_test_database(
        new_url, echo=False
    )
    # Point repository module-level handles to the isolated engine/session.
    orig_engine = ingestion_repo.engine
    orig_session_local = ingestion_repo.SessionLocal
    ingestion_repo.engine = test_engine
    ingestion_repo.SessionLocal = test_session_factory

    # Create all application tables needed by populate_access_graph plus City tables.
    db.metadata.create_all(test_engine)

    with test_engine.begin() as conn:
        conn.execute(
            db.CityPropertyAsync.insert().values(id=1, c_latitude=0.0, c_longitude=0.0)
        )
        conn.execute(
            db.CityAsync.insert().values(
                id=1,
                id_property=1,
                city_name="Demo",
                downloaded=False,
            )
        )
        # Minimal Osmosis-compatible support tables required for later tag/property inserts
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS node_tags (node_id INTEGER, k TEXT, v TEXT);"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS way_tags (way_id INTEGER, k TEXT, v TEXT);"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS way_nodes (way_id INTEGER, node_id INTEGER, sequence_id INTEGER);"
            )
        )

    try:
        yield ingestion_repo  # provides .engine for test queries
    finally:
        # Restore original repository bindings
        ingestion_repo.engine = orig_engine
        ingestion_repo.SessionLocal = orig_session_local
        test_engine.dispose()


def test_populate_access_graph_persists_access_entities(
    sqlite_access_db, monkeypatch, tmp_path
):
    repo = ingestion_repo.IngestionRepository()
    captured_paths: List[str] = []

    long_name = "N" * 150
    nodes_payload = [
        {
            "source_type": "node",
            "source_id": 101,
            "node_type": "driveway",
            "longitude": 30.1,
            "latitude": 60.2,
            "name": long_name,
            "tags": {"kind": "entrance"},
        },
        {
            "source_type": "node",
            "source_id": 102,
            "node_type": "intersection",
            "longitude": 30.2,
            "latitude": 60.3,
            "name": "Secondary",
            "tags": None,
        },
    ]
    edges_payload = [
        {
            "source_key": "node:101",
            "target_key": "node:102",
            "source_way_id": 555,
            "road_type": "service",
            "length_m": 12.5,
            "is_building_link": True,
            "name": "Entry",
        }
    ]

    def _fake_builder(osm_file_path: str) -> Tuple[list, list]:
        captured_paths.append(osm_file_path)
        return nodes_payload, edges_payload

    monkeypatch.setattr(ingestion_repo, "build_access_graph", _fake_builder)

    pbf_path = tmp_path / "demo.pbf"
    repo.populate_access_graph(city_id=1, file_path=str(pbf_path))

    with sqlite_access_db.engine.begin() as conn:
        nodes = conn.execute(db.AccessNodeAsync.select()).fetchall()
        edges = conn.execute(db.AccessEdgeAsync.select()).fetchall()

    assert captured_paths == [str(pbf_path)]
    assert len(nodes) == 2
    long_node = max(nodes, key=lambda n: len((n.name or "")))
    assert long_node.name == long_name[:128]
    assert long_node.tags is not None and "kind" in long_node.tags
    assert len(edges) == 1
    edge = edges[0]
    assert edge.road_type == "service"
    assert bool(edge.is_building_link) is True
    assert edge.id_src != edge.id_dst

    # ensure subsequent runs clear previous data
    repo.populate_access_graph(city_id=1, file_path=str(pbf_path))
    with sqlite_access_db.engine.begin() as conn:
        node_count = conn.execute(
            text('SELECT COUNT(*) FROM "AccessNodes"')
        ).scalar_one()
        edge_count = conn.execute(
            text('SELECT COUNT(*) FROM "AccessEdges"')
        ).scalar_one()
    assert node_count == 2
    assert edge_count == 1
