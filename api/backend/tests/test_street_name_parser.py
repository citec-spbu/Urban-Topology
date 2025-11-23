"""Tests for street_name_parser utilities."""

from __future__ import annotations

from infrastructure.osm import street_name_parser as parser


def test_parse_name_returns_dash_when_no_data(monkeypatch):
    monkeypatch.setenv("DADATA_TOKEN", "test-token")

    class _FakeDadata:
        def __init__(self, token):  # pragma: no cover - unused
            pass

        def geolocate(self, **kwargs):
            return []

    monkeypatch.setattr(parser, "Dadata", _FakeDadata)

    nodes = []
    result = parser.parse_name(nodes)

    assert result == "-"


def test_parse_name_extracts_street_from_response(monkeypatch):
    class _FakeNode:
        def __init__(self, lat, lon):
            self.location = type("Loc", (), {"lat": lat, "lon": lon})()

    class _FakeDadata:
        def __init__(self, token):
            self.token = token

        def geolocate(self, **kwargs):
            return [{"value": "г. Тест, ул Ленина,"}]

    monkeypatch.setattr(parser, "Dadata", _FakeDadata)
    monkeypatch.setenv("DADATA_TOKEN", "test-token")

    nodes = [_FakeNode(0, 0), _FakeNode(1, 1)]
    result = parser.parse_name(nodes)

    assert result == "Ленина улица"
