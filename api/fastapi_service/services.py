"""Фасад, который собирает сервисы ядра и экспортирует их в старый API."""
from database import SessionLocal
from geopandas.geodataframe import GeoDataFrame
from typing import List, TYPE_CHECKING
from datetime import datetime
import subprocess

import logging

from core.converters import graph_to_scheme
from core.city_service import get_city, get_cities
from core.graph_service import graph_from_poly, calc_metrics
from core.region_service import (
    list_to_polygon,
    polygons_from_region,
    get_regions,
    get_regions_info,
)
from core.ingestion_utils import (
    AUTH_FILE_PATH,
    add_city_to_db,
    add_graph_to_db,
    add_info_to_db,
    add_point_to_db,
    add_property_to_db,
    init_db,
)

# Собираем публичный API, чтобы старые импорты из services продолжали работать
__all__ = [
    'AUTH_FILE_PATH',
    'add_city_to_db',
    'add_graph_to_db',
    'add_info_to_db',
    'add_point_to_db',
    'add_property_to_db',
    'get_db',
    'get_city',
    'get_cities',
    'get_regions',
    'get_regions_info',
    'graph_from_ids',
    'graph_to_scheme',
    'init_db',
    'list_to_polygon',
    'polygons_from_region',
]

# Создайте или получите корневой логгер SQLAlchemy, установите уровень WARNING
log = logging.getLogger("sqlalchemy.engine")
log.setLevel(logging.WARNING)

# Убедитесь, что обработчик лога убран, если он уже установлен
if log.hasHandlers():
    log.handlers.clear()

# Если вы хотите полностью убрать любой вывод, вы можете добавить "глушитель":
log.addHandler(logging.NullHandler())


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def graph_from_ids(city_id : int, regions_ids : List[int], regions : GeoDataFrame):
    print(f"{datetime.now()} polygons_from_region begin")
    polygon = polygons_from_region(regions_ids=regions_ids, regions=regions)
    print(f"{datetime.now()} polygons_from_region end")
    if polygon == None:
        return None, None, None, None, None
    print(f"{datetime.now()} graph_from_poly begin")
    gfp = await graph_from_poly(city_id=city_id, polygon=polygon)
    print(f"{datetime.now()} graph_from_poly end")
    return gfp

