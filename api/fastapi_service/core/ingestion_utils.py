"""Utility helpers for preparing city data and loading graphs into the DB."""

from typing import Optional

from pandas.core.frame import DataFrame

from ingestion_service import IngestionService, REQUIRED_ROAD_TYPES
from models import City, CityProperty, Point
from database import SessionLocal


AUTH_FILE_PATH = "./data/db.properties"


def add_info_to_db(city_df: DataFrame) -> Optional[int]:
    """Create missing city records and trigger graph import when required."""
    ingestion = IngestionService(auth_file_path=AUTH_FILE_PATH)
    return ingestion.import_if_needed(city_df)


def add_graph_to_db(city_id: int, file_path: str, city_name: str) -> None:
    """Import a graph straight from a prepared PBF file."""
    ingestion = IngestionService(auth_file_path=AUTH_FILE_PATH)
    ingestion.repo.import_city_graph(
        city_id=city_id,
        file_path=file_path,
        city_name=city_name,
        auth_file_path=AUTH_FILE_PATH,
        required_road_types=REQUIRED_ROAD_TYPES,
    )


def add_point_to_db(df: DataFrame) -> int:
    """Persist a point of interest and return its identifier."""
    with SessionLocal.begin() as session:
        point = Point(latitude=float(df["Широта"]), longitude=float(df["Долгота"]))
        session.add(point)
        session.flush()
        return point.id


def add_property_to_db(df: DataFrame) -> int:
    """Store city properties such as centroid coordinates, population, and time zone."""
    with SessionLocal.begin() as session:
        city_property = CityProperty(
            c_latitude=float(df["Широта"]),
            c_longitude=float(df["Долгота"]),
            population=int(df["Население"]),
            time_zone=df["Часовой пояс"],
        )
        session.add(city_property)
        session.flush()
        return city_property.id


def add_city_to_db(df: DataFrame, property_id: int) -> int:
    """Create a city record tied to the previously stored properties."""
    with SessionLocal.begin() as session:
        city = City(city_name=df["Город"], id_property=property_id)
        session.add(city)
        session.flush()
        return city.id


def init_db(cities_info: DataFrame) -> None:
    """Iterate over the CSV with cities and kick off the import for each row."""
    for row in range(cities_info.shape[0]):
        add_info_to_db(cities_info.loc[row, :])
