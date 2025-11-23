"""Tests for application.service_facade module."""

from __future__ import annotations

import pytest

from application import service_facade
from domain.schemas import GraphBase


pytestmark = pytest.mark.anyio


@pytest.fixture()
def anyio_backend():
    return "asyncio"


def test_graph_to_zip_delegates_to_archive(monkeypatch):
    captured = {}

    def _fake_zip(graph_base):
        captured["graph"] = graph_base
        return b"zip"

    monkeypatch.setattr(service_facade, "graph_to_zip_archive", _fake_zip)
    graph = GraphBase(
        edges_csv="e",
        points_csv="p",
        ways_properties_csv="w",
        points_properties_csv="pp",
        metrics_csv="m",
    )

    result = service_facade.graph_to_zip(graph)

    assert result == b"zip"
    assert captured["graph"] is graph


async def test_graph_from_ids_returns_none_when_no_polygon(monkeypatch):
    monkeypatch.setattr(service_facade, "polygons_from_region", lambda **_: None)

    result = await service_facade.graph_from_ids(1, [2], "regions")

    assert result == (None, None, None, None, None, None, None)


async def test_graph_from_ids_invokes_graph_service(monkeypatch):
    polygon = object()
    expected = (
        "points",
        "edges",
        "pprop",
        "wprop",
        "metrics",
        "access_nodes",
        "access_edges",
    )

    async def _fake_graph_from_poly(city_id, polygon):  # type: ignore[override]
        return expected

    monkeypatch.setattr(service_facade, "polygons_from_region", lambda **_: polygon)
    monkeypatch.setattr(service_facade, "graph_from_poly", _fake_graph_from_poly)

    result = await service_facade.graph_from_ids(5, [9], "regions")

    assert result == expected
