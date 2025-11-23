"""Facade that gathers application services and re-exports them for the API layer."""

import logging
from typing import List, TYPE_CHECKING

from geopandas.geodataframe import GeoDataFrame

from application.converters import graph_to_scheme, graph_to_zip_archive
from application.city_service import get_city, get_cities
from application.graph_service import graph_from_poly
from application.region_service import (
    list_to_polygon,
    polygons_from_region,
    get_regions,
    get_regions_info,
)
from application.ingestion.utils import (
    AUTH_FILE_PATH,
    add_city_to_db,
    add_graph_to_db,
    add_info_to_db,
    add_point_to_db,
    add_property_to_db,
    init_db,
)
from domain.schemas import GraphBase
from infrastructure.database import SessionLocal

# Public API surface preserved for compatibility with the legacy imports
__all__ = [
    "AUTH_FILE_PATH",
    "add_city_to_db",
    "add_graph_to_db",
    "add_info_to_db",
    "add_point_to_db",
    "add_property_to_db",
    "get_db",
    "get_city",
    "get_cities",
    "get_regions",
    "get_regions_info",
    "graph_from_ids",
    "graph_to_scheme",
    "graph_to_zip",
    "init_db",
    "list_to_polygon",
    "polygons_from_region",
]

# Configure the root SQLAlchemy logger so it stays quiet by default
log = logging.getLogger("sqlalchemy.engine")
log.setLevel(logging.WARNING)

# Drop existing handlers to avoid duplicate output
if log.hasHandlers():
    log.handlers.clear()

# Attach a null handler to silence messages in production
log.addHandler(logging.NullHandler())


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def graph_from_ids(city_id: int, regions_ids: List[int], regions: GeoDataFrame):
    """Resolve region polygons by id list and delegate graph building to core services."""
    polygon = polygons_from_region(regions_ids=regions_ids, regions=regions)
    if polygon is None:
        return None, None, None, None, None, None, None

    gfp = await graph_from_poly(city_id=city_id, polygon=polygon)
    return gfp


def graph_to_zip(graph_base: GraphBase):
    """Wrap the graph CSV payloads into a downloadable ZIP archive."""
    return graph_to_zip_archive(graph_base)
