from sqlalchemy import(
    Column,
    Integer,
    VARCHAR,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    String,
    BigInteger,
    BIGINT
)
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from databases import Database

DATABASE_URL = "postgresql://user:password@postgres:5432/fastapi_database"

metadata = MetaData()

CityAsync = Table(
    "Cities",
    metadata,
    Column("id", BigInteger, primary_key = True, autoincrement=True, nullable=True),
    Column("id_property", Integer),
    Column("city_name", VARCHAR(30), unique=True),
    Column("downloaded", Boolean, index=True, default=False),
)

PropertyAsync = Table(
    "Properties",
    metadata,
    Column("id", Integer, primary_key=True, nullable=False, autoincrement=True),
    Column("property", String(50), nullable=False)
)


CityPropertyAsync = Table(
    "CityProperties",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, nullable=True),
    Column("c_latitude", Float, nullable=True),
    Column("c_longitude", Float),
    Column("id_district", Integer),
    Column("id_start_polygon", BigInteger),
    Column("population", Integer),
    Column("population_density", Float, default=0, index=True),
    Column("time_zone", VARCHAR(6)),
    Column("time_created", DateTime, index=True, default=datetime.utcnow),
)


PointAsync = Table(
    "Points",
    metadata,
    Column("id", BIGINT, primary_key=True, nullable=False),
    Column("longitude", Float),
    Column("latitude", Float),
)

WayAsync = Table(
    "Ways",
    metadata,
    Column("id", BigInteger, primary_key=True, nullable=False),
    Column("id_city", BigInteger, ForeignKey("Cities.id"), onupdate="CASCADE", nullable=False)
)

WayPropertyAsync = Table(
    "WayProperties",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, nullable=False),
    Column("id_way", BigInteger, ForeignKey("Ways.id"),onupdate="CASCADE", nullable=False),
    Column("id_property", BigInteger, ForeignKey("Properties.id"), nullable=False),
    Column("value", String, nullable=False),
)


EdgesAsync = Table(
    "Edges",
    metadata,
    Column("id",  Integer, primary_key=True, autoincrement=True, nullable=False),
    Column("id_way", BigInteger, ForeignKey("Ways.id"), nullable=False,onupdate="CASCADE"),
    Column("id_src", BigInteger, ForeignKey("Points.id"), nullable= False,onupdate="CASCADE"),
    Column("id_dist", BigInteger, ForeignKey("Points.id"), nullable=False,onupdate="CASCADE")
)

PointPropertyAsync = Table(
    "PointProperties",
    metadata,
    Column("id",Integer, primary_key=True, autoincrement=True, nullable=False),
    Column("id_point", BigInteger, ForeignKey("Points.id"), onupdate="CASCADE", nullable=False),
    Column("id_property", Integer, ForeignKey("Properties.id"), nullable=False),
    Column("value", String, nullable=False)
)


engine = create_engine(DATABASE_URL, echo=True)

database = Database(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()