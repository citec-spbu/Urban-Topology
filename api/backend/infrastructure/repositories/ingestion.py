import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from sqlalchemy import text, update

from infrastructure.database import (
    DATABASE_URL,
    CityAsync,
    SessionLocal,
    engine,
)
from infrastructure.models import City, CityProperty


logger = logging.getLogger(__name__)


class IngestionRepository:
    """Low-level data access helpers for importing OSM-derived city graphs."""

    def find_city_by_name(self, city_name: str) -> Optional[object]:
        """Return a city row if it already exists."""
        with engine.connect() as conn:
            q = CityAsync.select().where(CityAsync.c.city_name == city_name)
            return conn.execute(q).first()

    def create_city_property(
        self, *, latitude: float, longitude: float, population: int, time_zone: str
    ) -> int:
        """Insert a CityProperty record and return its id."""
        with SessionLocal.begin() as session:
            prop = CityProperty(
                c_latitude=latitude,
                c_longitude=longitude,
                population=population,
                time_zone=time_zone,
            )
            session.add(prop)
            session.flush()
            return prop.id

    def create_city(self, *, city_name: str, property_id: int) -> int:
        """Insert a City row pointing to the provided property id."""
        with SessionLocal.begin() as session:
            city = City(city_name=city_name, id_property=property_id)
            session.add(city)
            session.flush()
            return city.id

    def mark_downloaded(self, city_id: int) -> None:
        """Mark the city as downloaded after successful ingestion."""
        with engine.begin() as conn:
            conn.execute(
                update(CityAsync)
                .where(CityAsync.c.id == city_id)
                .values(downloaded=True)
            )

    def apply_osmosis_schema(self) -> None:
        """Load the Osmosis PostgreSQL schema via psql."""
        try:
            result = subprocess.run(
                [
                    "psql",
                    DATABASE_URL,
                    "-f",
                    "/osmosis/script/pgsimple_schema_0.6.sql",
                ],
                shell=False,
                timeout=300,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("psql schema apply timed out") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"psql schema apply failed with code {result.returncode}: {stderr}"
            )

    def run_osmosis_and_load(
        self,
        *,
        file_path: str,
        auth_file_path: str,
        required_road_types: tuple[str, ...],
        city_name: str,
    ) -> None:
        """Filter the original PBF and load the result into PostgreSQL tables."""
        base = Path(file_path)
        stem = base.name
        for suf in (".osm.pbf", ".pbf"):
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
                break
        road_file_path = str(base.with_name(f"{stem}_highway.pbf"))
        types = ",".join(required_road_types)
        try:
            logger.info(
                "Starting osmosis for city '%s' (file: %s)",
                city_name,
                file_path,
            )
            subprocess.run(
                [
                    "/osmosis/bin/osmosis",
                    "--read-pbf-fast",
                    f"file={file_path}",
                    "--tf",
                    "accept-ways",
                    f"highway={types}",
                    "--tf",
                    "reject-ways",
                    "side_road=yes",
                    "--used-node",
                    "--write-pbf",
                    "omitmetadata=true",
                    f"file={road_file_path}",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "/osmosis/bin/osmosis",
                    "--read-pbf-fast",
                    f"file={road_file_path}",
                    "--write-pgsimp",
                    f"authFile={auth_file_path}",
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"osmosis import failed: {e.returncode}") from e
        finally:
            try:
                os.remove(road_file_path)
            except OSError:
                pass

    def fill_city_graph_from_osm_tables(self, *, city_id: int) -> None:
        """Copy data from Osmosis tables into application-specific structures."""
        with engine.begin() as conn:
            # Populate "Ways"
            conn.execute(
                text(
                    """
                INSERT INTO "Ways" (id, id_city)
                SELECT w.id, :city_id
                FROM ways w;
                """
                ),
                {"city_id": city_id},
            )

            # Populate "Points"
            conn.execute(
                text(
                    """
                INSERT INTO "Points" (id, longitude, latitude)
                SELECT DISTINCT n.id, ST_X(n.geom) AS longitude, ST_Y(n.geom) AS latitude
                FROM nodes n
                JOIN way_nodes wn ON wn.node_id = n.id
                JOIN "Ways" w ON w.id = wn.way_id;
                """
                )
            )

            # Insert unique property keys collected from nodes and ways
            conn.execute(
                text(
                    """
                INSERT INTO "Properties" (property)
                SELECT DISTINCT k AS property
                FROM (
                    SELECT DISTINCT nt.k FROM node_tags nt JOIN "Points" p ON p.id = nt.node_id
                    UNION
                    SELECT DISTINCT wt.k FROM way_tags wt JOIN "Ways" w ON w.id = wt.way_id
                ) keys
                WHERE NOT EXISTS (SELECT 1 FROM "Properties" pr WHERE keys.k = pr.property);
                """
                )
            )

            # Map way tag values to "WayProperties"
            conn.execute(
                text(
                    """
                INSERT INTO "WayProperties" (id_way, id_property, value)
                SELECT wt.way_id, p.id, wt.v
                FROM way_tags wt
                JOIN "Ways" w ON w.id = wt.way_id
                JOIN "Properties" p ON LOWER(TRIM(p.property)) = LOWER(TRIM(wt.k));
                """
                )
            )

            # Map node tag values to "PointProperties"
            conn.execute(
                text(
                    """
                INSERT INTO "PointProperties" (id_point, id_property, value)
                SELECT nt.node_id, pr.id, nt.v
                FROM node_tags nt
                JOIN "Points" pt ON pt.id = nt.node_id
                JOIN "Properties" pr ON LOWER(TRIM(pr.property)) = LOWER(TRIM(nt.k));
                """
                )
            )

            # Insert directed edges for one-way streets
            conn.execute(
                text(
                    """
                INSERT INTO "Edges" (id_way, id_src, id_dist)
                SELECT wn.way_id, wn.node_id, wn2.node_id
                FROM "Ways" w
                JOIN way_nodes wn ON wn.way_id = w.id
                JOIN way_tags wt ON wt.way_id = wn.way_id
                JOIN way_nodes wn2 ON wn2.way_id = wn.way_id
                WHERE wt.k LIKE 'oneway' AND wt.v LIKE 'yes' AND wn.sequence_id + 1 = wn2.sequence_id
                ORDER BY wn.sequence_id;
                """
                )
            )

            # Insert forward edges for bidirectional streets
            conn.execute(
                text(
                    """
                WITH oneway_way_id AS (
                    SELECT w.id FROM ways w JOIN way_tags wt ON wt.way_id = w.id
                    WHERE wt.k LIKE 'oneway' AND wt.v LIKE 'yes'
                )
                INSERT INTO "Edges" (id_way, id_src, id_dist)
                SELECT wn.way_id, wn.node_id, wn2.node_id
                FROM "Ways" w
                JOIN way_nodes wn ON wn.way_id = w.id
                JOIN way_nodes wn2 ON wn2.way_id = wn.way_id
                WHERE w.id NOT IN (SELECT id FROM oneway_way_id)
                  AND wn.sequence_id + 1 = wn2.sequence_id
                ORDER BY wn.sequence_id;
                """
                )
            )

            # Insert reverse edges for bidirectional streets
            conn.execute(
                text(
                    """
                WITH oneway_way_id AS (
                    SELECT w.id FROM ways w JOIN way_tags wt ON wt.way_id = w.id
                    WHERE wt.k LIKE 'oneway' AND wt.v LIKE 'yes'
                )
                INSERT INTO "Edges" (id_way, id_src, id_dist)
                SELECT wn.way_id, wn2.node_id, wn.node_id
                FROM "Ways" w
                JOIN way_nodes wn ON wn.way_id = w.id
                JOIN way_nodes wn2 ON wn2.way_id = wn.way_id
                WHERE w.id NOT IN (SELECT id FROM oneway_way_id)
                  AND wn.sequence_id + 1 = wn2.sequence_id
                ORDER BY wn2.sequence_id DESC;
                """
                )
            )

    def import_city_graph(
        self,
        *,
        city_id: int,
        file_path: str,
        city_name: str,
        auth_file_path: str,
        required_road_types: tuple[str, ...],
    ) -> None:
        """Run the entire ingestion pipeline for a city."""
        self.apply_osmosis_schema()
        self.run_osmosis_and_load(
            file_path=file_path,
            auth_file_path=auth_file_path,
            required_road_types=required_road_types,
            city_name=city_name,
        )
        self.fill_city_graph_from_osm_tables(city_id=city_id)
        self.mark_downloaded(city_id)
