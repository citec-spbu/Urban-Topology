from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query, Request
from uvicorn import run
from os import getenv
from schemas import CityBase, RegionBase, GraphBase, OSMNXGraphBase
from database import database, engine, metadata

import osmnx as ox
import pandas as pd
import geopandas as gpd
import services
import logs 

regions_df = gpd.read_file('./data/regions.json', driver='GeoJSON')
cities_info = pd.read_csv('./data/cities.csv')
app = FastAPI()
logger = logs.init()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://158.160.17.229:4200", "http://0.0.0.0:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await database.connect()
    services.init_db(cities_info=cities_info)

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

if __name__ == "__main__":
    metadata.create_all(engine)
    run("main:app", host="0.0.0.0", port=getenv("PORT", 8901), reload=True)

@app.get("/api/city/", response_model=CityBase)
@logger.catch(exclude=HTTPException)
async def get_city(
    city_id: int
):
    request = f"GET /api/city?city_id={city_id}"
    status_code = 200
    detail = "OK"

    city = await services.get_city(city_id=city_id)
    if city is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)
    
    logger.info(f"{request} {status_code} {detail}")
    return city


@app.get("/api/cities/", response_model=List[CityBase])
@logger.catch(exclude=HTTPException)
async def get_cities(
    page: int = Query(ge=0), 
    per_page : int = Query(gt=0)
): 
    request = f"GET /api/cities?page={page}&per_page={per_page}/"
    status_code = 200
    detail = "OK"

    cities = await services.get_cities(page=page, per_page=per_page)  

    logger.info(f"{request} {status_code} {detail}")
    return cities


@app.get("/api/regions/city/", response_model=List[RegionBase])
@logger.catch(exclude=HTTPException)
async def city_regions(
    city_id: int
): 
    request = f"GET /api/regions/city?city_id={city_id}/"
    status_code = 200
    detail = "OK"

    regions = services.get_regions(city_id=city_id, regions=regions_df, cities=cities_info)
    if regions is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)

    logger.info(f"{request} {status_code} {detail}")
    return regions


@app.post('/api/city/graph/region/', response_model=GraphBase)
@logger.catch(exclude=HTTPException)
async def city_graph(
    city_id: int,
    regions_ids: List[int],
):
    request = f"GET /api/cities/graph/?city_id={city_id}&regions={regions_ids}"
    status_code = 200
    detail = "OK"

    points, edges, pprop, wprop  = await services.graph_from_ids(city_id=city_id, regions_ids=regions_ids, regions=regions_df)
    
    if points is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)

    logger.info(f"{request} {status_code} {detail}")
    return services.graph_to_scheme(points, edges, pprop, wprop)

@app.post('/api/city/osmnx_graph/region/', response_model=OSMNXGraphBase)
@logger.catch(exclude=HTTPException)
async def city_graph(
    city_id: int,
    request: Request,
):
    status_code = 200
    detail = "OK"

    place = get_city_name_by_id(city_id, cities_info)
    coordinates = get_polygon_by_city_name(regions_df, place)
    graph = ox.graph_from_polygon(coordinates, network_type='drive', simplify=True)
    
    nodes, edges = ox.graph_to_gdfs(graph)

    edges_geojson = edges.to_json()
    nodes_geojson = nodes.to_json()

    logger.info(f"{request.url.path} {status_code} {detail}")
    return {"nodes_csv": nodes_geojson, "edges_csv": edges_geojson}

def get_polygon_by_city_name(geo_df, city_name):
    """
    Получает полигон из GeoDataFrame по имени города.

    :param geo_df: GeoDataFrame с геометрией
    :param city_name: Имя города (строка)
    :return: Полигон (shapely.geometry.Polygon) или None, если город не найден
    """
    # Фильтрация по имени города
    filtered = geo_df[(geo_df['admin_level'] == 6.0)&(geo_df['boundary']=='administrative') & ((geo_df['name'] == city_name) | (geo_df['local_name'] == city_name))]

    if filtered.empty:
        return None  # Город не найден
    # Извлечение геометрии
    return filtered.iloc[0].geometry

def get_city_name_by_id(city_id: int, cities_info: pd.DataFrame) -> str:
    """
    Возвращает имя города по его ID.
    :param city_id: Идентификатор города (значение из 'Unnamed: 0').
    :param cities_info: DataFrame с информацией о городах.
    :return: Название города или сообщение, если ID не найден.
    """
    try:
        city_name = cities_info.loc[cities_info['Unnamed: 0'] == (city_id-1), 'Город'].values[0]
        return city_name
    except IndexError:
        return f"Город с ID {city_id} не найден."

@app.post('/api/city/graph/bbox/{city_id}/', response_model=GraphBase)
@logger.catch(exclude=HTTPException)
async def city_graph_poly(
    city_id: int,
    polygons_as_list:  List[List[List[float]]]
):
    request = f"POST /api/city/graph/bbox/{city_id}/"
    status_code = 200
    detail = "OK"

    polygon = services.list_to_polygon(polygons=polygons_as_list)
    points, edges, pprop, wprop = await services.graph_from_poly(city_id=city_id, polygon=polygon)
    
    if points is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)
    
    logger.info(f"{request} {status_code} {detail}")
    return services.graph_to_scheme(points, edges, pprop, wprop)

    

# Useless:

# @app.delete("/api/delete/city/", response_model=CityBase)
# @logger.catch(exclude=HTTPException)
# async def delete_city(
#     city_id: int
# ): 
#     request = f"GET /api/delete/city?city_id={city_id}/"
#     status_code = 200
#     detail = "OK"

#     city = await services.delete_city(city_id=city_id)
#     if city is None:
#         status_code = 404
#         detail = "NOT FOUND"
#         logger.error(f"{request} {status_code} {detail}")
#         raise HTTPException(status_code=status_code, detail=detail)

#     logger.info(f"{request} {status_code} {detail}")
#     return city

# @app.get("/api/download/city/", response_model=CityBase)
# @logger.catch(exclude=HTTPException)
# async def download_city(
#     city_id: int,
#     extension: float
# ): 
#     request = f"GET /api/download/city?city_id={city_id}&extension={extension}/"
#     status_code = 200
#     detail = "OK"

#     city = await services.download_city(city_id=city_id, extension=extension)
#     if city is None:
#         status_code = 404
#         detail = "NOT FOUND"
#         logger.error(f"{request} {status_code} {detail}")
#         raise HTTPException(status_code=status_code, detail=detail)

#     logger.info(f"{request} {status_code} {detail}")
#     return city
