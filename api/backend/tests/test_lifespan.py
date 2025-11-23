"""Tests for FastAPI lifespan hooks."""

from __future__ import annotations

from fastapi import FastAPI
import pandas as pd
import pytest

from app import lifespan as lifespan_module


class DummyLogger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def info(self, message, *args):  # pragma: no cover - only verify via state
        self.infos.append((message, args))

    def error(self, message, *args):  # pragma: no cover
        self.errors.append((message, args))

    def exception(self, message, *args):  # pragma: no cover
        self.errors.append((message, args))

    def catch(self, **kwargs):  # pragma: no cover - not used here
        def decorator(func):
            return func

        return decorator


@pytest.mark.anyio
async def test_lifespan_loads_data(monkeypatch, tmp_path):
    regions_file = tmp_path / "regions.json"
    cities_file = tmp_path / "cities.csv"
    regions_file.write_text("{}", encoding="utf-8")
    cities_file.write_text("city,lat\n", encoding="utf-8")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    loaded_regions = object()
    loaded_cities = pd.DataFrame([{"Город": "Test"}])
    monkeypatch.setattr(lifespan_module.gpd, "read_file", lambda path: loaded_regions)
    monkeypatch.setattr(lifespan_module.pd, "read_csv", lambda path: loaded_cities)

    connect_called = []
    disconnect_called = []

    async def fake_connect():
        connect_called.append(True)

    async def fake_disconnect():
        disconnect_called.append(True)

    monkeypatch.setattr(lifespan_module.database, "connect", fake_connect)
    monkeypatch.setattr(lifespan_module.database, "disconnect", fake_disconnect)

    init_calls = []
    monkeypatch.setattr(
        lifespan_module.service_facade,
        "init_db",
        lambda cities_info: init_calls.append(cities_info),
    )

    app = FastAPI()
    logger = DummyLogger()
    lifespan = lifespan_module.build_lifespan(logger)

    async with lifespan(app):
        assert app.state.regions_df is loaded_regions
        assert app.state.cities_info is loaded_cities

    assert connect_called
    assert disconnect_called
    assert init_calls == [loaded_cities]


@pytest.mark.anyio
async def test_lifespan_missing_regions_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    logger = DummyLogger()
    lifespan = lifespan_module.build_lifespan(logger)

    with pytest.raises(FileNotFoundError):
        async with lifespan(FastAPI()):
            pass
