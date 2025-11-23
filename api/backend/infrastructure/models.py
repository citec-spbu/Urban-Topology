from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    DateTime,
    Float,
    BigInteger,
    ForeignKey,
    String,
    Text,
)

from infrastructure.database import Base
from shared.datetime_utils import utcnow


class City(Base):
    __tablename__ = "Cities"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=False)
    id_property = Column(type_=Integer)
    city_name = Column(type_=String(30), unique=True)
    downloaded = Column(type_=Boolean, index=True, default=False)


class CityProperty(Base):
    __tablename__ = "CityProperties"

    id = Column(type_=Integer, primary_key=True, autoincrement=True, nullable=False)
    c_latitude = Column(type_=Float, nullable=False)
    c_longitude = Column(type_=Float, nullable=False)
    id_district = Column(type_=Integer)
    id_start_polygon = Column(type_=BigInteger)
    population = Column(type_=Integer)
    population_density = Column(type_=Float, default=0, index=True)
    time_zone = Column(type_=String(6))
    time_created = Column(type_=DateTime(timezone=True), index=True, default=utcnow)


class Point(Base):
    __tablename__ = "Points"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=False)
    longitude = Column(type_=Float, nullable=False)
    latitude = Column(type_=Float, nullable=False)


class AccessNode(Base):
    __tablename__ = "AccessNodes"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=False)
    id_city = Column(
        BigInteger,
        ForeignKey("Cities.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = Column(type_=String(16), nullable=False)
    source_id = Column(type_=BigInteger)
    node_type = Column(type_=String(16), nullable=False)
    longitude = Column(type_=Float, nullable=False)
    latitude = Column(type_=Float, nullable=False)
    name = Column(type_=String(128))
    tags = Column(type_=Text)


class AccessEdge(Base):
    __tablename__ = "AccessEdges"

    id = Column(type_=BigInteger, primary_key=True, autoincrement=True, nullable=False)
    id_city = Column(
        BigInteger,
        ForeignKey("Cities.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    id_src = Column(
        BigInteger,
        ForeignKey("AccessNodes.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    id_dst = Column(
        BigInteger,
        ForeignKey("AccessNodes.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    source_way_id = Column(type_=BigInteger)
    road_type = Column(type_=String(32), nullable=False)
    length_m = Column(type_=Float)
    is_building_link = Column(type_=Boolean, default=False, nullable=False)
    name = Column(type_=String(128))
