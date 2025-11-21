from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

import math
from collections import defaultdict

import numpy as np
import osmium as o
from haversine import haversine, Unit

try:
    from scipy.spatial import cKDTree  # type: ignore
except Exception:  # pragma: no cover - optional optimization dependency
    cKDTree = None


required_ways_tags = {
    "highway",
    "junction",
    "lit",
    "surface",
    "maxspeed:type",
    "tunnel",
    "bridge",
    "oneway",
    "living_street",
    "lanes",
    "maxspeed",
    "name",
}
required_point_tags = {
    "population",
    "traffic_signals",
    "crossing",
    "button_operated",
    "traffic_calming",
    "highway",
    "traffic_sign",
    "admin_level",
    "railway",
    "population:date",
    "name",
    "public_transport",
    "motorcar",
}

ACCESS_HIGHWAY_TYPES: Set[str] = {
    "service",
    "residential",
    "living_street",
    "unclassified",
    "tertiary",
    "road",
    "track",
}

ACCESS_SERVICE_VALUES: Set[str] = {
    "driveway",
    "alley",
    "parking_aisle",
    "emergency_access",
}

STANDALONE_BUILDING_TYPES: Set[str] = {
    "yes",
    "house",
    "detached",
    "residential",
    "apartments",
    "industrial",
    "commercial",
    "warehouse",
    "retail",
    "public",
    "school",
    "hospital",
}

DEFAULT_SNAP_DISTANCE_M = 80.0
EARTH_RADIUS_M = 6_371_000.0
_BUCKET_PRECISION = 0.001


@dataclass
class RawNode:
    lon: float
    lat: float
    ways: Set[int] = field(default_factory=set)
    neighbors: Set[int] = field(default_factory=set)


@dataclass
class RawRoad:
    way_id: int
    node_ids: List[int]
    highway: str
    name: Optional[str]
    tags: Dict[str, str]


@dataclass
class RawBuilding:
    osm_id: int
    longitude: float
    latitude: float
    name: Optional[str]
    tags: Dict[str, str]


class _LocalProjector:
    """Project geographic coordinates into a local metric plane for fast math."""

    def __init__(self, origin_lat: float, origin_lon: float) -> None:
        self._origin_lat_rad = math.radians(origin_lat)
        self._origin_lon_rad = math.radians(origin_lon)
        self._cos_origin = math.cos(self._origin_lat_rad)

    @classmethod
    def from_nodes(cls, nodes: Iterable[RawNode]) -> Optional["_LocalProjector"]:
        coords = [(node.lat, node.lon) for node in nodes]
        if not coords:
            return None
        avg_lat = sum(lat for lat, _ in coords) / len(coords)
        avg_lon = sum(lon for _, lon in coords) / len(coords)
        return cls(avg_lat, avg_lon)

    def project(self, lat: float, lon: float) -> Tuple[float, float]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        x = EARTH_RADIUS_M * (lon_rad - self._origin_lon_rad) * self._cos_origin
        y = EARTH_RADIUS_M * (lat_rad - self._origin_lat_rad)
        return (x, y)


class HighwayWaysHandler(o.SimpleHandler):
    """Collect highway ways that match the allowed road types."""

    def __init__(self):
        super(HighwayWaysHandler, self).__init__()
        self.required_road_types = {
            "motorway",
            "trunk",
            "primary",
            "secondary",
            "tertiary",
            "unclassified",
            "residential",
            "road",
            "living_street",
        }  # add "service" or "pedestrian" if those ways should be ingested
        self.used_nodes_ids = {}
        self.ways_tags = {}

    def way(self, w):
        if ("highway" in w.tags) and (
            w.tags.get("highway") in self.required_road_types
        ):
            self.ways_tags[w.id] = {tag.k: tag.v for tag in w.tags}
            # If a way is missing "name", we can later try to infer it from nodes

            graph = []
            for i in range(0, len(w.nodes) - 1):
                graph.append([int(w.nodes[i].ref), int(w.nodes[i + 1].ref)])
                self.used_nodes_ids[int(w.nodes[i].ref)] = {
                    "lat": w.nodes[i].lat,
                    "lon": w.nodes[i].lon,
                }

            i = len(w.nodes) - 1
            self.used_nodes_ids[int(w.nodes[i].ref)] = {
                "lat": w.nodes[i].lat,
                "lon": w.nodes[i].lon,
            }
            self.ways_tags[w.id]["graph"] = graph


class HighwayNodesHandler(o.SimpleHandler):
    """Populate node-level metadata for the way nodes discovered earlier."""

    def __init__(self, used_nodes_ids):
        super(HighwayNodesHandler, self).__init__()
        self.nodes_tags = used_nodes_ids

    def node(self, n):
        if n.id in self.nodes_tags.keys():
            dct = {tag.k: tag.v for tag in n.tags}
            if len(dct) == 0:
                return

            for k, v in dct.items():
                self.nodes_tags[n.id][k] = v


def parse_osm(osm_file_path) -> Tuple[dict, dict]:
    """Parse the provided OSM PBF file and return dictionaries of ways and nodes."""
    ways = HighwayWaysHandler()
    try:
        ways.apply_file(osm_file_path, locations=False)
    except RuntimeError:
        pass
    nodes = HighwayNodesHandler(ways.used_nodes_ids)
    try:
        nodes.apply_file(osm_file_path, locations=False)
    except RuntimeError:
        pass

    return ways.ways_tags, nodes.nodes_tags


class AccessGraphHandler(o.SimpleHandler):
    """Collect residential/driveway ways and standalone buildings for access graph."""

    def __init__(
        self,
        highway_types: Optional[Iterable[str]] = None,
        building_types: Optional[Iterable[str]] = None,
    ) -> None:
        super().__init__()
        self.highway_types: Set[str] = set(highway_types or ACCESS_HIGHWAY_TYPES)
        self.building_types: Set[str] = set(building_types or STANDALONE_BUILDING_TYPES)
        self.roads: List[RawRoad] = []
        self.nodes: Dict[int, RawNode] = {}
        self.buildings: List[RawBuilding] = []

    def way(self, way):  # type: ignore[override]
        tags = {tag.k: tag.v for tag in way.tags}
        self._collect_roads(way, tags)
        self._collect_buildings(way, tags)

    def _collect_roads(self, way, tags: Dict[str, str]) -> None:
        highway = tags.get("highway")
        service = tags.get("service")
        if highway not in self.highway_types and not (
            highway == "service" and service in ACCESS_SERVICE_VALUES
        ):
            return

        node_ids: List[int] = []
        for node in way.nodes:
            if not node.location.valid():
                continue
            node_id = int(node.ref)
            raw_node = self.nodes.get(node_id)
            if raw_node is None:
                raw_node = RawNode(lon=node.lon, lat=node.lat)
                self.nodes[node_id] = raw_node
            raw_node.ways.add(int(way.id))
            node_ids.append(node_id)

        if len(node_ids) < 2:
            return

        for src, dst in zip(node_ids, node_ids[1:]):
            self.nodes[src].neighbors.add(dst)
            self.nodes[dst].neighbors.add(src)

        self.roads.append(
            RawRoad(
                way_id=int(way.id),
                node_ids=node_ids,
                highway=highway,
                name=tags.get("name"),
                tags=tags,
            )
        )

    def _collect_buildings(self, way, tags: Dict[str, str]) -> None:
        building = tags.get("building")
        if not building:
            return

        if (
            self.building_types
            and building not in self.building_types
            and building != "yes"
        ):
            return

        coords: List[Tuple[float, float]] = []
        for node in way.nodes:
            if not node.location.valid():
                continue
            coords.append((node.lon, node.lat))

        centroid = _polygon_centroid(coords)
        if centroid is None:
            return

        self.buildings.append(
            RawBuilding(
                osm_id=int(way.id),
                longitude=centroid[0],
                latitude=centroid[1],
                name=tags.get("name") or tags.get("addr:housename"),
                tags=tags,
            )
        )


class _AccessGraphAssembler:
    """Transform raw handler output into node/edge payloads."""

    def __init__(
        self,
        *,
        nodes: Dict[int, RawNode],
        roads: List[RawRoad],
        buildings: List[RawBuilding],
        snap_distance_m: float = DEFAULT_SNAP_DISTANCE_M,
    ) -> None:
        self.nodes = nodes
        self.roads = roads
        self.buildings = buildings
        self.snap_distance_m = snap_distance_m
        self._bucket: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        self._bucket_ready = False
        self._projector: Optional[_LocalProjector] = None
        self._node_ids: List[int] = []
        self._node_xy: Optional[np.ndarray] = None
        self._spatial_index = None
        self._init_spatial_index()

    def build(self) -> Tuple[List[dict], List[dict]]:
        if not self.nodes:
            return [], []

        intersections = self._intersection_ids()
        building_links = self._snap_buildings()
        for _, node_id, _ in building_links:
            intersections.add(node_id)

        node_payloads = self._serialize_intersection_nodes(intersections)
        node_payloads.extend(self._serialize_building_nodes(building_links))

        edges = self._serialize_road_edges(intersections)
        edges.extend(self._serialize_building_edges(building_links))
        return node_payloads, edges

    def _serialize_intersection_nodes(self, intersections: Set[int]) -> List[dict]:
        payloads: List[dict] = []
        for node_id in sorted(intersections):
            node = self.nodes.get(node_id)
            if node is None:
                continue
            payloads.append(
                {
                    "key": self._node_key(node_id),
                    "source_type": "node",
                    "source_id": node_id,
                    "node_type": "intersection",
                    "longitude": node.lon,
                    "latitude": node.lat,
                    "name": None,
                    "tags": None,
                }
            )
        return payloads

    def _serialize_building_nodes(
        self, building_links: List[Tuple[RawBuilding, int, float]]
    ) -> List[dict]:
        payloads: List[dict] = []
        seen: Set[int] = set()
        for building, _, _ in building_links:
            if building.osm_id in seen:
                continue
            seen.add(building.osm_id)
            payloads.append(
                {
                    "key": self._building_key(building.osm_id),
                    "source_type": "building",
                    "source_id": building.osm_id,
                    "node_type": "building",
                    "longitude": building.longitude,
                    "latitude": building.latitude,
                    "name": building.name,
                    "tags": building.tags,
                }
            )
        return payloads

    def _serialize_road_edges(self, intersections: Set[int]) -> List[dict]:
        edges: List[dict] = []
        for road in self.roads:
            start_node: Optional[int] = None
            path: List[int] = []
            for node_id in road.node_ids:
                if node_id not in self.nodes:
                    continue
                path.append(node_id)
                if node_id in intersections:
                    if start_node is None:
                        start_node = node_id
                        path = [node_id]
                        continue
                    if start_node == node_id:
                        path = [node_id]
                        continue
                    length_m = self._path_length(path)
                    if length_m <= 0:
                        start_node = node_id
                        path = [node_id]
                        continue
                    src_key = self._node_key(start_node)
                    dst_key = self._node_key(node_id)
                    edges.extend(self._edge_payloads(road, src_key, dst_key, length_m))
                    start_node = node_id
                    path = [node_id]
        return edges

    def _serialize_building_edges(
        self, building_links: List[Tuple[RawBuilding, int, float]]
    ) -> List[dict]:
        edges: List[dict] = []
        for building, node_id, distance in building_links:
            building_key = self._building_key(building.osm_id)
            intersection_key = self._node_key(node_id)
            payload = {
                "source_key": building_key,
                "target_key": intersection_key,
                "source_way_id": None,
                "road_type": "building_link",
                "length_m": distance,
                "is_building_link": True,
                "name": building.name,
            }
            edges.append(payload)
            edges.append(
                {**payload, "source_key": intersection_key, "target_key": building_key}
            )
        return edges

    def _edge_payloads(
        self, road: RawRoad, src_key: str, dst_key: str, length_m: float
    ) -> List[dict]:
        payload = {
            "source_key": src_key,
            "target_key": dst_key,
            "source_way_id": road.way_id,
            "road_type": road.highway,
            "length_m": length_m,
            "is_building_link": False,
            "name": road.name,
        }
        edges = [payload]
        oneway = str(road.tags.get("oneway", "")).lower() in {"yes", "1", "true"}
        if not oneway:
            edges.append({**payload, "source_key": dst_key, "target_key": src_key})
        return edges

    def _intersection_ids(self) -> Set[int]:
        intersections: Set[int] = set()
        for node_id, node in self.nodes.items():
            neighbor_count = len(node.neighbors)
            way_count = len(node.ways)
            if neighbor_count != 2 or way_count > 1:
                intersections.add(node_id)
        return intersections

    def _snap_buildings(self) -> List[Tuple[RawBuilding, int, float]]:
        links: List[Tuple[RawBuilding, int, float]] = []
        if not self.buildings:
            return links
        for building in self.buildings:
            node_id, distance = self._nearest_node(
                building.latitude, building.longitude
            )
            if node_id is None or distance is None:
                continue
            if distance > self.snap_distance_m:
                continue
            links.append((building, node_id, distance))
        return links

    def _nearest_node(
        self, lat: float, lon: float
    ) -> Tuple[Optional[int], Optional[float]]:
        node_id, distance = self._nearest_node_via_tree(lat, lon)
        if node_id is not None:
            return node_id, distance
        return self._nearest_node_linear(lat, lon)

    def _nearest_node_via_tree(
        self, lat: float, lon: float
    ) -> Tuple[Optional[int], Optional[float]]:
        if (
            self._spatial_index is None
            or self._projector is None
            or self._node_xy is None
            or not self._node_ids
        ):
            return None, None
        try:
            x, y = self._projector.project(lat, lon)
            distance, idx = self._spatial_index.query((x, y), k=1)
        except Exception:
            return None, None
        if not math.isfinite(distance):
            return None, None
        if isinstance(idx, np.ndarray):  # pragma: no cover - k>1 safeguard
            idx = int(idx[0])
        if idx >= len(self._node_ids):
            return None, None
        node_id = self._node_ids[idx]
        node = self.nodes.get(node_id)
        if node is None:
            return None, None
        exact_distance = haversine((lat, lon), (node.lat, node.lon), unit=Unit.METERS)
        return node_id, exact_distance

    def _nearest_node_linear(
        self, lat: float, lon: float
    ) -> Tuple[Optional[int], Optional[float]]:
        if not self._bucket_ready:
            self._build_bucket()
        bucket = self._bucket_key(lat, lon)
        candidates: List[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                candidates.extend(
                    self._bucket.get((bucket[0] + dx, bucket[1] + dy), [])
                )
        if not candidates:
            candidates = list(self.nodes.keys())
        nearest_node = None
        nearest_distance = None
        for node_id in candidates:
            node = self.nodes.get(node_id)
            if node is None:
                continue
            distance = haversine((lat, lon), (node.lat, node.lon), unit=Unit.METERS)
            if nearest_distance is None or distance < nearest_distance:
                nearest_node = node_id
                nearest_distance = distance
        return nearest_node, nearest_distance

    def _build_bucket(self) -> None:
        for node_id, node in self.nodes.items():
            key = self._bucket_key(node.lat, node.lon)
            self._bucket[key].append(node_id)
        self._bucket_ready = True

    def _init_spatial_index(self) -> None:
        if not self.nodes or cKDTree is None:
            return
        projector = _LocalProjector.from_nodes(self.nodes.values())
        if projector is None:
            return
        coords: List[Tuple[float, float]] = []
        ids: List[int] = []
        for node_id, node in self.nodes.items():
            ids.append(node_id)
            coords.append(projector.project(node.lat, node.lon))
        if not coords:
            return
        self._projector = projector
        self._node_ids = ids
        self._node_xy = np.array(coords, dtype=float)
        try:
            self._spatial_index = cKDTree(self._node_xy)
        except Exception:
            self._spatial_index = None

    @staticmethod
    def _bucket_key(lat: float, lon: float) -> Tuple[int, int]:
        return (
            math.floor(lat / _BUCKET_PRECISION),
            math.floor(lon / _BUCKET_PRECISION),
        )

    def _path_length(self, node_ids: List[int]) -> float:
        length = 0.0
        for src, dst in zip(node_ids, node_ids[1:]):
            first = self.nodes.get(src)
            second = self.nodes.get(dst)
            if first is None or second is None:
                continue
            length += haversine(
                (first.lat, first.lon),
                (second.lat, second.lon),
                unit=Unit.METERS,
            )
        return length

    @staticmethod
    def _node_key(node_id: int) -> str:
        return f"node:{node_id}"

    @staticmethod
    def _building_key(osm_id: int) -> str:
        return f"building:{osm_id}"


def _polygon_centroid(
    coords: List[Tuple[float, float]],
) -> Optional[Tuple[float, float]]:
    if not coords:
        return None
    if len(coords) < 3:
        lon = sum(x for x, _ in coords) / len(coords)
        lat = sum(y for _, y in coords) / len(coords)
        return lon, lat
    points = coords[:]
    if points[0] != points[-1]:
        points.append(points[0])
    area = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if math.isclose(area, 0.0):
        lon = sum(x for x, _ in coords) / len(coords)
        lat = sum(y for _, y in coords) / len(coords)
        return lon, lat
    area *= 0.5
    cx /= 6.0 * area
    cy /= 6.0 * area
    return cx, cy


def build_access_graph(
    osm_file_path: str,
    *,
    highway_types: Optional[Iterable[str]] = None,
    building_types: Optional[Iterable[str]] = None,
    snap_distance_m: float = DEFAULT_SNAP_DISTANCE_M,
) -> Tuple[List[dict], List[dict]]:
    """Return node/edge payloads for the residential access graph."""
    handler = AccessGraphHandler(
        highway_types=highway_types,
        building_types=building_types,
    )
    try:
        handler.apply_file(osm_file_path, locations=True)
    except RuntimeError:
        return [], []

    assembler = _AccessGraphAssembler(
        nodes=handler.nodes,
        roads=handler.roads,
        buildings=handler.buildings,
        snap_distance_m=snap_distance_m,
    )
    return assembler.build()
