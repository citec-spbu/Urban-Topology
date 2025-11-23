"""Tests for shared.paths helpers."""

from __future__ import annotations

from pathlib import Path

from shared import paths


def test_cities_pbf_dir_prefers_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CITIES_PBF_DIR", str(tmp_path))

    result = paths.cities_pbf_dir()

    assert result == tmp_path


def test_city_pbf_path_builds_filename(monkeypatch, tmp_path):
    monkeypatch.setenv("CITIES_PBF_DIR", str(tmp_path))

    city_path = paths.city_pbf_path("Sample")

    assert city_path == tmp_path / "Sample.pbf"
    assert isinstance(city_path, Path)
