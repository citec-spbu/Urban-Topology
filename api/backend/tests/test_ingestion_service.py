"""Tests for ingestion service orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from application.ingestion import service as ingestion_service
from infrastructure.repositories import ingestion as ingestion_repo


def _city_row(name: str = "Demo"):
    frame = pd.DataFrame(
        [
            {
                "Город": name,
                "Широта": 10.0,
                "Долгота": 20.0,
                "Население": 1000,
                "Часовой пояс": "+03",
            }
        ]
    )
    return frame.iloc[0]


class _RepoStub:
    def __init__(self, *, existing=None):
        self.existing = existing
        self.created_property = None
        self.created_city = None
        self.import_calls = []

    def find_city_by_name(self, city_name):  # type: ignore[override]
        return self.existing

    def create_city_property(self, **kwargs):  # type: ignore[override]
        self.created_property = kwargs
        return 42

    def create_city(self, *, city_name, property_id):  # type: ignore[override]
        self.created_city = {"city_name": city_name, "property_id": property_id}
        return 99

    def import_city_graph(self, **kwargs):  # type: ignore[override]
        self.import_calls.append(kwargs)


def test_ensure_city_returns_existing(monkeypatch):
    existing = SimpleNamespace(id=5, downloaded=True)
    repo = _RepoStub(existing=existing)
    svc = ingestion_service.IngestionService()
    svc.repo = repo

    city_id, downloaded = svc.ensure_city(_city_row())

    assert (city_id, downloaded) == (5, True)
    assert repo.created_property is None


def test_ensure_city_creates_new_records(monkeypatch):
    repo = _RepoStub(existing=None)
    svc = ingestion_service.IngestionService()
    svc.repo = repo

    city_id, downloaded = svc.ensure_city(_city_row())

    assert city_id == 99
    assert downloaded is False
    assert repo.created_property == {
        "latitude": 10.0,
        "longitude": 20.0,
        "population": 1000,
        "time_zone": "+03",
    }
    assert repo.created_city == {"city_name": "Demo", "property_id": 42}


def test_import_if_needed_skips_when_already_downloaded(monkeypatch, tmp_path):
    svc = ingestion_service.IngestionService()
    svc.repo = _RepoStub(existing=None)
    svc.ensure_city = lambda _: (77, True)  # type: ignore[assignment]

    result = svc.import_if_needed(_city_row())

    assert result == 77
    assert svc.repo.import_calls == []


def test_import_if_needed_runs_import_when_file_exists(monkeypatch, tmp_path):
    file_dir = tmp_path / "pbf"
    file_dir.mkdir()
    city_name = "Sample"
    file_path = file_dir / f"{city_name}.pbf"
    file_path.write_text("mock")
    monkeypatch.setenv("CITIES_PBF_DIR", str(file_dir))

    repo = _RepoStub(existing=None)
    svc = ingestion_service.IngestionService()
    svc.repo = repo
    svc.ensure_city = lambda _: (88, False)  # type: ignore[assignment]

    result = svc.import_if_needed(_city_row(name=city_name))

    assert result == 88
    assert len(repo.import_calls) == 1
    call = repo.import_calls[0]
    assert call["city_id"] == 88
    assert call["file_path"] == str(file_path)
    assert call["city_name"] == city_name
    assert call["required_road_types"] == ingestion_service.REQUIRED_ROAD_TYPES


def test_repository_import_pipeline_invokes_all_steps(monkeypatch):
    repo = ingestion_repo.IngestionRepository()
    calls = []

    def _stub(name):
        def _inner(*args, **kwargs):
            calls.append((name, args, kwargs))

        return _inner

    monkeypatch.setattr(repo, "apply_osmosis_schema", _stub("schema"))
    monkeypatch.setattr(repo, "run_osmosis_and_load", _stub("osmosis"))
    monkeypatch.setattr(repo, "fill_city_graph_from_osm_tables", _stub("fill"))
    monkeypatch.setattr(repo, "populate_access_graph", _stub("access"))
    monkeypatch.setattr(repo, "mark_downloaded", _stub("mark"))

    repo.import_city_graph(
        city_id=123,
        file_path="/tmp/demo.pbf",
        city_name="Demo",
        auth_file_path="/tmp/auth",
        required_road_types=("motorway",),
    )

    assert [name for name, *_ in calls] == [
        "schema",
        "osmosis",
        "fill",
        "access",
        "mark",
    ]
    osmosis_kwargs = calls[1][2]
    assert osmosis_kwargs["file_path"] == "/tmp/demo.pbf"
    assert calls[-1][1][0] == 123
