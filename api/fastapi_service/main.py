from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query
from uvicorn import run
from os import getenv
from schemas import CityBase, RegionBase, GraphBase
from database import database, engine, metadata

import pandas as pd
import geopandas as gpd
import services
import logs 
import json
import os
from datetime import datetime

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
    use_cache: bool = True
):
    request = f"GET /api/cities/graph/?city_id={city_id}&regions={regions_ids}"
    status_code = 200
    detail = "OK"

    os.makedirs("./data/caches", exist_ok=True)

    cache_response_file_path = f"./data/caches/{city_id}_{regions_ids}.json"
    if use_cache and os.path.exists(cache_response_file_path):
        with open(cache_response_file_path, 'r') as f:
            return json.load(f)

    print(f"{datetime.now()} graph_from_ids begin")
    points, edges, pprop, wprop, metrics  = await services.graph_from_ids(city_id=city_id, regions_ids=regions_ids, regions=regions_df)
    print(f"{datetime.now()} graph_from_ids end")
    if points is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)

    graphBase = services.graph_to_scheme(points, edges, pprop, wprop, metrics)

    with open (cache_response_file_path, "w+") as f:
        json.dump(graphBase.model_dump(), f)

    logger.info(f"{request} {status_code} {detail}")
    return graphBase


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
    points, edges, pprop, wprop, metrics = await services.graph_from_poly(city_id=city_id, polygon=polygon)
    
    if points is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)
    
    logger.info(f"{request} {status_code} {detail}")
    return services.graph_to_scheme(points, edges, pprop, wprop, metrics)