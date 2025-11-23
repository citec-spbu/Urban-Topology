import os
from typing import Optional

from databases import Database
from sqlalchemy import (
    BIGINT,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    VARCHAR,
)
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from shared.datetime_utils import utcnow

DEFAULT_DATABASE_URL = "postgresql://user:password@postgres:5432/fastapi_database"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

metadata = MetaData()

CityAsync = Table(
    "Cities",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True, nullable=False),
    Column("id_property", Integer),
    Column("city_name", VARCHAR(30), unique=True),
    Column("downloaded", Boolean, index=True, default=False),
)

PropertyAsync = Table(
    "Properties",
    metadata,
    Column("id", Integer, primary_key=True, nullable=False, autoincrement=True),
    Column("property", String(50), nullable=False),
)


CityPropertyAsync = Table(
    "CityProperties",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, nullable=False),
    Column("c_latitude", Float, nullable=False),
    Column("c_longitude", Float, nullable=False),
    Column("id_district", Integer),
    Column("id_start_polygon", BigInteger),
    Column("population", Integer),
    Column("population_density", Float, default=0, index=True),
    Column("time_zone", VARCHAR(6)),
    Column(
        "time_created",
        DateTime(timezone=True),
        index=True,
        default=utcnow,
    ),
)


PointAsync = Table(
    "Points",
    metadata,
    Column("id", BIGINT, primary_key=True, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("latitude", Float, nullable=False),
)

WayAsync = Table(
    "Ways",
    metadata,
    Column("id", BigInteger, primary_key=True, nullable=False),
    Column(
        "id_city",
        BigInteger,
        ForeignKey("Cities.id"),
        onupdate="CASCADE",
        nullable=False,
    ),
)

WayPropertyAsync = Table(
    "WayProperties",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, nullable=False),
    Column(
        "id_way", BigInteger, ForeignKey("Ways.id"), onupdate="CASCADE", nullable=False
    ),
    Column("id_property", BigInteger, ForeignKey("Properties.id"), nullable=False),
    Column("value", String, nullable=False),
)


EdgesAsync = Table(
    "Edges",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, nullable=False),
    Column(
        "id_way", BigInteger, ForeignKey("Ways.id"), nullable=False, onupdate="CASCADE"
    ),
    Column(
        "id_src",
        BigInteger,
        ForeignKey("Points.id"),
        nullable=False,
        onupdate="CASCADE",
    ),
    Column(
        "id_dist",
        BigInteger,
        ForeignKey("Points.id"),
        nullable=False,
        onupdate="CASCADE",
    ),
)

PointPropertyAsync = Table(
    "PointProperties",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, nullable=False),
    Column(
        "id_point",
        BigInteger,
        ForeignKey("Points.id"),
        onupdate="CASCADE",
        nullable=False,
    ),
    Column("id_property", Integer, ForeignKey("Properties.id"), nullable=False),
    Column("value", String, nullable=False),
)


AccessNodeAsync = Table(
    "AccessNodes",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True, nullable=False),
    Column(
        "id_city",
        BigInteger,
        ForeignKey("Cities.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("source_type", VARCHAR(16), nullable=False),
    Column("source_id", BigInteger, nullable=True),
    Column("node_type", VARCHAR(16), nullable=False),
    Column("longitude", Float, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("name", VARCHAR(128), nullable=True),
    Column("tags", Text, nullable=True),
)


AccessEdgeAsync = Table(
    "AccessEdges",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True, nullable=False),
    Column(
        "id_city",
        BigInteger,
        ForeignKey("Cities.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "id_src",
        BigInteger,
        ForeignKey(
            "AccessNodes.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    ),
    Column(
        "id_dst",
        BigInteger,
        ForeignKey(
            "AccessNodes.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    ),
    Column("source_way_id", BigInteger, nullable=True),
    Column("road_type", VARCHAR(32), nullable=False),
    Column("length_m", Float, nullable=True),
    Column("is_building_link", Boolean, nullable=False, default=False),
    Column("name", VARCHAR(128), nullable=True),
)


engine = None

database = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False)

_DB_INITIALIZED = False


def configure_database(url: Optional[str] = None, *, echo: bool = True) -> str:
    """Initialize global database connection objects.

    This function is intended to run exactly once at process startup. Re-running it
    after the initial configuration is unsafe in a concurrent environment because
    existing sessions, connections and in-flight transactions may still reference
    the previous engine. For tests, prefer creating isolated engines with
    ``create_test_database`` instead of reconfiguring globals.

    Raises:
        RuntimeError: If called after the database has already been initialized.
    """

    global DATABASE_URL, engine, database, _DB_INITIALIZED

    if _DB_INITIALIZED:
        raise RuntimeError(
            "configure_database() has already been called; runtime reconfiguration is unsafe. "
            "Use create_test_database(url) for isolated test engines instead."
        )

    resolved_url = url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    DATABASE_URL = resolved_url
    engine = create_engine(resolved_url, echo=echo)
    SessionLocal.configure(bind=engine)
    database = Database(resolved_url)
    _DB_INITIALIZED = True
    return resolved_url


def create_test_database(url: str, *, echo: bool = False):
    """Return isolated (engine, session_factory, database) triple for tests.

    Does NOT mutate global engine / session / database, so parallel tests or
    repeated invocations remain safe. The caller is responsible for invoking
    ``metadata.create_all(test_engine)`` and disposing the engine after use.
    """
    test_engine = create_engine(url, echo=echo)
    test_session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    test_database = Database(url)
    return test_engine, test_session_factory, test_database


Base = declarative_base()


# Initialize globals using the resolved DATABASE_URL at import time
configure_database(DATABASE_URL)
