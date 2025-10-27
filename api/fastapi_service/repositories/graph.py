# api/fastapi_service/repositories/graph.py
from typing import Iterable, Sequence, Optional
from sqlalchemy import text
from database import database, engine

class GraphRepository:
    async def points_in_bbox(self, city_id: int, bbox: tuple[float, float, float, float]) -> Sequence[tuple]:
        q = (
            """
            SELECT p.id, p.longitude, p.latitude
            FROM "Points" p
            JOIN "Edges" e ON e.id_src = p.id
            JOIN "Ways" w  ON e.id_way = w.id
            WHERE w.id_city = :city_id
              AND p.longitude BETWEEN :min_lon AND :max_lon
              AND p.latitude  BETWEEN :min_lat AND :max_lat
            """
        )
        return await database.fetch_all(q, values={
            "city_id": city_id,
            "min_lon": bbox[0], "min_lat": bbox[1],
            "max_lon": bbox[2], "max_lat": bbox[3],
        })

    async def property_id(self, name: str) -> int:
        # Используем строковый SQL вместо text(), т.к. fetch_one с TextClause падает на некоторых версиях "databases"
        row = await database.fetch_one(
            'SELECT id FROM "Properties" WHERE property = :name',
            values={"name": name}
        )
        return None if row is None else row.id

    async def edges_in_bbox(self, city_id: int, bbox, prop_id_name: int, prop_id_highway: int,
                            highway_types: Iterable[str]) -> Sequence[tuple]:
        # :types — массив строк
        q = (
            """
            WITH named_streets AS (
                SELECT e.id, e.id_way, e.id_src, e.id_dist, wp_n.value AS value
                FROM "Edges" e
                JOIN "WayProperties" wp_n ON wp_n.id_way = e.id_way AND wp_n.id_property = :prop_id_name
                JOIN "WayProperties" wp_h ON wp_h.id_way = e.id_way AND wp_h.id_property = :prop_id_hw
                JOIN "Ways" w ON w.id = e.id_way
                JOIN "Points" p ON p.id = e.id_src
                WHERE w.id_city = :city_id
                  AND p.longitude BETWEEN :min_lon AND :max_lon
                  AND p.latitude  BETWEEN :min_lat AND :max_lat
                  AND wp_h.value = ANY(:types)
            ),
            unnamed_streets AS (
                SELECT e.id, e.id_way, e.id_src, e.id_dist, NULL AS value
                FROM "Edges" e
                JOIN "Ways" w ON w.id = e.id_way
                JOIN "Points" p ON p.id = e.id_src
                JOIN "WayProperties" wp_h ON wp_h.id_way = e.id_way AND wp_h.id_property = :prop_id_hw
                LEFT JOIN "WayProperties" wp_n ON wp_n.id_way = e.id_way AND wp_n.id_property = :prop_id_name
                WHERE w.id_city = :city_id
                  AND p.longitude BETWEEN :min_lon AND :max_lon
                  AND p.latitude  BETWEEN :min_lat AND :max_lat
                  AND wp_n.value IS NULL
                  AND wp_h.value = ANY(:types)
            )
            SELECT id, id_way, id_src, id_dist, value FROM named_streets
            UNION
            SELECT id, id_way, id_src, id_dist, value FROM unnamed_streets
            """
        )
        return await database.fetch_all(q, values={
            "city_id": city_id,
            "min_lon": bbox[0], "min_lat": bbox[1],
            "max_lon": bbox[2], "max_lat": bbox[3],
            "prop_id_name": prop_id_name,
            "prop_id_hw": prop_id_highway,
            "types": list(highway_types),
        })

    async def way_props(self, way_ids: Iterable[int]) -> Sequence[tuple]:
        ids = list(way_ids)
        if not ids:
            return []
        q = (
            """
            SELECT wp.id_way AS id_way, p.property, wp.value
            FROM "WayProperties" wp
            JOIN "Properties" p ON p.id = wp.id_property
            WHERE wp.id_way = ANY(:ids)
            """
        )
        return await database.fetch_all(q, values={"ids": ids})

    def point_props_via_temp(self, point_ids: Iterable[int]) -> Sequence[tuple]:
        # как у тебя сейчас через TEMP TABLE — оставляем, но прячем внутрь репозитория
        ids = list(point_ids)
        if not ids:
            return []
        with engine.begin() as conn:
            conn.execute(text("CREATE TEMPORARY TABLE temp_ids_point (id_point BIGINT PRIMARY KEY);"))
            conn.execute(text("INSERT INTO temp_ids_point (id_point) VALUES " + ",".join(f"({i})" for i in ids)))
            rows = conn.execute(text("""
                SELECT pp.id_point, p.property, pp.value
                FROM "PointProperties" pp
                JOIN temp_ids_point t ON t.id_point = pp.id_point
                JOIN "Properties" p ON p.id = pp.id_property
            """)).fetchall()
            conn.execute(text("DROP TABLE temp_ids_point;"))
            return rows

    async def oneway_ids(self, city_id: int) -> list[int]:
        q = (
            """
            SELECT DISTINCT wp.id_way
            FROM "WayProperties" wp
            JOIN "Properties" p ON p.id = wp.id_property
            JOIN "Ways" w ON w.id = wp.id_way
            WHERE p.property = 'oneway' AND wp.value = 'yes' AND w.id_city = :city_id
            """
        )
        rows = await database.fetch_all(q, values={"city_id": city_id})
        return [r[0] for r in rows]

    async def points_in_polygon(self, city_id: int, polygon_wkt: str) -> Sequence[tuple]:
        """
        Return points whose lon/lat fall within the provided polygon (WKT, SRID 4326).
        """
        q = (
            """
            WITH poly AS (
                SELECT ST_GeomFromText(:wkt, 4326) AS g
            )
            SELECT p.id, p.longitude, p.latitude
            FROM "Points" p
            JOIN "Edges" e ON e.id_src = p.id -- ensure point participates in an edge of this city
            JOIN "Ways" w  ON e.id_way = w.id
            CROSS JOIN poly
            WHERE w.id_city = :city_id
              AND ST_Within(ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326), poly.g)
            """
        )
        return await database.fetch_all(q, values={"wkt": polygon_wkt, "city_id": city_id})

    async def edges_in_polygon(
        self,
        city_id: int,
        polygon_wkt: str,
        prop_id_name: int,
        prop_id_highway: int,
        highway_types: Iterable[str],
        require_both_endpoints: bool = True,
        use_midpoint: bool = False,
    ) -> Sequence[tuple]:
        """
        Return edges (id, id_way, id_src, id_dist, name) where
        - way belongs to city_id
        - highway in given types
        - and either:
            a) both endpoints are inside polygon (default), or
            b) midpoint of the segment is inside (use_midpoint=True)
        """
        condition = """
            (ST_Within(ST_SetSRID(ST_MakePoint(ps.longitude, ps.latitude), 4326), poly.g)
             AND ST_Within(ST_SetSRID(ST_MakePoint(pd.longitude, pd.latitude), 4326), poly.g))
        """
        if not require_both_endpoints and use_midpoint:
            # midpoint inside polygon
            condition = """
                ST_Within(
                    ST_LineInterpolatePoint(
                        ST_MakeLine(
                            ST_SetSRID(ST_MakePoint(ps.longitude, ps.latitude), 4326),
                            ST_SetSRID(ST_MakePoint(pd.longitude, pd.latitude), 4326)
                        ),
                        0.5
                    ),
                    poly.g
                )
            """
        elif use_midpoint:
            # both endpoints OR midpoint
            condition = """
                (
                    (ST_Within(ST_SetSRID(ST_MakePoint(ps.longitude, ps.latitude), 4326), poly.g)
                     AND ST_Within(ST_SetSRID(ST_MakePoint(pd.longitude, pd.latitude), 4326), poly.g))
                )
                OR
                (
                    ST_Within(
                        ST_LineInterpolatePoint(
                            ST_MakeLine(
                                ST_SetSRID(ST_MakePoint(ps.longitude, ps.latitude), 4326),
                                ST_SetSRID(ST_MakePoint(pd.longitude, pd.latitude), 4326)
                            ),
                            0.5
                        ),
                        poly.g
                    )
                )
            """

        q = (
            f"""
            WITH poly AS (
                SELECT ST_GeomFromText(:wkt, 4326) AS g
            ),
            named AS (
                SELECT e.id, e.id_way, e.id_src, e.id_dist, wp_n.value AS value
                FROM "Edges" e
                JOIN "WayProperties" wp_n ON wp_n.id_way = e.id_way AND wp_n.id_property = :prop_id_name
                JOIN "WayProperties" wp_h ON wp_h.id_way = e.id_way AND wp_h.id_property = :prop_id_hw
                JOIN "Ways" w ON w.id = e.id_way
                JOIN "Points" ps ON ps.id = e.id_src
                JOIN "Points" pd ON pd.id = e.id_dist
                CROSS JOIN poly
                WHERE w.id_city = :city_id
                  AND wp_h.value = ANY(:types)
                  AND {condition}
            ),
            unnamed AS (
                SELECT e.id, e.id_way, e.id_src, e.id_dist, NULL AS value
                FROM "Edges" e
                JOIN "Ways" w ON w.id = e.id_way
                JOIN "WayProperties" wp_h ON wp_h.id_way = e.id_way AND wp_h.id_property = :prop_id_hw
                LEFT JOIN "WayProperties" wp_n ON wp_n.id_way = e.id_way AND wp_n.id_property = :prop_id_name
                JOIN "Points" ps ON ps.id = e.id_src
                JOIN "Points" pd ON pd.id = e.id_dist
                CROSS JOIN poly
                WHERE w.id_city = :city_id
                  AND wp_n.value IS NULL
                  AND wp_h.value = ANY(:types)
                  AND {condition}
            )
            SELECT id, id_way, id_src, id_dist, value FROM named
            UNION
            SELECT id, id_way, id_src, id_dist, value FROM unnamed
            """
        )
        return await database.fetch_all(q, values={
            "wkt": polygon_wkt,
            "city_id": city_id,
            "prop_id_name": prop_id_name,
            "prop_id_hw": prop_id_highway,
            "types": list(highway_types),
        })
