"""Validate ingestion repository interactions with the database."""

from __future__ import annotations

from typing import List, Tuple

import pytest
from sqlalchemy import text

from infrastructure import database as db
from infrastructure.repositories import ingestion as ingestion_repo


@pytest.fixture()
def sqlite_access_db(tmp_path):
    prev_url = db.DATABASE_URL
    new_url = f"sqlite:///{tmp_path}/ingestion.db"
    db.configure_database(new_url, echo=False)
    ingestion_repo.engine = db.engine
    ingestion_repo.SessionLocal = db.SessionLocal
    db.metadata.create_all(db.engine)

    with db.engine.begin() as conn:
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
        # Minimal Osmosis-compatible support tables
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

    yield db

    db.configure_database(prev_url, echo=False)
    ingestion_repo.engine = db.engine
    ingestion_repo.SessionLocal = db.SessionLocal


def test_populate_access_graph_persists_access_entities(sqlite_access_db, monkeypatch):
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

    repo.populate_access_graph(city_id=1, file_path="/tmp/demo.pbf")

    with sqlite_access_db.engine.begin() as conn:
        nodes = conn.execute(db.AccessNodeAsync.select()).fetchall()
        edges = conn.execute(db.AccessEdgeAsync.select()).fetchall()

    assert captured_paths == ["/tmp/demo.pbf"]
    assert len(nodes) == 2
    assert nodes[0].name == long_name[:128]
    assert nodes[0].tags is not None and "kind" in nodes[0].tags
    assert len(edges) == 1
    edge = edges[0]
    assert edge.road_type == "service"
    assert bool(edge.is_building_link) is True
    assert edge.id_src != edge.id_dst

    # ensure subsequent runs clear previous data
    repo.populate_access_graph(city_id=1, file_path="/tmp/demo.pbf")
    with sqlite_access_db.engine.begin() as conn:
        node_count = conn.execute(
            text('SELECT COUNT(*) FROM "AccessNodes"')
        ).scalar_one()
        edge_count = conn.execute(
            text('SELECT COUNT(*) FROM "AccessEdges"')
        ).scalar_one()
    assert node_count == 2
    assert edge_count == 1
