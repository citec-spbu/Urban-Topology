"""Tests for application.region_service helpers."""

from __future__ import annotations

import pandas as pd
import pytest
from shapely.geometry import Polygon

from application import region_service


pytestmark = pytest.mark.anyio


@pytest.fixture()
def anyio_backend():
    return "asyncio"


def _regions_df(city_name: str = "Testopolis"):
    city_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    child_polygon = Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    data = {
        "osm_id": [101, 202],
        "local_name": [city_name, "District A"],
        "geometry": [city_polygon, child_polygon],
        "parents": ["[101]", "[101]"],
        "admin_level": [8, 9],
    }
    return pd.DataFrame(data)


def _cities_df(city_name: str = "Testopolis"):
    return pd.DataFrame(
        [
            {
                "Город": city_name,
                "admin_levels": "[8, 9]",
            }
        ]
    )


class _CityRepoStub:
    def __init__(self, city):
        self._city = city
        self.calls = []

    async def by_id(self, city_id):  # type: ignore[override]
        self.calls.append(city_id)
        return self._city


def test_children_returns_original_ids_when_not_found():
    regions = _regions_df()
    ids, has_children = region_service.children([101], 10, regions)
    assert ids == [101]
    assert has_children is False


def test_children_returns_new_ids_when_present():
    regions = _regions_df()
    regions.loc[1, "parents"] = "101,404"
    ids, has_children = region_service.children([101], 9, regions)
    assert ids == [202]
    assert has_children is True


def test_list_to_polygon_returns_combined_shape():
    coords = [[[0, 0], [1, 0], [1, 1], [0, 0]]]
    polygon = region_service.list_to_polygon(coords)
    assert polygon.area == pytest.approx(0.5, rel=1e-2)


def test_polygons_from_region_returns_union():
    regions = _regions_df()
    union = region_service.polygons_from_region([101, 202], regions)
    assert union is not None
    assert pytest.approx(union.area, rel=1e-2) == 2.0


def test_polygons_from_region_handles_missing():
    regions = _regions_df()
    assert region_service.polygons_from_region([], regions) is None


async def test_get_regions_builds_region_schemas(monkeypatch):
    regions = _regions_df()
    cities = _cities_df()
    repo = _CityRepoStub({"city_name": "Testopolis"})
    monkeypatch.setattr(region_service, "CityRepository", lambda: repo)

    result = await region_service.get_regions(42, regions, cities)

    assert result is not None
    assert len(result) >= 2
    assert result[0].name == "Testopolis"
    assert result[-1].name == "District A"
    assert repo.calls == [42]


async def test_get_regions_info_returns_metadata(monkeypatch):
    regions = _regions_df()
    cities = _cities_df()
    repo = _CityRepoStub({"city_name": "Testopolis"})
    monkeypatch.setattr(region_service, "CityRepository", lambda: repo)

    result = await region_service.get_regions_info(7, regions, cities)

    assert result is not None
    assert [r.admin_level for r in result] == [8, 8, 9]
