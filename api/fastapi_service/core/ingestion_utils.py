"""Утилиты для подготовки данных городов и загрузки графов в базу."""

from typing import Optional

from pandas.core.frame import DataFrame

from ..ingestion_service import IngestionService, REQUIRED_ROAD_TYPES
from ..models import City, CityProperty, Point
from ..database import SessionLocal


AUTH_FILE_PATH = "./data/db.properties"


def add_info_to_db(city_df: DataFrame) -> Optional[int]:
    """Создаёт недостающие записи города и при необходимости запускает импорт графа."""
    ingestion = IngestionService(auth_file_path=AUTH_FILE_PATH)
    return ingestion.import_if_needed(city_df)


def add_graph_to_db(city_id: int, file_path: str, city_name: str) -> None:
    """Прямая загрузка графа по заранее подготовленному PBF."""
    ingestion = IngestionService(auth_file_path=AUTH_FILE_PATH)
    ingestion.repo.import_city_graph(
        city_id=city_id,
        file_path=file_path,
        city_name=city_name,
        auth_file_path=AUTH_FILE_PATH,
        required_road_types=REQUIRED_ROAD_TYPES,
    )


def add_point_to_db(df: DataFrame) -> int:
    """Сохраняет координаты точки интереса и возвращает её идентификатор."""
    with SessionLocal.begin() as session:
        point = Point(latitude=float(df['Широта']), longitude=float(df['Долгота']))
        session.add(point)
        session.flush()
        return point.id


def add_property_to_db(df: DataFrame) -> int:
    """Заводит свойства города (координаты центра, население, часовой пояс)."""
    with SessionLocal.begin() as session:
        city_property = CityProperty(
            c_latitude=float(df['Широта']),
            c_longitude=float(df['Долгота']),
            population=int(df['Население']),
            time_zone=df['Часовой пояс'],
        )
        session.add(city_property)
        session.flush()
        return city_property.id


def add_city_to_db(df: DataFrame, property_id: int) -> int:
    """Создаёт запись о городе и привязывает её к ранее созданным свойствам."""
    with SessionLocal.begin() as session:
        city = City(city_name=df['Город'], id_property=property_id)
        session.add(city)
        session.flush()
        return city.id


def init_db(cities_info: DataFrame) -> None:
    """Итерируется по CSV со списком городов и вызывает импорт по каждой записи."""
    for row in range(cities_info.shape[0]):
        add_info_to_db(cities_info.loc[row, :])
