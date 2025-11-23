from typing import Optional

from pandas.core.frame import DataFrame

from infrastructure.repositories.ingestion import IngestionRepository
from shared.paths import city_pbf_path


REQUIRED_ROAD_TYPES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "road",
    "unclassified",
    "residential",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
)


class IngestionService:
    """High-level helper that ensures city metadata and graphs are loaded into the DB."""

    def __init__(self, auth_file_path: str = "./data/db.properties") -> None:
        self.repo = IngestionRepository()
        self.auth_file_path = auth_file_path

    def ensure_city(self, city_row: DataFrame) -> tuple[int, bool]:
        """Make sure city metadata exists; return DB id and downloaded flag."""
        city_name = city_row["Город"]
        existing = self.repo.find_city_by_name(city_name)
        if existing is not None:
            return existing.id, bool(existing.downloaded)

        prop_id = self.repo.create_city_property(
            latitude=float(city_row["Широта"]),
            longitude=float(city_row["Долгота"]),
            population=int(city_row["Население"]),
            time_zone=city_row["Часовой пояс"],
        )
        city_id = self.repo.create_city(city_name=city_name, property_id=prop_id)
        return city_id, False

    def import_if_needed(self, city_row: DataFrame) -> Optional[int]:
        """Import a city's graph if it is not already marked as downloaded."""
        city_name = city_row["Город"]
        city_id, downloaded = self.ensure_city(city_row)

        if downloaded:
            return city_id

        file_path = city_pbf_path(city_name)
        try:
            import os

            if os.path.exists(file_path):
                self.repo.import_city_graph(
                    city_id=city_id,
                    file_path=str(file_path),
                    city_name=city_name,
                    auth_file_path=self.auth_file_path,
                    required_road_types=REQUIRED_ROAD_TYPES,
                )
                return city_id
        except Exception:
            # Errors are logged up the stack; returning None signals a failure
            return None
        return None
