"""Utility helpers for working with filesystem locations used by the service."""

from __future__ import annotations

import os
from pathlib import Path


def cities_pbf_dir() -> Path:
    """Resolve the directory that stores downloaded city PBF files."""
    env_path = os.environ.get("CITIES_PBF_DIR")
    if env_path:
        return Path(env_path).expanduser()

    repo_root = Path(__file__).resolve().parents[3]
    default_top_level = repo_root / "cities_pbf"

    # Inside Docker images the repo root resolves to "/", which still gives us
    # a predictable "/cities_pbf" path that we can mount to via docker-compose.
    if repo_root == Path("/"):
        return Path("/cities_pbf")

    return default_top_level


def city_pbf_path(city_name: str) -> Path:
    """Build a full path to the given city's PBF file."""
    return cities_pbf_dir() / f"{city_name}.pbf"
