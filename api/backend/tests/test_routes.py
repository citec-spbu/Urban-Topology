"""FastAPI route tests using the built router and dummy service facade."""

from __future__ import annotations

import io
from typing import List

import pytest
from fastapi.testclient import TestClient

from application import service_facade
from domain.schemas import GraphBase


@pytest.fixture()
def graph_components():
    points = [[1, 30.0, 60.0]]
    edges = [[1, 10, 1, 2, "Main"]]
    points_props = [[1, "kind", "intersection"]]
    ways_props = [[10, "lanes", "2"]]
    metrics = [[1, 1, 1, 0, 0.1, 0.2, 0.3, "#fff"]]
    access_nodes = [["a1", "building", 30.1, 60.1, "building", 10, "Дом"]]
    access_edges = [["e1", "a1", 1, None, "building_link", 15.5, True, "Подъезд"]]
    return (
        points,
        edges,
        points_props,
        ways_props,
        metrics,
        access_nodes,
        access_edges,
    )


@pytest.fixture()
def graph_base():
    return GraphBase(
        edges_csv="id,id_way,source,target,name\n1,10,1,2,Main",
        points_csv="id,longitude,latitude\n1,30.0,60.0",
        ways_properties_csv="id,property,value\n10,name,Main",
        points_properties_csv="id,property,value\n1,kind,intersection",
        metrics_csv="id,degree,in_degree,out_degree,eigenvector,betweenness,radius,color\n1,1,1,0,0.1,0.2,0.3,#fff",
        access_nodes_csv="id,node_type,longitude,latitude,source_type,source_id,name\na1,building,30.1,60.1,building,10,Дом",
        access_edges_csv="id,source,target,source_way_id,road_type,length_m,is_building_link,name\n20,a1,1,,building_link,15.5,True,Подъезд",
    )


def _stub_graph_from_ids(graph_data):
    async def _inner(*, city_id: int, regions_ids: List[int], regions):  # type: ignore[override]
        return graph_data

    return _inner


def _bytes_zip(payload: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    buffer.write(payload)
    buffer.seek(0)
    return buffer


def test_city_graph_route_returns_graph(
    monkeypatch, api_client: TestClient, graph_components, graph_base
):
    graph_data = graph_components

    monkeypatch.setattr(
        service_facade,
        "graph_from_ids",
        _stub_graph_from_ids(graph_data),
    )
    monkeypatch.setattr(
        service_facade, "graph_to_scheme", lambda *args, **kwargs: graph_base
    )

    response = api_client.post(
        "/api/city/graph/region/",
        json=[5],
        params={"city_id": 1, "use_cache": "false"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "edges_csv" in payload
    assert payload["edges_csv"].startswith("id,id_way")


def test_city_graph_export_streams_zip(
    monkeypatch, api_client: TestClient, graph_components, graph_base
):
    graph_data = graph_components
    monkeypatch.setattr(
        service_facade,
        "graph_from_ids",
        _stub_graph_from_ids(graph_data),
    )
    monkeypatch.setattr(
        service_facade, "graph_to_scheme", lambda *args, **kwargs: graph_base
    )

    zip_payload = b"PK\x03\x04"
    monkeypatch.setattr(
        service_facade, "graph_to_zip", lambda _: _bytes_zip(zip_payload)
    )

    response = api_client.post(
        "/api/city/graph/region/export/",
        json=[5],
        params={"city_id": 1, "use_cache": "false"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.content == zip_payload


def test_get_city_returns_404(monkeypatch, api_client: TestClient):
    async def _missing_city(*, city_id: int):  # type: ignore[override]
        return None

    monkeypatch.setattr(service_facade, "get_city", _missing_city)

    response = api_client.get("/api/city/", params={"city_id": 123})

    assert response.status_code == 404


def test_city_graph_returns_404_when_points_missing(
    monkeypatch, api_client: TestClient
):
    async def _missing_graph(*args, **kwargs):  # type: ignore[override]
        return (None, None, None, None, None, None, None)

    monkeypatch.setattr(service_facade, "graph_from_ids", _missing_graph)

    response = api_client.post(
        "/api/city/graph/region/",
        json=[1],
        params={"city_id": 1, "use_cache": "false"},
    )

    assert response.status_code == 404


def test_city_graph_returns_422_when_no_edges(monkeypatch, api_client: TestClient):
    async def _empty_graph(*args, **kwargs):  # type: ignore[override]
        return ([], [], [], [], [], [], [])

    monkeypatch.setattr(service_facade, "graph_from_ids", _empty_graph)

    response = api_client.post(
        "/api/city/graph/region/",
        json=[5],
        params={"city_id": 2, "use_cache": "false"},
    )

    assert response.status_code == 422


def test_city_graph_returns_500_on_unexpected_error(
    monkeypatch, api_client: TestClient
):
    async def _raise(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError("boom")

    monkeypatch.setattr(service_facade, "graph_from_ids", _raise)

    response = api_client.post(
        "/api/city/graph/region/",
        json=[7],
        params={"city_id": 9, "use_cache": "false"},
    )

    assert response.status_code == 500


def test_city_graph_export_handles_zip_errors(
    monkeypatch, api_client: TestClient, graph_components, graph_base
):
    monkeypatch.setattr(
        service_facade,
        "graph_from_ids",
        _stub_graph_from_ids(graph_components),
    )
    monkeypatch.setattr(
        service_facade, "graph_to_scheme", lambda *args, **kwargs: graph_base
    )

    def _raise_zip(_):  # pragma: no cover - simple helper
        raise RuntimeError("zip")

    monkeypatch.setattr(service_facade, "graph_to_zip", _raise_zip)

    response = api_client.post(
        "/api/city/graph/region/export/",
        json=[5],
        params={"city_id": 1, "use_cache": "false"},
    )

    assert response.status_code == 500
