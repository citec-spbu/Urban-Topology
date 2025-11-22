"""Tests for ingestion utility helpers."""

from __future__ import annotations

import pandas as pd

from application.ingestion import utils


class _FakeIngestionService:
    instances = []
    import_calls = []

    def __init__(self, auth_file_path: str):  # pragma: no cover - simple wiring
        self.auth_file_path = auth_file_path
        self.repo = type(
            "Repo",
            (),
            {
                "import_city_graph": lambda _self, **kwargs: _FakeIngestionService.import_calls.append(
                    kwargs
                )
            },
        )()
        _FakeIngestionService.instances.append(self)

    def import_if_needed(self, row):
        return {"row": row}


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - no special handling
        return False


class _RecordingSession:
    def __init__(self):
        self.added = []
        self.next_id = 1

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", self.next_id)
                self.next_id += 1


class _SessionFactory:
    def __init__(self):
        self.sessions = []

    def begin(self):
        session = _RecordingSession()
        self.sessions.append(session)
        return _SessionContext(session)


def test_add_info_to_db_uses_ingestion_service(monkeypatch):
    monkeypatch.setattr(utils, "IngestionService", _FakeIngestionService)

    df = pd.DataFrame([{"Город": "Demo"}])
    result = utils.add_info_to_db(df.iloc[0])

    assert result["row"]["Город"] == "Demo"
    assert _FakeIngestionService.instances


def test_add_graph_to_db_invokes_repo(monkeypatch):
    _FakeIngestionService.instances.clear()
    _FakeIngestionService.import_calls.clear()
    monkeypatch.setattr(utils, "IngestionService", _FakeIngestionService)

    utils.add_graph_to_db(city_id=1, file_path="/tmp/file.pbf", city_name="City")

    assert _FakeIngestionService.import_calls[0]["city_id"] == 1
    assert _FakeIngestionService.instances[0].auth_file_path == utils.AUTH_FILE_PATH


def test_session_based_helpers_return_ids(monkeypatch):
    factory = _SessionFactory()
    monkeypatch.setattr(utils, "SessionLocal", factory)

    df = pd.DataFrame(
        [
            {
                "Широта": 10,
                "Долгота": 20,
                "Население": 1000,
                "Часовой пояс": "+03",
                "Город": "Demo",
            }
        ]
    )
    point_id = utils.add_point_to_db(df.iloc[0])
    property_id = utils.add_property_to_db(df.iloc[0])
    city_id = utils.add_city_to_db(df.iloc[0], property_id=property_id)

    assert point_id == 1
    assert property_id == 1
    assert city_id == 1


def test_init_db_iterates_all_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(utils, "add_info_to_db", lambda row: calls.append(row))

    df = pd.DataFrame([{"Город": "A"}, {"Город": "B"}])
    utils.init_db(df)

    assert len(calls) == 2
