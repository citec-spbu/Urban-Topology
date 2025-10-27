"""Утилиты для чтения городов из репозитория и приведения их к схемам."""

from typing import List, Optional

from models import City, CityProperty
from repositories import CityRepository
from schemas import CityBase, PropertyBase


async def property_to_scheme(prop: Optional[CityProperty]) -> Optional[PropertyBase]:
    """Преобразует запись из БД о свойствах города в Pydantic-схему."""
    if prop is None:
        return None

    return PropertyBase(
        population=prop.population,
        population_density=prop.population_density,
        time_zone=prop.time_zone,
        time_created=str(prop.time_created),
        c_latitude=prop.c_latitude,
        c_longitude=prop.c_longitude,
    )


async def city_to_scheme(city: Optional[City]) -> Optional[CityBase]:
    """Дополняет DTO города связанными свойствами и возвращает CityBase."""
    if city is None:
        return None

    city_base = CityBase(id=city.id, city_name=city.city_name, downloaded=city.downloaded)
    repo = CityRepository()
    prop = await repo.property_by_city(city.id_property)
    city_base.property = await property_to_scheme(prop=prop)
    return city_base


async def cities_to_scheme_list(cities: List[City]) -> List[CityBase]:
    """Проходит по списку городов и собирает список схем."""
    return [await city_to_scheme(city=city) for city in cities]


async def get_cities(page: int, per_page: int) -> List[CityBase]:
    repo = CityRepository()
    rows = await repo.list(page=page, per_page=per_page)
    return await cities_to_scheme_list(rows)


async def get_city(city_id: int) -> Optional[CityBase]:
    repo = CityRepository()
    city = await repo.by_id(city_id)
    return await city_to_scheme(city=city)

