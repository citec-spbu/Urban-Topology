"""Tests for graph_service metric helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon

from application import graph_service


pytestmark = pytest.mark.anyio


@pytest.fixture()
def anyio_backend():
    return "asyncio"


def test_get_color_from_blue_to_red_handles_constant_range():
    color = graph_service.get_color_from_blue_to_red(5.0, 5.0, 5.0)
    assert color == "rgb(0, 0, 0)"


def test_get_radius_based_on_metric_scales_value():
    assert graph_service.get_radius_based_on_metric(0.0) == 1
    assert graph_service.get_radius_based_on_metric(0.5) == 6


async def test_calc_metrics_returns_empty_when_no_points():
    metrics = await graph_service.calc_metrics([], [], set())
    assert metrics == []


async def test_calc_metrics_builds_metrics_for_simple_graph():
    points = [[1, 30.0, 60.0], [2, 31.0, 61.0]]
    edges = [
        [10, 100, 1, 2, "Road"],
    ]
    oneway_ids = set()

    metrics = await graph_service.calc_metrics(points, edges, oneway_ids)

    assert len(metrics) == 2
    ids = {row[0] for row in metrics}
    assert ids == {1, 2}
    # Ensure betweenness normalization and color computation happened
    colors = {row[-1] for row in metrics}
    assert all(color.startswith("rgb(") for color in colors)


class _CityRepoMissing:
    async def by_id(self, city_id):  # pragma: no cover - helper
        return None


class _CityRow(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__dict__.update(kwargs)


class _GraphRepoStub:
    def __init__(self, *, prop_id_name=None, prop_id_highway=None):
        self._name = prop_id_name
        self._highway = prop_id_highway

    async def property_id(self, key):  # pragma: no cover - simple stub
        return self._name if key == "name" else self._highway


@pytest.mark.anyio
async def test_graph_from_poly_returns_none_when_city_missing(monkeypatch):
    monkeypatch.setattr(graph_service, "CityRepository", lambda: _CityRepoMissing())

    poly = Polygon([(0, 0), (1, 0), (1, 1)])
    result = await graph_service.graph_from_poly(1, poly)

    assert result[0] is None


class _LoopStub:
    def __init__(self, exc: Exception | None = None):
        self.exc = exc
        self.calls = []

    async def run_in_executor(self, executor, func, *args):
        self.calls.append((executor, func, args))
        if self.exc:
            raise self.exc
        return None


class _CityRepoSequence:
    def __init__(self, responses):
        self._responses = list(responses)
        self._index = 0

    async def by_id(self, city_id):
        if self._index >= len(self._responses):  # pragma: no cover - safety
            return self._responses[-1]
        value = self._responses[self._index]
        self._index += 1
        return value


class _GraphRepoComplete:
    def __init__(self):
        self._point_calls = []

    async def property_id(self, key):
        return {"name": 11, "highway": 22}.get(key)

    async def points_in_polygon(self, *args, **kwargs):
        self._point_calls.append((args, kwargs))
        return [SimpleNamespace(id=1, longitude=30.0, latitude=60.0)]

    async def edges_in_polygon(self, *args, **kwargs):
        return [
            SimpleNamespace(id=5, id_way=7, id_src=1, id_dist=2, name="Road"),
        ]

    async def way_props(self, ids):
        return [SimpleNamespace(id_way=next(iter(ids)), property="name", value="Main")]

    def point_props_via_temp(self, ids):
        return [
            SimpleNamespace(id_point=next(iter(ids)), property="kind", value="cross")
        ]

    async def oneway_ids(self, **kwargs):
        return {999}

    async def access_nodes_in_polygon(self, *args, **kwargs):
        return [
            SimpleNamespace(
                id="a1",
                node_type="building",
                longitude=31.0,
                latitude=61.0,
                source_type="building",
                source_id=10,
                name="Дом",
            )
        ]

    async def access_edges_in_polygon(self, *args, **kwargs):
        return [
            SimpleNamespace(
                id="e1",
                id_src="a1",
                id_dst=1,
                source_way_id=7,
                road_type="service",
                length_m=5.5,
                is_building_link=True,
                name="link",
            )
        ]


@pytest.mark.anyio
async def test_graph_from_poly_returns_none_when_import_fails(monkeypatch, tmp_path):
    city = _CityRow(city_name="AsyncCity", downloaded=False)

    class _CityRepo:
        async def by_id(self, city_id):
            return city

    loop = _LoopStub(exc=RuntimeError("import"))
    pbf_path = tmp_path / "AsyncCity.pbf"
    pbf_path.write_text("data")

    monkeypatch.setattr(graph_service, "CityRepository", lambda: _CityRepo())
    monkeypatch.setattr(graph_service, "city_pbf_path", lambda _: pbf_path)
    monkeypatch.setattr(graph_service.asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(graph_service, "add_graph_to_db", lambda *args, **kwargs: None)

    result = await graph_service.graph_from_poly(5, Polygon([(0, 0), (1, 0), (1, 1)]))

    assert result[0] is None
    assert len(loop.calls) == 1


@pytest.mark.anyio
async def test_graph_from_poly_returns_none_when_import_leaves_city_undownloaded(
    monkeypatch, tmp_path
):
    rows = [
        _CityRow(city_name="RetryCity", downloaded=False),
        _CityRow(city_name="RetryCity", downloaded=False),
    ]

    loop = _LoopStub()
    pbf_path = tmp_path / "RetryCity.pbf"
    pbf_path.write_text("data")

    monkeypatch.setattr(
        graph_service, "CityRepository", lambda: _CityRepoSequence(rows)
    )
    monkeypatch.setattr(graph_service, "city_pbf_path", lambda _: pbf_path)
    monkeypatch.setattr(graph_service.asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(graph_service, "add_graph_to_db", lambda *args, **kwargs: None)

    result = await graph_service.graph_from_poly(7, Polygon([(0, 0), (1, 0), (1, 1)]))

    assert result[0] is None
    assert len(loop.calls) == 1


@pytest.mark.anyio
async def test_graph_from_poly_returns_full_payload(monkeypatch):
    downloaded_city = _CityRow(city_name="Ready", downloaded=True)

    class _CityRepo:
        async def by_id(self, city_id):
            return downloaded_city

    monkeypatch.setattr(graph_service, "CityRepository", lambda: _CityRepo())
    monkeypatch.setattr(graph_service, "GraphRepository", lambda: _GraphRepoComplete())

    async def _fake_metrics(points, edges, oneway_ids):
        return [
            [point[0], 1, 0.5, 0.5, 0.1, 0.2, 1.5, "rgb(0, 0, 0)"] for point in points
        ]

    monkeypatch.setattr(graph_service, "calc_metrics", _fake_metrics)

    result = await graph_service.graph_from_poly(3, Polygon([(0, 0), (1, 0), (1, 1)]))

    (points, edges, points_prop, ways_prop, metrics, access_nodes, access_edges) = (
        result
    )

    assert points == [[1, 30.0, 60.0]]
    assert edges[0][:4] == [5, 7, 1, 2]
    assert points_prop == [[1, "kind", "cross"]]
    assert ways_prop == [[7, "name", "Main"]]
    assert metrics[0][0] == 1
    assert access_nodes[0][0] == "a1"
    assert access_edges[0][0] == "e1"


@pytest.mark.anyio
async def test_graph_from_poly_handles_missing_pbf(monkeypatch, tmp_path):
    missing_city = _CityRow(city_name="TestCity", downloaded=False)

    class _CityRepo:
        async def by_id(self, city_id):
            return missing_city

    monkeypatch.setattr(graph_service, "CityRepository", lambda: _CityRepo())
    monkeypatch.setattr(
        graph_service, "city_pbf_path", lambda name: tmp_path / f"{name}.pbf"
    )

    poly = Polygon([(0, 0), (1, 0), (1, 1)])
    result = await graph_service.graph_from_poly(1, poly)

    assert result[0] is None


@pytest.mark.anyio
async def test_graph_from_poly_aborts_without_property_id(monkeypatch):
    downloaded_city = _CityRow(city_name="Test", downloaded=True)

    class _CityRepo:
        async def by_id(self, city_id):
            return downloaded_city

    class _GraphRepo(_GraphRepoStub):
        def __init__(self):
            super().__init__(prop_id_name=None, prop_id_highway=1)

    monkeypatch.setattr(graph_service, "CityRepository", lambda: _CityRepo())
    monkeypatch.setattr(graph_service, "GraphRepository", lambda: _GraphRepo())

    poly = Polygon([(0, 0), (1, 0), (1, 1)])
    result = await graph_service.graph_from_poly(1, poly)

    assert result[0] is None
