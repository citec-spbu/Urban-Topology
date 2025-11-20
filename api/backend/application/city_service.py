"""Helpers that load cities from the repository and convert them to schemas."""

from typing import List, Optional, Mapping, Any

from domain.schemas import CityBase, PropertyBase
from infrastructure.models import City, CityProperty
from infrastructure.repositories.cities import CityRepository


async def property_to_scheme(
    prop: Optional[Mapping[str, Any]],
) -> Optional[PropertyBase]:
    """Convert a raw city property record into a Pydantic schema."""
    if prop is None:
        return None

    prop_data = dict(prop)

    return PropertyBase(
        population=prop_data["population"],
        population_density=prop_data.get("population_density"),
        time_zone=prop_data["time_zone"],
        time_created=str(prop_data["time_created"]),
        c_latitude=prop_data["c_latitude"],
        c_longitude=prop_data["c_longitude"],
    )


async def city_to_scheme(city: Optional[Mapping[str, Any]]) -> Optional[CityBase]:
    """Attach property data to the city DTO and return a CityBase."""
    if city is None:
        return None

    city_base = CityBase(
        id=city["id"], city_name=city["city_name"], downloaded=city["downloaded"]
    )
    repo = CityRepository()
    prop = await repo.property_by_city(city["id_property"])
    city_base.property = await property_to_scheme(prop=prop)
    return city_base


async def cities_to_scheme_list(cities: List[City]) -> List[CityBase]:
    """Convert every city in the list into its schema representation."""
    return [await city_to_scheme(city=city) for city in cities]


async def get_cities(page: int, per_page: int) -> List[CityBase]:
    repo = CityRepository()
    rows = await repo.list(page=page, per_page=per_page)
    return await cities_to_scheme_list(rows)


async def get_city(city_id: int) -> Optional[CityBase]:
    repo = CityRepository()
    city = await repo.by_id(city_id)
    return await city_to_scheme(city=city)
