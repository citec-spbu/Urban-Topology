import os
from typing import Optional
from sqlalchemy import text, update

from database import engine, DATABASE_URL, CityAsync, SessionLocal
from models import City, CityProperty


class IngestionRepository:
    """Low-level ingestion operations: create city records and import OSM graph into DB."""

    def find_city_by_name(self, city_name: str) -> Optional[object]:
        with engine.connect() as conn:
            q = CityAsync.select().where(CityAsync.c.city_name == city_name)
            return conn.execute(q).first()

    def create_city_property(self, *, latitude: float, longitude: float, population: int, time_zone: str) -> int:
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
        with SessionLocal.begin() as session:
            city = City(city_name=city_name, id_property=property_id)
            session.add(city)
            session.flush()
            return city.id

    def mark_downloaded(self, city_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(update(CityAsync).where(CityAsync.c.id == city_id).values(downloaded=True))

    def apply_osmosis_schema(self) -> None:
        cmd = f"psql {DATABASE_URL} -f /osmosis/script/pgsimple_schema_0.6.sql"
        rc = os.system(cmd)
        if rc != 0:
            raise RuntimeError(f"psql schema apply failed with code {rc}")

    def run_osmosis_and_load(self, *, file_path: str, auth_file_path: str, required_road_types: tuple[str, ...]) -> None:
        road_file_path = file_path[:-8] + "_highway.pbf"
        types = ",".join(required_road_types)
        cmd = (
            f"/osmosis/bin/osmosis --read-pbf-fast file=\"{file_path}\" "
            f"--tf accept-ways highway={types} --tf reject-ways side_road=yes --used-node "
            f"--write-pbf omitmetadata=true file=\"{road_file_path}\" "
            f"&& /osmosis/bin/osmosis --read-pbf-fast file=\"{road_file_path}\" --write-pgsimp authFile=\"{auth_file_path}\" "
            f"&& rm \"{road_file_path}\""
        )
        rc = os.system(cmd)
        if rc != 0:
            raise RuntimeError(f"osmosis import failed with code {rc}")

    def fill_city_graph_from_osm_tables(self, *, city_id: int) -> None:
        with engine.begin() as conn:
            # Ways
            conn.execute(text(
                """
                INSERT INTO "Ways" (id, id_city)
                SELECT w.id, :city_id
                FROM ways w;
                """
            ), {"city_id": city_id})

            # Points
            conn.execute(text(
                """
                INSERT INTO "Points" (id, longitude, latitude)
                SELECT DISTINCT n.id, ST_X(n.geom) AS longitude, ST_Y(n.geom) AS latitude
                FROM nodes n
                JOIN way_nodes wn ON wn.node_id = n.id
                JOIN "Ways" w ON w.id = wn.way_id;
                """
            ))

            # Properties (unique keys from nodes/ways)
            conn.execute(text(
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
            ))

            # WayProperties
            conn.execute(text(
                """
                INSERT INTO "WayProperties" (id_way, id_property, value)
                SELECT wt.way_id, p.id, wt.v
                FROM way_tags wt
                JOIN "Ways" w ON w.id = wt.way_id
                JOIN "Properties" p ON p.property LIKE wt.k;
                """
            ))

            # PointProperties
            conn.execute(text(
                """
                INSERT INTO "PointProperties" (id_point, id_property, value)
                SELECT nt.node_id, pr.id, nt.v
                FROM node_tags nt
                JOIN "Points" pt ON pt.id = nt.node_id
                JOIN "Properties" pr ON pr.property LIKE nt.k;
                """
            ))

            # Edges oneway
            conn.execute(text(
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
            ))

            # Edges not oneway (forward)
            conn.execute(text(
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
            ))

            # Edges not oneway (reverse)
            conn.execute(text(
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
            ))

    def import_city_graph(self, *, city_id: int, file_path: str, city_name: str, auth_file_path: str,
                           required_road_types: tuple[str, ...]) -> None:
        self.apply_osmosis_schema()
        self.run_osmosis_and_load(file_path=file_path, auth_file_path=auth_file_path, required_road_types=required_road_types)
        self.fill_city_graph_from_osm_tables(city_id=city_id)
        self.mark_downloaded(city_id)
