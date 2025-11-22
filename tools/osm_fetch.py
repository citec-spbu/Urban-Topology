"""Utilities for downloading OpenStreetMap extracts via Overpass or OSMnx."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import osmnx as ox
import requests

import logging

logger = logging.getLogger(__name__)

USER_AGENT = "Urban-Topology-Analysis-Service/api"
DEFAULT_HEADERS = {
    "Connection": "keep-alive",
    "sec-ch-ua": '"Not-A.Brand";v="99", "Opera";v="91", "Chromium";v="105"',
    "Accept": "*/*",
    "Sec-Fetch-Dest": "empty",
    "User-Agent": USER_AGENT,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://overpass-turbo.eu",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Referer": "https://overpass-turbo.eu/",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "dnt": "1",
}


def osmfetch(
    title: str,
    bbox: Sequence[float],
    save_directory: str | Path,
    expansion: float = 0.0,
    headers: dict | None = None,
) -> Path:
    """Fetch an OSM extract for the bbox and save the .osm file into save_directory."""
    bbox_list = list(bbox)
    if len(bbox_list) != 4:
        raise ValueError(
            "bbox must contain exactly 4 coordinates: south, west, north, east"
        )
    if expansion < 0:
        raise ValueError("expansion must be non-negative")

    height = bbox_list[2] - bbox_list[0]
    width = bbox_list[3] - bbox_list[1]
    lat_delta = round(expansion / 200 * height, 8)
    lon_delta = round(expansion / 200 * width, 8)
    bbox_list[0] -= lat_delta
    bbox_list[1] -= lon_delta
    bbox_list[2] += lat_delta
    bbox_list[3] += lon_delta

    query = f"nwr ({bbox_list[0]}, {bbox_list[1]}, {bbox_list[2]}, {bbox_list[3]});out geom;"
    body = {"data": query}
    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        headers=headers or DEFAULT_HEADERS,
        data=body,
        timeout=120,
    )

    if response.status_code != 200:
        title = f"status_code_{response.status_code}"

    destination_dir = Path(save_directory)
    destination_dir.mkdir(parents=True, exist_ok=True)
    full_path = destination_dir / f"{title}.osm"
    full_path.write_text(response.text, encoding="utf-8")
    return full_path


def download_city(
    city_name: str, *, save_directory: str | Path = ".", expansion: float = 10
) -> Path | None:
    """Geocode the city with OSMnx and download its OSM extract via `osmfetch`."""
    query = {"city": city_name}
    try:
        city_info = ox.geocode_to_gdf(query)
    except ValueError:
        logger.error(f"Invalid city name: {city_name}")
        return None

    north = city_info.iloc[0]["bbox_north"]
    south = city_info.iloc[0]["bbox_south"]
    east = city_info.iloc[0]["bbox_east"]
    west = city_info.iloc[0]["bbox_west"]

    return osmfetch(
        title=city_name,
        bbox=[south, west, north, east],
        save_directory=save_directory,
        expansion=expansion,
    )
