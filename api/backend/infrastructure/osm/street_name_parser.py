import os
from re import search

from dadata import Dadata

try:  # graceful fallback for environments without osmium binary wheels
    from osmium.osm._osm import WayNodeList
except ImportError:  # pragma: no cover
    WayNodeList = list  # type: ignore

regex = r",( (ул|пр) ([\w\s-]+))|( ([\w\s-]+) (пр-д|пл)),"


def _get_dadata_token() -> str:
    token = os.getenv("DADATA_TOKEN")
    if not token:
        raise RuntimeError(
            "DADATA_TOKEN environment variable is required for DaData street name parsing."
        )
    return token


def parse_name(nodes_list):
    """Infer a street name for the provided OSM way nodes using DaData geolocation."""
    dadata = Dadata(_get_dadata_token())

    length = len(nodes_list)
    for i in range(0, length - 1):
        try:
            lat = (nodes_list[i].location.lat + nodes_list[i + 1].location.lat) / 2
            lon = (nodes_list[i].location.lon + nodes_list[i + 1].location.lon) / 2
        except Exception:
            continue

        data = dadata.geolocate(name="address", lat=lat, lon=lon, count=1)
        if len(data) == 0:
            continue
        data = data[0].get("value")
        if data is None:
            continue
        match = search(regex, data)
        try:
            if match.group(2):
                street_type = match.group(2)
                if street_type == "ул":
                    street_name = match.group(3) + str(" улица")
                else:
                    street_name = str("проезд ") + match.group(3)
            elif match.group(6):
                street_type = match.group(6)
                if street_type == "пл":
                    street_name = match.group(5) + str(" площадь")
                else:
                    street_name = match.group(5) + str(" проезд")
            else:
                continue

            return street_name
        except Exception:
            continue

    return "-"
