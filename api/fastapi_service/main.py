from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query
from uvicorn import run
from os import getenv
from schemas import CityBase, RegionBase, GraphBase
from database import database, engine, metadata
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
import geopandas as gpd
import services
import logs
import json
import os
from datetime import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Load data files
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))

    # Load regions GeoJSON
    regions_file = data_dir / "regions.json"
    if not regions_file.exists():
        error_msg = f"Required data file not found: {regions_file.absolute()}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        app.state.regions_df = gpd.read_file(regions_file)
        logger.info(f"Loaded regions data from {regions_file}")
    except Exception as e:
        error_msg = f"Failed to load regions data from {regions_file}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    # Load cities CSV
    cities_file = data_dir / "cities.csv"
    if not cities_file.exists():
        error_msg = f"Required data file not found: {cities_file.absolute()}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        app.state.cities_info = pd.read_csv(cities_file)
        logger.info(f"Loaded cities data from {cities_file}")
    except Exception as e:
        error_msg = f"Failed to load cities data from {cities_file}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    # Connect to database
    await database.connect()
    services.init_db(cities_info=app.state.cities_info)
    logger.info("Database connected and initialized")

    yield

    # Shutdown
    await database.disconnect()
    logger.info("Database disconnected")


app = FastAPI(lifespan=lifespan)
logger = logs.init()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://158.160.17.229:4200",
        "http://0.0.0.0:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    metadata.create_all(engine)
    run("main:app", host="0.0.0.0", port=int(getenv("PORT", "8901")), reload=True)


@app.get("/api/city/", response_model=CityBase)
@logger.catch(exclude=HTTPException)
async def get_city(city_id: int):
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
async def get_cities(page: int = Query(ge=0), per_page: int = Query(gt=0)):
    request = f"GET /api/cities?page={page}&per_page={per_page}/"
    status_code = 200
    detail = "OK"

    cities = await services.get_cities(page=page, per_page=per_page)

    logger.info(f"{request} {status_code} {detail}")
    return cities


@app.get("/api/regions/city/", response_model=List[RegionBase])
@logger.catch(exclude=HTTPException)
async def city_regions(city_id: int):
    request = f"GET /api/regions/city?city_id={city_id}/"
    status_code = 200
    detail = "OK"

    regions = services.get_regions(
        city_id=city_id, regions=app.state.regions_df, cities=app.state.cities_info
    )
    if regions is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)

    logger.info(f"{request} {status_code} {detail}")
    return regions


@app.post("/api/city/graph/region/", response_model=GraphBase)
@logger.catch(exclude=HTTPException)
async def city_graph(city_id: int, regions_ids: List[int], use_cache: bool = True):
    request = f"GET /api/cities/graph/?city_id={city_id}&regions={regions_ids}"
    status_code = 200
    detail = "OK"

    try:
        os.makedirs("./data/caches", exist_ok=True)

        cache_response_file_path = f"./data/caches/{city_id}_{regions_ids}.json"
        if use_cache and os.path.exists(cache_response_file_path):
            with open(cache_response_file_path, "r") as f:
                return json.load(f)

        print(f"{datetime.now()} graph_from_ids begin")
        points, edges, pprop, wprop, metrics = await services.graph_from_ids(
            city_id=city_id, regions_ids=regions_ids, regions=app.state.regions_df
        )
        print(f"{datetime.now()} graph_from_ids end")

        if points is None:
            status_code = 404
            detail = f"Region not found or city {city_id} not downloaded. Requested regions: {regions_ids}"
            logger.error(f"{request} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail)

        # Check if graph is empty
        if len(points) == 0 or len(edges) == 0:
            status_code = 422
            detail = f"No road network data found for region(s) {regions_ids} in city {city_id}. The data for this region has not been downloaded from OSM yet. Please ensure the region data is downloaded before requesting the graph."
            logger.error(f"{request} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail)

        graphBase = services.graph_to_scheme(points, edges, pprop, wprop, metrics)

        with open(cache_response_file_path, "w+") as f:
            # Support both Pydantic v1 and v2: prefer model_dump() (v2), fallback to dict() (v1)
            data = (
                graphBase.model_dump()
                if hasattr(graphBase, "model_dump")
                else graphBase.dict()
            )
            json.dump(data, f)

        logger.info(f"{request} {status_code} {detail}")
        return graphBase

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Catch any other unexpected errors and provide detailed error message
        status_code = 500
        error_type = type(e).__name__
        error_msg = str(e)
        detail = f"Internal server error processing graph for city {city_id}, regions {regions_ids}. Error: {error_type}: {error_msg}"
        logger.exception(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail) from e


@app.post("/api/city/graph/bbox/{city_id}/", response_model=GraphBase)
@logger.catch(exclude=HTTPException)
async def city_graph_poly(city_id: int, polygons_as_list: List[List[List[float]]]):
    request = f"POST /api/city/graph/bbox/{city_id}/"
    status_code = 200
    detail = "OK"

    polygon = services.list_to_polygon(polygons=polygons_as_list)
    points, edges, pprop, wprop, metrics = await services.graph_from_poly(
        city_id=city_id, polygon=polygon
    )

    if points is None:
        status_code = 404
        detail = "NOT FOUND"
        logger.error(f"{request} {status_code} {detail}")
        raise HTTPException(status_code=status_code, detail=detail)

    logger.info(f"{request} {status_code} {detail}")
    return services.graph_to_scheme(points, edges, pprop, wprop, metrics)
