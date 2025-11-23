"""FastAPI lifespan hooks that prepare shared state and bootstrap dependencies."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import geopandas as gpd
import pandas as pd
from fastapi import FastAPI

from application import service_facade
from infrastructure.database import database


def build_lifespan(logger):
    """Return an async lifespan context manager bound to the provided logger."""
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup phase — preload required data files
        regions_file = data_dir / "regions.json"
        if not regions_file.exists():
            error_msg = f"Required data file not found: {regions_file.absolute()}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            app.state.regions_df = gpd.read_file(regions_file)
            logger.info("Loaded regions data from {}", regions_file)
        except Exception as exc:
            error_msg = f"Failed to load regions data from {regions_file}: {exc}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from exc

        cities_file = data_dir / "cities.csv"
        if not cities_file.exists():
            error_msg = f"Required data file not found: {cities_file.absolute()}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            app.state.cities_info = pd.read_csv(cities_file)
            logger.info("Loaded cities data from {}", cities_file)
        except Exception as exc:
            error_msg = f"Failed to load cities data from {cities_file}: {exc}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from exc

        await database.connect()
        service_facade.init_db(cities_info=app.state.cities_info)
        logger.info("Database connected and initialized")

        try:
            yield
        finally:
            await database.disconnect()
            logger.info("Database disconnected")

    return lifespan
