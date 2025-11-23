"""Work with regional geodata and convert them into schemas."""

from __future__ import annotations

import ast
from typing import List, Optional, Tuple

from geopandas.geodataframe import GeoDataFrame
from pandas.core.frame import DataFrame
from shapely.geometry.linestring import LineString
from shapely.geometry.multilinestring import MultiLineString
from shapely.geometry.polygon import Polygon
from shapely.ops import unary_union

from domain.schemas import RegionBase, RegionInfoBase
from infrastructure.repositories.cities import CityRepository


def to_list(polygon: LineString) -> List[List[float]]:
    coords: List[List[float]] = []
    for x, y in polygon.coords:
        coords.append([x, y])
    return coords


def to_json_array(polygon) -> List[List[List[float]]]:
    coordinates_list: List[List[List[float]]] = []
    if isinstance(polygon, LineString):
        coordinates_list.append(to_list(polygon))
    elif isinstance(polygon, MultiLineString):
        for line in polygon.geoms:
            coordinates_list.append(to_list(line))
    else:
        raise ValueError("polygon must be type of LineString or MultiLineString")

    return coordinates_list


def region_to_schemas(
    regions: GeoDataFrame, ids_list: List[int], admin_level: int
) -> List[RegionBase]:
    regions_list = []
    polygons = regions[regions["osm_id"].isin(ids_list)]
    for _, row in polygons.iterrows():
        id = row["osm_id"]
        name = row["local_name"]
        regions_array = to_json_array(row["geometry"].boundary)
        base = RegionBase(
            id=id, name=name, admin_level=admin_level, regions=regions_array
        )
        regions_list.append(base)

    return regions_list


def region_to_info_schemas(
    regions: GeoDataFrame, ids_list: List[int], admin_level: int
) -> List[RegionInfoBase]:
    regions_list: List[RegionInfoBase] = []
    polygons = regions[regions["osm_id"].isin(ids_list)]
    for _, row in polygons.iterrows():
        base = RegionInfoBase(
            id=int(row["osm_id"]),
            name=row["local_name"],
            admin_level=admin_level,
        )
        regions_list.append(base)
    return regions_list


def children(ids_list: List[int], admin_level: int, regions: GeoDataFrame):
    area = regions[
        regions["parents"].str.contains("|".join(str(x) for x in ids_list), na=False)
    ]
    area = area[area["admin_level"] == admin_level]
    lst = area["osm_id"].to_list()
    if len(lst) == 0:
        return ids_list, False
    return lst, True


def get_admin_levels(
    city_name: str, regions: GeoDataFrame, cities: DataFrame
) -> List[RegionBase]:
    regions_list = []

    levels_str = cities[cities["Город"] == city_name]["admin_levels"].values[0]
    levels = ast.literal_eval(levels_str)

    info = regions[regions["local_name"] == city_name].sort_values(by="admin_level")
    ids_list = [info["osm_id"].to_list()[0]]

    schemas = region_to_schemas(
        regions=regions, ids_list=ids_list, admin_level=levels[0]
    )
    regions_list.extend(schemas)
    for level in levels:
        ids_list, data_valid = children(
            ids_list=ids_list, admin_level=level, regions=regions
        )
        if data_valid:
            schemas = region_to_schemas(
                regions=regions, ids_list=ids_list, admin_level=level
            )
            regions_list.extend(schemas)

    return regions_list


def get_admin_levels_info(
    city_name: str, regions: GeoDataFrame, cities: DataFrame
) -> List[RegionInfoBase]:
    regions_list: List[RegionInfoBase] = []

    levels_str = cities[cities["Город"] == city_name]["admin_levels"].values[0]
    levels = ast.literal_eval(levels_str)

    info = regions[regions["local_name"] == city_name].sort_values(by="admin_level")
    ids_list = [info["osm_id"].to_list()[0]]

    schemas = region_to_info_schemas(
        regions=regions, ids_list=ids_list, admin_level=levels[0]
    )
    regions_list.extend(schemas)
    for level in levels:
        ids_list, data_valid = children(
            ids_list=ids_list, admin_level=level, regions=regions
        )
        if data_valid:
            schemas = region_to_info_schemas(
                regions=regions, ids_list=ids_list, admin_level=level
            )
            regions_list.extend(schemas)

    return regions_list


def list_to_polygon(polygons: List[List[List[float]]]):
    return unary_union([Polygon(polygon) for polygon in polygons])


def polygons_from_region(regions_ids: List[int], regions: GeoDataFrame):
    if len(regions_ids) == 0:
        return None
    polygons = regions[regions["osm_id"].isin(regions_ids)]
    if polygons is None or len(polygons) == 0:
        return None
    try:
        union_geom = unary_union([geom for geom in polygons["geometry"].values])
    except Exception:
        return None
    try:
        if union_geom is None or getattr(union_geom, "is_empty", False):
            return None
    except Exception:
        return None
    return union_geom


async def get_regions(
    city_id: int, regions: GeoDataFrame, cities: DataFrame
) -> Optional[List[RegionBase]]:
    """Find the city and assemble polygons for every administrative level."""
    repo = CityRepository()
    city = await repo.by_id(city_id)
    if city is None:
        return None

    city_name = (
        city["city_name"] if "city_name" in city else getattr(city, "city_name", None)
    )
    if city_name is None:
        return None

    return get_admin_levels(city_name=city_name, regions=regions, cities=cities)


async def get_regions_info(
    city_id: int, regions: GeoDataFrame, cities: DataFrame
) -> Optional[List[RegionInfoBase]]:
    """Return district metadata without geometry for the specified city."""
    repo = CityRepository()
    city = await repo.by_id(city_id)
    if city is None:
        return None

    city_name = (
        city["city_name"] if "city_name" in city else getattr(city, "city_name", None)
    )
    if city_name is None:
        return None

    return get_admin_levels_info(city_name=city_name, regions=regions, cities=cities)
