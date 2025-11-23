import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from sqlalchemy import text, update
from sqlalchemy.exc import CompileError, IntegrityError

from infrastructure.database import (
    AccessEdgeAsync,
    AccessNodeAsync,
    DATABASE_URL,
    CityAsync,
    SessionLocal,
    engine,
    metadata,
)
from infrastructure.models import City, CityProperty
from infrastructure.osm.osm_handler import build_access_graph


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
        # Sanitize city_name to prevent path traversal
        import re

        sanitized_name = re.sub(r"[^\w\-]", "_", city_name)
        if sanitized_name != city_name:
            raise ValueError("Invalid city_name: contains unsafe characters")

        base = Path(file_path).resolve()
        auth_path = Path(auth_file_path).resolve()

        # Verify paths are within expected directory
        from shared.paths import cities_pbf_dir, auth_dir

        expected_pbf_root = cities_pbf_dir().resolve()
        expected_auth_root = auth_dir().resolve()

        # Robust directory membership check using pathlib
        def _is_within_directory(path: Path, allowed_root: Path) -> bool:
            """Check if resolved path is contained within allowed_root directory."""
            try:
                # Python 3.9+ has is_relative_to; fallback to parents check for older versions
                if hasattr(path, "is_relative_to"):
                    return path.is_relative_to(allowed_root)
                else:
                    return allowed_root in path.parents or path == allowed_root
            except (ValueError, OSError):
                return False

        if not _is_within_directory(base, expected_pbf_root):
            raise ValueError(f"PBF file path outside expected directory: {base}")

        if not base.is_file():
            raise FileNotFoundError(f"PBF file does not exist: {base}")

        if not _is_within_directory(auth_path, expected_auth_root):
            raise ValueError(f"Auth file path outside expected directory: {auth_path}")

        if not auth_path.is_file():
            raise FileNotFoundError(f"Auth file does not exist: {auth_path}")

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
                str(base),
            )
            subprocess.run(
                [
                    "/osmosis/bin/osmosis",
                    "--read-pbf-fast",
                    f"file={str(base)}",
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
                    f"authFile={auth_path!s}",
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

    def populate_access_graph(self, *, city_id: int, file_path: str) -> None:
        """Build driveway/intersection graph directly from the PBF and store it."""
        metadata.create_all(engine, tables=[AccessNodeAsync, AccessEdgeAsync])

        nodes_payload, edges_payload = build_access_graph(osm_file_path=file_path)

        def _trim(name: Optional[str]) -> Optional[str]:
            if not name:
                return None
            return name[:128]

        with engine.begin() as conn:
            conn.execute(
                text('DELETE FROM "AccessEdges" WHERE id_city = :city_id'),
                {"city_id": city_id},
            )
            conn.execute(
                text('DELETE FROM "AccessNodes" WHERE id_city = :city_id'),
                {"city_id": city_id},
            )

            key_to_db_id = {}
            if nodes_payload:
                node_rows = []
                for node in nodes_payload:
                    tags = node.get("tags") or None
                    node_rows.append(
                        {
                            "id_city": city_id,
                            "source_type": node.get("source_type") or "node",
                            "source_id": node.get("source_id"),
                            "node_type": node.get("node_type"),
                            "longitude": node.get("longitude"),
                            "latitude": node.get("latitude"),
                            "name": _trim(node.get("name")),
                            "tags": (
                                json.dumps(tags, ensure_ascii=True) if tags else None
                            ),
                        }
                    )

                try:
                    result = conn.execute(
                        AccessNodeAsync.insert().returning(
                            AccessNodeAsync.c.id,
                            AccessNodeAsync.c.source_type,
                            AccessNodeAsync.c.source_id,
                        ),
                        node_rows,
                    )

                    key_to_db_id = {
                        f"{row.source_type}:{row.source_id}": row.id for row in result
                    }
                except (CompileError, IntegrityError):
                    max_id = conn.execute(
                        text('SELECT COALESCE(MAX(id), 0) FROM "AccessNodes"')
                    ).scalar_one()
                    next_id = int(max_id or 0)
                    for payload in node_rows:
                        next_id += 1
                        payload_with_id = dict(payload)
                        payload_with_id["id"] = next_id
                        conn.execute(AccessNodeAsync.insert(), payload_with_id)
                        key = f"{payload_with_id['source_type']}:{payload_with_id['source_id']}"
                        key_to_db_id[key] = next_id

            edge_rows = []
            if nodes_payload and edges_payload:
                for edge in edges_payload:
                    src_id = key_to_db_id.get(edge.get("source_key"))
                    dst_id = key_to_db_id.get(edge.get("target_key"))
                    if src_id is None or dst_id is None:
                        continue
                    edge_rows.append(
                        {
                            "id_city": city_id,
                            "id_src": src_id,
                            "id_dst": dst_id,
                            "source_way_id": edge.get("source_way_id"),
                            "road_type": edge.get("road_type", "service"),
                            "length_m": edge.get("length_m"),
                            "is_building_link": bool(
                                edge.get("is_building_link", False)
                            ),
                            "name": _trim(edge.get("name")),
                        }
                    )

            if edge_rows:
                try:
                    conn.execute(AccessEdgeAsync.insert(), edge_rows)
                except IntegrityError:
                    max_edge_id = conn.execute(
                        text('SELECT COALESCE(MAX(id), 0) FROM "AccessEdges"')
                    ).scalar_one()
                    next_edge_id = int(max_edge_id or 0)
                    rows_with_ids = []
                    for payload in edge_rows:
                        next_edge_id += 1
                        row = dict(payload)
                        row["id"] = next_edge_id
                        rows_with_ids.append(row)
                    conn.execute(AccessEdgeAsync.insert(), rows_with_ids)

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
        self.populate_access_graph(city_id=city_id, file_path=file_path)
        self.mark_downloaded(city_id)
