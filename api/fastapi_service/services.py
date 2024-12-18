from database import engine, Base, SessionLocal, database, DATABASE_URL
from models import City, CityProperty, Point
from shapely.geometry.point import Point as ShapelyPoint
from database import *
from schemas import CityBase, PropertyBase, PointBase, RegionBase, GraphBase
from shapely.geometry.multilinestring import MultiLineString
from shapely.geometry.linestring import LineString
from shapely.geometry.polygon import Polygon
from shapely.ops import unary_union
from geopandas.geodataframe import GeoDataFrame
from pandas.core.frame import DataFrame
from osm_handler import parse_osm
from typing import List, Iterable, Union, TYPE_CHECKING
from sqlalchemy import update, text
from datetime import datetime

import pandas as pd
import osmnx as ox
import os.path
import ast
import io
import pandas as pd
import networkx as nx
import time
import networkx as nx
import logging

# Создайте или получите корневой логгер SQLAlchemy, установите уровень WARNING
log = logging.getLogger('sqlalchemy.engine')
log.setLevel(logging.WARNING)

# Убедитесь, что обработчик лога убран, если он уже установлен
if log.hasHandlers():
    log.handlers.clear()

# Если вы хотите полностью убрать любой вывод, вы можете добавить "глушитель":
log.addHandler(logging.NullHandler())


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


AUTH_FILE_PATH = "./data/db.properties"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:        
        db.close()


def point_to_scheme(point : Point) -> PointBase:
    if point is None:
        return None

    return PointBase(latitude=point.latitude, longitude=point.longitude)


def list_to_csv_str(data, columns : List['str']):
    buffer = io.StringIO()
    df = pd.DataFrame(data, columns=columns)
    df.to_csv(buffer, index=False)
    return buffer.getvalue(), df

def graph_to_scheme(points, edges, pprop, wprop, metrics) -> GraphBase:
    edges_str, edges_df = list_to_csv_str(edges, ['id', 'id_way', 'source', 'target', 'name'])
    points_str, _ = list_to_csv_str(points, ['id', 'longitude', 'latitude'])
    pprop_str, _ = list_to_csv_str(pprop, ['id', 'property', 'value'])
    wprop_str, _ = list_to_csv_str(wprop, ['id', 'property', 'value'])
    metrics_str, _ = list_to_csv_str(metrics, ['id', 'degree', 'in_degree', 'out_degree', 'eigenvector', 'betweenness', 'radius', 'color'])

    return GraphBase(edges_csv=edges_str, points_csv=points_str, 
                     ways_properties_csv=wprop_str, points_properties_csv=pprop_str,
                     metrics_csv=metrics_str)


async def property_to_scheme(property : CityProperty) -> PropertyBase:
    if property is None:
        return None

    return PropertyBase(population=property.population, population_density=property.population_density, 
                        time_zone=property.time_zone, time_created=str(property.time_created),
                        c_latitude = property.c_latitude, c_longitude = property.c_longitude)


async def city_to_scheme(city : City) -> CityBase:
    if city is None:
        return None

    city_base = CityBase(id=city.id, city_name=city.city_name, downloaded=city.downloaded)
    query = CityPropertyAsync.select().where(CityPropertyAsync.c.id == city.id_property)
    property = await database.fetch_one(query)
    property_base = await property_to_scheme(property=property)
    city_base.property = property_base
    
    return city_base


async def cities_to_scheme_list(cities : List[City]) -> List[CityBase]:
    schemas = []
    for city in cities:
        schemas.append(await city_to_scheme(city=city))
    return schemas


async def get_cities(page: int, per_page: int) -> List[CityBase]:
    query = CityAsync.select()
    cities = await database.fetch_all(query)
    cities = cities[page * per_page : (page + 1) * per_page]
    return await cities_to_scheme_list(cities)


async def get_city(city_id: int) -> CityBase:
    query = CityAsync.select().where(CityAsync.c.id == city_id)
    city = await database.fetch_one(query)
    return await city_to_scheme(city=city)


def add_info_to_db(city_df : DataFrame):
    city_name = city_df['Город']
    query = CityAsync.select().where(CityAsync.c.city_name == city_name)
    conn = engine.connect()
    city_db = conn.execute(query).first()
    downloaded = False
    if city_db is None:
        property_id = add_property_to_db(df=city_df)
        city_id = add_city_to_db(df=city_df, property_id=property_id)
    else:
        downloaded = city_db.downloaded
        city_id = city_db.id
    conn.close()
    file_path = f'./data/cities_osm/{city_name}.pbf'
    if (not downloaded) and (os.path.exists(file_path)):
        print("ANDO NOW IM HERE")
        add_graph_to_db(city_id=city_id, file_path=file_path, city_name=city_name)


def add_graph_to_db(city_id: int, file_path: str, city_name: str) -> None:
        try:
            conn = engine.connect()
            # with open("/osmosis/script/pgsimple_schema_0.6.sql", "r") as f:
            #     query = text(f.read())
            #     conn.execute(query) -U user -d fastapi_database
            command = f"psql {DATABASE_URL} -f /osmosis/script/pgsimple_schema_0.6.sql"
            res = os.system(command)

            required_road_types = ('motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'road', 'unclassified', 'residential',
                                   'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link') # , 'residential','living_street'
            
            road_file_path = file_path[:-8] + "_highway.pbf"
            command = f'''/osmosis/bin/osmosis --read-pbf-fast file="{file_path}" --tf accept-ways highway={",".join(required_road_types)} \
                          --tf reject-ways side_road=yes --used-node --write-pbf omitmetadata=true file="{road_file_path}" \
                          && /osmosis/bin/osmosis --read-pbf-fast file="{road_file_path}" --write-pgsimp authFile="{AUTH_FILE_PATH}" \
                          && rm "{road_file_path}"
                       '''
            res = os.system(command)     

            # Вставка в Ways
            query = text(
                f"""
                INSERT INTO "Ways" (id, id_city)
                SELECT w.id,
                {city_id}
                FROM ways w
                ;
                """
            )
            # WHERE wt.k LIKE 'highway'
            # AND wt.v IN ({"'"+"', '".join(required_road_types)+"'"})
            # query = WayAsync.insert().from_select(["id", "id_city"], select_query)
            res = conn.execute(query)

            # Вставка в Points
            query = text(
                """INSERT INTO "Points" ("id", "longitude", "latitude")
                SELECT DISTINCT n.id,
                ST_X(n.geom) AS longitude, 
                ST_Y(n.geom) AS latitude
                FROM nodes n
                JOIN way_nodes wn ON wn.node_id = n.id
                JOIN "Ways" w ON w.id = wn.way_id;
                """)
            # query = PointAsync.insert().from_select(["id", "longitude", "latitude"], select_query)
            res = conn.execute(query)

            # Вставка в Properties
            query = text(
                """INSERT INTO "Properties" (property)
                SELECT DISTINCT k AS property
                FROM
                (
                    SELECT DISTINCT nt.k
                    FROM node_tags nt
                    JOIN "Points" p ON p.id = nt.node_id
                    UNION
                    SELECT DISTINCT wt.k
                    FROM way_tags wt
                    JOIN "Ways" w ON w.id = wt.way_id
                ) keys
                WHERE NOT EXISTS (SELECT * FROM "Properties" pr WHERE keys.k = pr.property)
                """
            )
            res = conn.execute(query)

            # Вставка в WayProperties, используя значения из Properties
            query = text(
                """INSERT INTO "WayProperties" (id_way, id_property, value)
                SELECT wt.way_id,
                p.id,
                wt.v
                FROM way_tags wt
                JOIN "Ways" w ON w.id = wt.way_id
                JOIN "Properties" p ON p.property LIKE wt.k
                """
            )
            res = conn.execute(query)

            # Вставка в PointProperties, используя значения из Properties
            query = text(
                """INSERT INTO "PointProperties" (id_point, id_property, value)
                SELECT nt.node_id,
                pr.id,
                nt.v
                FROM node_tags nt
                JOIN "Points" pt ON pt.id = nt.node_id
                JOIN "Properties" pr ON pr.property LIKE nt.k
                """
            )
            res = conn.execute(query)

            # Вставка в Edges дорог с пометкой oneway
            query = text(
                """INSERT INTO "Edges" (id_way, id_src, id_dist)
                SELECT 
                wn.way_id,
                wn.node_id,
                wn2.node_id
                FROM "Ways" w
                JOIN way_nodes wn ON wn.way_id = w.id 
                JOIN way_tags wt ON wt.way_id = wn.way_id 
                JOIN way_nodes wn2 ON wn2.way_id = wn.way_id 
                WHERE wt.k like 'oneway'
                AND wt.v like 'yes'
                AND wn.sequence_id + 1 = wn2.sequence_id
                ORDER BY wn.sequence_id;
                """
            )
            res = conn.execute(query)

            # Вставка в Edges дорог без пометки oneway
            query = text(
                """WITH oneway_way_id AS (
                SELECT
                    w.id
                FROM ways w
                JOIN way_tags wt ON wt.way_id = w.id 
                WHERE (wt.k like 'oneway'
                AND wt.v like 'yes')
                )
                INSERT INTO "Edges" (id_way, id_src, id_dist)
                SELECT 
                wn.way_id,
                wn.node_id,
                wn2.node_id
                FROM "Ways" w
                JOIN way_nodes wn ON wn.way_id = w.id
                JOIN way_nodes wn2 ON wn2.way_id = wn.way_id 
                WHERE w.id NOT IN (SELECT id FROM oneway_way_id)
                AND wn.sequence_id + 1 = wn2.sequence_id
                ORDER BY wn.sequence_id;
                """
            )
            res = conn.execute(query)

            # Вставка в Edges обратных дорог без пометки oneway
            query = text(
                """WITH oneway_way_id AS (
                SELECT
                    w.id
                FROM ways w
                JOIN way_tags wt ON wt.way_id = w.id 
                WHERE (wt.k like 'oneway'
                AND wt.v like 'yes')
                )
                INSERT INTO "Edges" (id_way, id_src, id_dist)
                SELECT 
                wn.way_id,
                wn2.node_id,
                wn.node_id
                FROM "Ways" w
                JOIN way_nodes wn ON wn.way_id = w.id
                JOIN way_nodes wn2 ON wn2.way_id = wn.way_id 
                WHERE w.id NOT IN (SELECT id FROM oneway_way_id)
                AND wn.sequence_id + 1 = wn2.sequence_id
                ORDER BY wn2.sequence_id DESC;
                """
            )
            res = conn.execute(query)

            query = update(CityAsync).where(CityAsync.c.id == f"{city_id}").values(downloaded = True)
            conn.execute(query)

            conn.close()
        except Exception:
            print(f"Can't download {city_name} with id {city_id}")
        

def add_point_to_db(df : DataFrame) -> int:
    with SessionLocal.begin() as session:
        point = Point(latitude=float(df['Широта']), longitude=float(df['Долгота']))
        session.add(point)
        session.flush()
        return point.id


def add_property_to_db(df : DataFrame) -> int:
    with SessionLocal.begin() as session:
        property = CityProperty(c_latitude=float(df['Широта']), c_longitude=float(df['Долгота']), population=int(df['Население']), time_zone=df['Часовой пояс'])
        session.add(property)
        session.flush()
        return property.id


def add_city_to_db(df : DataFrame, property_id : int) -> int:
    with SessionLocal.begin() as session:
        city = City(city_name=df['Город'], id_property=property_id)
        session.add(city)
        session.flush()
        return city.id


def init_db(cities_info : DataFrame):
    for row in range(0, cities_info.shape[0]):
        add_info_to_db(cities_info.loc[row, :])


def to_list(polygon : LineString):
    list = []
    for x, y in polygon.coords:
        list.append([x, y])
    return list


def to_json_array(polygon):
    coordinates_list = []
    if type(polygon) == LineString:
       coordinates_list.append(to_list(polygon))
    elif type(polygon) == MultiLineString:
        for line in polygon.geoms:
            coordinates_list.append(to_list(line))
    else:
        raise ValueError("polygon must be type of LineString or MultiLineString")

    return coordinates_list


def region_to_schemas(regions : GeoDataFrame, ids_list : List[int], admin_level : int) -> List[RegionBase]:
    regions_list = [] 
    polygons = regions[regions['osm_id'].isin(ids_list)]
    for _, row in polygons.iterrows():
        id = row['osm_id']
        name = row['local_name']
        regions_array = to_json_array(row['geometry'].boundary)
        base = RegionBase(id=id, name=name, admin_level=admin_level, regions=regions_array)
        regions_list.append(base)

    return regions_list


def children(ids_list : List[int], admin_level : int, regions : GeoDataFrame):
    area = regions[regions['parents'].str.contains('|'.join(str(x) for x in ids_list), na=False)]
    area = area[area['admin_level']==admin_level]
    lst = area['osm_id'].to_list()
    if len(lst) == 0:
        return ids_list, False
    return lst, True


def get_admin_levels(city : City, regions : GeoDataFrame, cities : DataFrame) -> List[RegionBase]:
    regions_list = []

    levels_str = cities[cities['Город'] == city.city_name]['admin_levels'].values[0]
    levels = ast.literal_eval(levels_str)

    info = regions[regions['local_name']==city.city_name].sort_values(by='admin_level')
    ids_list = [info['osm_id'].to_list()[0]]

    schemas = region_to_schemas(regions=regions, ids_list=ids_list, admin_level=levels[0])
    regions_list.extend(schemas)
    for level in levels:
        ids_list, data_valid = children(ids_list=ids_list, admin_level=level, regions=regions)
        if data_valid:
            schemas = region_to_schemas(regions=regions, ids_list=ids_list, admin_level=level)
            regions_list.extend(schemas)

    return regions_list


def get_regions(city_id : int, regions : GeoDataFrame, cities : DataFrame) -> List[RegionBase]:
    with SessionLocal.begin() as session:
        city = session.query(City).get(city_id)
        if city is None:
            return None
        return get_admin_levels(city=city, regions=regions, cities=cities)


def list_to_polygon(polygons : List[List[List[float]]]):
    return unary_union([Polygon(polygon) for polygon in polygons])


def polygons_from_region(regions_ids : List[int], regions : GeoDataFrame):
    if len(regions_ids) == 0:
        return None
    polygons = regions[regions['osm_id'].isin(regions_ids)]
    return unary_union([geom for geom in polygons['geometry'].values])


async def graph_from_ids(city_id : int, regions_ids : List[int], regions : GeoDataFrame):
    print(f"{datetime.now()} polygons_from_region begin")
    polygon = polygons_from_region(regions_ids=regions_ids, regions=regions)
    print(f"{datetime.now()} polygons_from_region end")
    if polygon == None:
        return None, None, None, None, None
    print(f"{datetime.now()} graph_from_poly begin")
    gfp = await graph_from_poly(city_id=city_id, polygon=polygon)
    print(f"{datetime.now()} graph_from_poly end")
    return gfp

def point_obj_to_list(db_record) -> List:
    return [db_record.id, db_record.longitude, db_record.latitude]


def edge_obj_to_list(db_record) -> List:
    return [db_record.id, db_record.id_way, db_record.id_src, db_record.id_dist, db_record.value]


def record_obj_to_wprop(record):
    return [record.id_way, record.property ,record.value]


def record_obj_to_pprop(record):
    return [record.id_point ,record.property ,record.value]


async def graph_from_poly(city_id, polygon):
    bbox = polygon.bounds   # min_lon, min_lat, max_lon, max_lat

    q = CityAsync.select().where(CityAsync.c.id == city_id)
    city = await database.fetch_one(q)
    if city is None or not city.downloaded:
        return None, None, None, None
    
    print(f"{datetime.now()} q1 begin")
    query = text(
        f"""SELECT p.id, p.longitude, p.latitude 
        FROM "Points" p
        JOIN "Edges" e ON e.id_src = p.id 
        JOIN "Ways" w ON e.id_way = w.id 
        WHERE w.id_city = {city_id}
        AND (p.longitude BETWEEN {bbox[0]} AND {bbox[2]})
        AND (p.latitude BETWEEN {bbox[1]} AND {bbox[3]});
        """
    )
    print(f"{datetime.now()} q1 end")

    print(f"{datetime.now()} fetch_all begin")
    res = await database.fetch_all(query)
    points = list(map(point_obj_to_list, res)) # [...[id, longitude, latitude]...]
    print(f"{datetime.now()} fetch_all end")

    print(f"{datetime.now()} q2 begin")
    q = PropertyAsync.select().where(PropertyAsync.c.property == 'name')
    prop = await database.fetch_one(q)
    prop_id_name = prop.id
    print(f"{datetime.now()} q2 end")

    print(f"{datetime.now()} q3 begin")
    q = PropertyAsync.select().where(PropertyAsync.c.property == 'highway')
    prop = await database.fetch_one(q)
    prop_id_highway = prop.id
    print(f"{datetime.now()} q3 end")

    print(f"{datetime.now()} q4 begin")
    road_types = ('motorway', 'trunk', 'primary', 'secondary', 'tertiary',
                  'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link')
    road_types_query = build_in_query('wp_h.value', road_types)
    print("Start getting edges")
    query = text(f"""
        WITH named_streets AS 
        (
            SELECT 
            e.id AS id, e.id_way AS id_way, e.id_src AS id_src, e.id_dist AS id_dist, wp_n.value AS value
            FROM "Edges" e 
            JOIN "WayProperties" wp_n 
            ON wp_n.id_way = e.id_way
            AND wp_n.id_property = {prop_id_name}
            JOIN "WayProperties" wp_h 
            ON wp_h.id_way = e.id_way
            AND wp_h.id_property = {prop_id_highway}
            JOIN "Ways" w ON w.id = e.id_way 
            JOIN "Points" p ON p.id = e.id_src 
            WHERE w.id_city = {city_id}
            AND (p.longitude BETWEEN {bbox[0]} AND {bbox[2]})
            AND (p.latitude BETWEEN {bbox[1]} AND {bbox[3]})
        )
        , unnamed_streets AS 
        (
            SELECT
            e.id AS id, e.id_way AS id_way, e.id_src AS id_src, e.id_dist AS id_dist, NULL AS value
            FROM "Edges" e 
            JOIN "Ways" w ON w.id = e.id_way 
            JOIN "Points" p ON p.id = e.id_src
            LEFT JOIN "WayProperties" wp_n 
            ON wp_n.id_way = e.id_way
            AND wp_n.id_property = {prop_id_name}
            JOIN "WayProperties" wp_h 
            ON wp_h.id_way = e.id_way
            AND wp_h.id_property = {prop_id_highway}
            WHERE wp_n.value is NULL
            and {road_types_query}
            AND w.id_city = {city_id}
            AND (p.longitude BETWEEN {bbox[0]} AND {bbox[2]})
            AND (p.latitude BETWEEN {bbox[1]} AND {bbox[3]})
        )
        SELECT id, id_way, id_src, id_dist, value
        FROM named_streets
        UNION
        SELECT id, id_way, id_src, id_dist, value
        FROM unnamed_streets;
    """
    )

    res = await database.fetch_all(query)
    edges = list(map(edge_obj_to_list, res)) # [...[id, id_way, from, to, name]...]
    print(f"{datetime.now()} q4 end")

    print(f"{datetime.now()} filter by polygon begin")
    points, edges, ways_prop_ids, points_prop_ids  = filter_by_polygon(polygon=polygon, edges=edges, points=points)
    print(f"{datetime.now()} filter by polygon end")

    conn = engine.connect()

    print(f"{datetime.now()} q5 begin")
    ids_ways = build_in_query('id_way', ways_prop_ids)
    # print("ids_ways content:", ids_ways)
    query = text(
        f"""
        SELECT
            id_way,
            property,
            value
        FROM (
            SELECT
                id_way,
                id_property,
                value
            FROM "WayProperties" WHERE {ids_ways}
        ) AS p 
        JOIN "Properties"
        ON p.id_property = "Properties".id;
        """)

    # res = conn.execute(query).fetchall()
    res = await database.fetch_all(query)
    ways_prop = list(map(record_obj_to_wprop, res))
    print(f"{datetime.now()} q5 end")

    print(f"{datetime.now()} q6 begin")

    ids_points = build_in_query('id_point', points_prop_ids)

    metadata = MetaData()

    # Определите временную таблицу (например, для PostgreSQL)
    temp_table = Table(
        'temp_ids_point', metadata,
        Column('id_point', Integer, primary_key=True)
    )

    # Создайте временную таблицу
    conn.execute(text("CREATE TEMPORARY TABLE temp_ids_point (id_point BIGINT PRIMARY KEY);"))
    
    # Заполните временную таблицу данными из id_list
    conn.execute(temp_table.insert(), [{'id_point': id} for id in points_prop_ids])

    # print("ids_points content:", ids_points)
    query = text(
        f"""
        SELECT
            id_point,
            property,
            value
        FROM (
            SELECT
                pp.id_point as id_point,
                pp.id_property as id_property,
                pp.value as value
            FROM "PointProperties" pp
            JOIN "temp_ids_point" t
            ON pp.id_point = t.id_point
        ) AS p 
        JOIN "Properties" ON p.id_property = "Properties".id;
        """)

    res = conn.execute(query).fetchall()
    conn.execute(text("DROP TABLE temp_ids_point;"))
    # res = await database.fetch_all(query)
    points_prop = list(map(record_obj_to_pprop, res))

    # conn.close()

    print(f"{datetime.now()} q6 end")
    print(f"{datetime.now()} metrics begin")

    oneway_ids = await get_oneway_ids(city_id=city_id)
    metrics = await calc_metrics(points, edges, oneway_ids)

    print(f"{datetime.now()} metrics end")

    return points, edges, points_prop, ways_prop, metrics


def build_in_query(query_field : str, values : Iterable[Union[int, str]]):
    first_value = next(iter(values))
    if isinstance(first_value, str):
        elements = "', '".join(values)
        buffer = f"{query_field} IN ('{elements}')"
        return buffer
    else:
    # if isinstance(first_value, int):
        elements = ", ".join(map(str, values))
        buffer = f"{query_field} IN ({elements})"
        return buffer
    # return ""


def filter_by_polygon(polygon, edges, points):
    points_ids = set()
    ways_prop_ids = set()
    points_filtred = []
    edges_filtred = []

    for point in points:
        lon = point[1]
        lat = point[2]
        if polygon.contains(ShapelyPoint(lon, lat)):
            points_ids.add(point[0])
            points_filtred.append(point)

    for edge in edges:
        id_from = edge[2]
        id_to = edge[3]
        if (id_from in points_ids) and (id_to in points_ids):
            edges_filtred.append(edge)
            ways_prop_ids.add(edge[1])

    return points_filtred, edges_filtred, ways_prop_ids, points_ids

async def get_oneway_ids(city_id: int) -> List[int]:
    query = text(
        """
        SELECT DISTINCT wp.id_way
        FROM "WayProperties" wp
        JOIN "Properties" p ON wp.id_property = p.id
        JOIN "Ways" w ON w.id = wp.id_way
        WHERE p.property = 'oneway' AND wp.value = 'yes' AND w.id_city = :city_id;
        """
    )
    with engine.connect() as conn:
        result = conn.execute(query, {"city_id": city_id}).fetchall()
        return [row[0] for row in result]

async def calc_metrics(points, edges, oneway_ids):
    points_list = [point[0] for point in points]
    edges_list = [(edge[2], edge[3]) for edge in edges]  # Ориентированные ребра
    reversed_edges_list = [(edge[3], edge[2]) for edge in edges if edge[1] not in oneway_ids]  # Обратные ребра для двусторонних дорог
    
    print(f"{datetime.now()} calc metrics begin")
    print(f"{datetime.now()} graph building begin")
    G = nx.DiGraph()  # Ориентированный граф
    G.add_nodes_from(points_list)
    G.add_edges_from(edges_list)  # Добавляем основные направления
    G.add_edges_from(reversed_edges_list)  # Добавляем обратные направления для двусторонних дорог
    print(f"{datetime.now()} graph building end")

    print(f"{datetime.now()} degree begin")
    degree_dict = nx.degree(G)
    in_degree_dict = nx.in_degree_centrality(G)
    out_degree_dict = nx.out_degree_centrality(G)
    print(f"{datetime.now()} degree end")
    
    print(f"{datetime.now()} eigenvector begin")
    eigenvector_dict = nx.eigenvector_centrality(G, max_iter=1000)
    print(f"{datetime.now()} eigenvector end")
    
    print(f"{datetime.now()} betweenness begin")
    betweenness_dict = nx.betweenness_centrality(G, k=100)
    print(f"{datetime.now()} betweenness end")
    
    betweenness_values = betweenness_dict.values()

    max_betweenness = max(betweenness_values)
    min_betweenness = min(betweenness_values)

    adjusted_max_betweenness = 1 if max_betweenness == 0 else max_betweenness

    metrics_list = []
    for node_id in in_degree_dict:
        node_betweenness = betweenness_dict[node_id]
        normalized_betweenness = node_betweenness / adjusted_max_betweenness
        radius = get_radius_based_on_metric(normalized_betweenness)
        color = get_color_from_blue_to_red(node_betweenness, min_betweenness, max_betweenness)

        metrics_list.append(
            [
                node_id,
                degree_dict[node_id],
                in_degree_dict[node_id],  # Входящая степень
                out_degree_dict[node_id],  # Исходящая степень
                eigenvector_dict[node_id],
                node_betweenness,
                radius,
                color                
            ]
        )
    print(f"{datetime.now()} calc metrics end")
    
    return metrics_list

def get_radius_based_on_metric(value: float) -> float:
    """
    Возвращает радиус, основанный на значении метрики.
    """
    return 1 + 10 * value


def get_color_from_blue_to_red(value: float, min_value: float, max_value: float) -> str:
    """
    Возвращает цвет от синего к красному на основе значения в диапазоне.
    
    :param value: Текущее значение метрики
    :param min_value: Минимальное значение метрики
    :param max_value: Максимальное значение метрики
    :return: Цвет в формате 'rgb(r, g, b)'
    """
    if max_value == min_value:
        # Если все значения одинаковые, возвращаем базовый цвет (например, черный)
        return "rgb(0, 0, 0)"
    
    # Линейная нормализация значения в диапазоне [0, 1]
    normalized_value = (value - min_value) / (max_value - min_value)
    
    # Интерполяция между синим и красным
    red = int(255 * normalized_value)  # Увеличиваем красный с увеличением значения
    green = 0  # Зеленый отсутствует
    blue = int(255 * (1 - normalized_value))  # Уменьшаем синий с увеличением значения

    return f"rgb({red}, {green}, {blue})"
