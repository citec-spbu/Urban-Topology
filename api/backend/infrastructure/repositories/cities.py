from typing import Sequence, Optional

from sqlalchemy import update

from infrastructure.database import (
    CityAsync,
    CityPropertyAsync,
    database,
    engine,
)


class CityRepository:
    """Async helpers for querying cities and their properties."""

    async def list(self, page: int, per_page: int) -> Sequence[dict]:
        """Return paginated cities using a pure SQL approach."""
        rows = await database.fetch_all(
            CityAsync.select().offset(page * per_page).limit(per_page)
        )
        return rows

    async def by_id(self, city_id: int) -> Optional[dict]:
        """Fetch a single city record by identifier."""
        row = await database.fetch_one(
            CityAsync.select().where(CityAsync.c.id == city_id)
        )
        return row

    async def property_by_city(self, city_prop_id: int) -> Optional[dict]:
        """Fetch the city property row by identifier."""
        row = await database.fetch_one(
            CityPropertyAsync.select().where(CityPropertyAsync.c.id == city_prop_id)
        )
        return row

    def mark_downloaded(self, city_id: int) -> None:
        """Flag a city as downloaded inside the database."""
        with engine.begin() as conn:
            conn.execute(
                update(CityAsync)
                .where(CityAsync.c.id == city_id)
                .values(downloaded=True)
            )
