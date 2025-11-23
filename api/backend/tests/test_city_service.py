"""Unit tests for application.city_service helpers."""

from __future__ import annotations

import pytest

from application import city_service


pytestmark = pytest.mark.anyio


@pytest.fixture()
def anyio_backend():
    return "asyncio"


class _FakeCityRepo:
    """Simple stub that mimics CityRepository async interface."""

    def __init__(self, *, cities, properties, city_by_id=None):
        self._cities = cities
        self._properties = properties
        self._city_by_id = city_by_id or {}
        self.property_calls = []
        self.list_calls = []
        self.by_id_calls = []

    async def property_by_city(self, prop_id):  # type: ignore[override]
        self.property_calls.append(prop_id)
        return self._properties.get(prop_id)

    async def list(self, *, page: int, per_page: int):  # type: ignore[override]
        self.list_calls.append((page, per_page))
        return self._cities

    async def by_id(self, city_id: int):  # type: ignore[override]
        self.by_id_calls.append(city_id)
        if not self._city_by_id:
            return None
        return self._city_by_id if city_id == self._city_by_id.get("id") else None


async def test_property_to_scheme_fills_schema_fields():
    prop = {
        "population": 100000,
        "population_density": 2500,
        "time_zone": "+03:00",
        "time_created": "2024-01-01",
        "c_latitude": 50.5,
        "c_longitude": 30.2,
    }

    result = await city_service.property_to_scheme(prop)

    assert result.population == 100000
    assert result.time_zone == "+03:00"
    assert result.c_longitude == 30.2


async def test_city_to_scheme_enriches_property(monkeypatch):
    city_row = {
        "id": 7,
        "city_name": "Test City",
        "downloaded": False,
        "id_property": 15,
    }
    fake_repo = _FakeCityRepo(
        cities=[city_row],
        properties={
            15: {
                "population": 5,
                "population_density": None,
                "time_zone": "+02",
                "time_created": "2024",
                "c_latitude": 1.1,
                "c_longitude": 2.2,
            }
        },
        city_by_id=city_row,
    )
    monkeypatch.setattr(city_service, "CityRepository", lambda: fake_repo)

    result = await city_service.city_to_scheme(city_row)

    assert result.city_name == "Test City"
    assert result.property is not None
    assert fake_repo.property_calls == [15]


async def test_get_cities_uses_repository(monkeypatch):
    cities = [
        {"id": 1, "city_name": "A", "downloaded": True, "id_property": 10},
        {"id": 2, "city_name": "B", "downloaded": False, "id_property": 20},
    ]
    properties = {
        10: {
            "population": 1,
            "population_density": None,
            "time_zone": "+00",
            "time_created": "2024",
            "c_latitude": 0.0,
            "c_longitude": 0.0,
        },
        20: {
            "population": 2,
            "population_density": None,
            "time_zone": "+01",
            "time_created": "2024",
            "c_latitude": 1.0,
            "c_longitude": 1.0,
        },
    }
    fake_repo = _FakeCityRepo(
        cities=cities, properties=properties, city_by_id=cities[0]
    )
    monkeypatch.setattr(city_service, "CityRepository", lambda: fake_repo)

    result = await city_service.get_cities(page=2, per_page=5)

    assert len(result) == 2
    assert fake_repo.list_calls == [(2, 5)]
    assert fake_repo.property_calls == [10, 20]


async def test_get_city_returns_none_if_missing(monkeypatch):
    fake_repo = _FakeCityRepo(cities=[], properties={}, city_by_id={})
    monkeypatch.setattr(city_service, "CityRepository", lambda: fake_repo)

    result = await city_service.get_city(city_id=999)

    assert result is None
    assert fake_repo.by_id_calls == [999]
