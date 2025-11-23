"""Pytest fixtures for backend tests."""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import build_router


class DummyLogger:
    """Minimal logger compatible with build_router expectations."""

    def catch(self, **kwargs):  # type: ignore[override]
        def decorator(func):
            return func

        return decorator

    def info(self, *args, **kwargs):  # pragma: no cover - no-op
        return None

    def warning(self, *args, **kwargs):  # pragma: no cover - no-op
        return None

    def error(self, *args, **kwargs):  # pragma: no cover - no-op
        return None

    def exception(self, *args, **kwargs):  # pragma: no cover - no-op
        return None


@pytest.fixture()
def api_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with router mounted and state prepared."""

    app = FastAPI()
    logger = DummyLogger()
    app.include_router(build_router(logger))
    app.state.regions_df = object()
    app.state.cities_info = object()

    # Ensure cache writes land in a temp directory during tests
    monkeypatch.chdir(tmp_path)

    with TestClient(app) as client:
        yield client
