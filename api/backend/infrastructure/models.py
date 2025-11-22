from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Boolean, DateTime, Float, BigInteger
from sqlalchemy.dialects.mysql import VARCHAR

from infrastructure.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class City(Base):
    __tablename__ = "Cities"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=True)
    id_property = Column(type_=Integer)
    city_name = Column(type_=VARCHAR(30), unique=True)
    downloaded = Column(type_=Boolean, index=True, default=False)


class CityProperty(Base):
    __tablename__ = "CityProperties"

    id = Column(type_=Integer, primary_key=True, autoincrement=True, nullable=True)
    c_latitude = Column(type_=Float)
    c_longitude = Column(type_=Float)
    id_district = Column(type_=BigInteger)
    id_start_polygon = Column(type_=Integer)
    population = Column(type_=Integer)
    population_density = Column(type_=Float, default=0, index=True)
    time_zone = Column(type_=VARCHAR(6))
    time_created = Column(type_=DateTime(timezone=True), index=True, default=utcnow)


class Point(Base):
    __tablename__ = "Points"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=True)
    longitude = Column(type_=Float)
    latitude = Column(type_=Float)


class AccessNode(Base):
    __tablename__ = "AccessNodes"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=False)
    id_city = Column(type_=BigInteger)
    source_type = Column(type_=VARCHAR(16))
    source_id = Column(type_=BigInteger)
    node_type = Column(type_=VARCHAR(16))
    longitude = Column(type_=Float)
    latitude = Column(type_=Float)
    name = Column(type_=VARCHAR(128))
    tags = Column(type_=VARCHAR(1024))


class AccessEdge(Base):
    __tablename__ = "AccessEdges"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=False)
    id_city = Column(type_=BigInteger)
    id_src = Column(type_=BigInteger)
    id_dst = Column(type_=BigInteger)
    source_way_id = Column(type_=BigInteger)
    road_type = Column(type_=VARCHAR(32))
    length_m = Column(type_=Float)
    is_building_link = Column(type_=Boolean, default=False)
    name = Column(type_=VARCHAR(128))
