"""Build a graph for a selected region and compute centrality metrics."""

import asyncio
import logging
from typing import List, Dict, Tuple
from math import radians, cos, sin, asin, sqrt

import networkx as nx

from application.converters import (
    point_obj_to_list,
    edge_obj_to_list,
    record_obj_to_wprop,
    record_obj_to_pprop,
    access_node_obj_to_list,
    access_edge_obj_to_list,
)
from application.ingestion.utils import add_graph_to_db
from infrastructure.repositories.cities import CityRepository
from infrastructure.repositories.graph import GraphRepository
from shared.paths import city_pbf_path


logger = logging.getLogger(__name__)


async def graph_from_poly(city_id, polygon):
    repo_city = CityRepository()
    city = await repo_city.by_id(city_id)
    if city is None:
        return None, None, None, None, None, None, None

    if not city.downloaded:
        city_name = city["city_name"]
        pbf_path = city_pbf_path(city_name)

        if not pbf_path.exists():
            logger.warning(
                "Graph for city %s is requested but PBF is missing at %s",
                city_id,
                pbf_path,
            )
            return None, None, None, None, None, None, None

        logger.info(
            "City %s graph not in DB; attempting on-demand import from %s",
            city_id,
            pbf_path,
        )

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                add_graph_to_db,
                city_id,
                str(pbf_path),
                city_name,
            )
        except Exception:
            logger.exception(
                "Failed to import graph for city %s from %s",
                city_id,
                pbf_path,
            )
            return None, None, None, None, None, None, None

        city = await repo_city.by_id(city_id)
        if city is None or not city.downloaded:
            logger.error(
                "Graph import for city %s completed but city still not marked as downloaded",
                city_id,
            )
            return None, None, None, None, None, None, None

    polygon_wkt = polygon.wkt

    repo_graph = GraphRepository()

    # Fetch property identifiers required for graph queries
    prop_id_name = await repo_graph.property_id("name")
    prop_id_highway = await repo_graph.property_id("highway")

    if prop_id_name is None:
        logger.error(
            "Missing property id for 'name' (city_id=%s); graph build aborted",
            city_id,
        )
        return None, None, None, None, None, None, None

    if prop_id_highway is None:
        logger.error(
            "Missing property id for 'highway' (city_id=%s); graph build aborted",
            city_id,
        )
        return None, None, None, None, None, None, None

    # Retrieve points inside the polygon (PostGIS)
    res_points = await repo_graph.points_in_polygon(city_id, polygon_wkt)
    points = list(map(point_obj_to_list, res_points))

    # Filter edges by polygon bounds and road types (PostGIS)
    road_types = (
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "motorway_link",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
    )
    res_edges = await repo_graph.edges_in_polygon(
        city_id=city_id,
        polygon_wkt=polygon_wkt,
        prop_id_name=prop_id_name,
        prop_id_highway=prop_id_highway,
        highway_types=road_types,
        require_both_endpoints=True,
        use_midpoint=False,
    )
    edges = list(map(edge_obj_to_list, res_edges))

    # Collect property identifiers from selected entities
    ways_prop_ids = {e[1] for e in edges}
    points_prop_ids = {p[0] for p in points}

    res = await repo_graph.way_props(ways_prop_ids)
    ways_prop = list(map(record_obj_to_wprop, res))

    res = repo_graph.point_props_via_temp(points_prop_ids)
    points_prop = list(map(record_obj_to_pprop, res))

    access_nodes_raw = await repo_graph.access_nodes_in_polygon(
        city_id=city_id, polygon_wkt=polygon_wkt
    )
    access_edges_raw = await repo_graph.access_edges_in_polygon(
        city_id=city_id, polygon_wkt=polygon_wkt
    )
    access_nodes = list(map(access_node_obj_to_list, access_nodes_raw))
    access_edges = list(map(access_edge_obj_to_list, access_edges_raw))

    points, edges, access_nodes, access_edges = merge_close_nodes(
        points, edges, access_nodes, access_edges, threshold_meters=5.0
    )

    points, edges, access_nodes, access_edges = filter_largest_component(
        points, edges, access_nodes, access_edges
    )

    oneway_ids = await repo_graph.oneway_ids(city_id=city_id)
    metrics = await calc_metrics(points, edges, access_nodes, access_edges, oneway_ids)

    return (
        points,
        edges,
        points_prop,
        ways_prop,
        metrics,
        access_nodes,
        access_edges,
    )


async def calc_metrics(points, edges, access_nodes, access_edges, oneway_ids):
    # Empty graph means no metrics to compute
    if not points and not access_nodes:
        return []

    points_list = [point[0] for point in points]
    access_points_list = [node[0] for node in access_nodes]

    oneway_ids_set = set(oneway_ids)
    directed_edges = {(edge[2], edge[3]) for edge in edges}
    directed_edges.update(
        (edge[3], edge[2]) for edge in edges if edge[1] not in oneway_ids_set
    )

    # Access layer edges are modeled as bidirectional connectors.
    for edge in access_edges:
        source, target = edge[1], edge[2]
        directed_edges.add((source, target))
        directed_edges.add((target, source))

    G = nx.DiGraph()
    G.add_nodes_from(points_list)
    G.add_nodes_from(access_points_list)
    G.add_edges_from(directed_edges)

    degree_dict = nx.degree(G)
    in_degree_dict = nx.in_degree_centrality(G)
    out_degree_dict = nx.out_degree_centrality(G)

    try:
        eigenvector_dict = nx.eigenvector_centrality(G, max_iter=1000)
    except Exception:
        eigenvector_dict = {n: 0.0 for n in G.nodes}

    try:
        k = min(100, max(1, G.number_of_nodes()))
        betweenness_dict = nx.betweenness_centrality(G, k=k)
    except Exception:
        betweenness_dict = {n: 0.0 for n in G.nodes}

    betweenness_values = betweenness_dict.values()
    if betweenness_values:
        max_betweenness = max(betweenness_values)
        min_betweenness = min(betweenness_values)
    else:
        max_betweenness = 0.0
        min_betweenness = 0.0

    adjusted_max_betweenness = 1 if max_betweenness == 0 else max_betweenness

    metrics_list = []
    for node_id in G.nodes:
        node_betweenness = betweenness_dict[node_id]
        normalized_betweenness = node_betweenness / adjusted_max_betweenness
        radius = get_radius_based_on_metric(normalized_betweenness)
        color = get_color_from_blue_to_red(
            node_betweenness, min_betweenness, max_betweenness
        )

        metrics_list.append(
            [
                node_id,
                degree_dict[node_id],
                in_degree_dict[node_id],
                out_degree_dict[node_id],
                eigenvector_dict[node_id],
                node_betweenness,
                radius,
                color,
            ]
        )

    return metrics_list


def get_radius_based_on_metric(value: float) -> float:
    return 1 + 10 * value


def get_color_from_blue_to_red(value: float, min_value: float, max_value: float) -> str:
    if max_value == min_value:
        return "rgb(0, 0, 0)"
    normalized_value = (value - min_value) / (max_value - min_value)
    red = int(255 * normalized_value)
    green = 0
    blue = int(255 * (1 - normalized_value))
    return f"rgb({red}, {green}, {blue})"


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate the great circle distance in meters between two points
    on the earth (specified in decimal degrees).
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r


def merge_close_nodes(
    points: List[List],
    edges: List[List],
    access_nodes: List[List],
    access_edges: List[List],
    threshold_meters: float = 5.0,
) -> Tuple[List[List], List[List], List[List], List[List]]:
    """
    Merge nodes that are within threshold_meters of each other.
    Returns filtered points, edges, access_nodes, access_edges and node mapping.

    points: [id, longitude, latitude]
    edges: [id, id_way, source, target, name]
    access_nodes: [id, node_type, longitude, latitude, source_type, source_id, name]
    access_edges: [id, source, target, source_way_id, road_type, length_m, is_building_link, name]
    """
    all_nodes = {}
    for point in points:
        all_nodes[point[0]] = {
            "lon": point[1],
            "lat": point[2],
            "type": "base",
            "data": point,
        }

    for node in access_nodes:
        all_nodes[node[0]] = {
            "lon": node[2],
            "lat": node[3],
            "type": "access",
            "data": node,
        }

    node_ids = list(all_nodes.keys())
    merged_groups = []
    processed = set()

    for i, node_id in enumerate(node_ids):
        if node_id in processed:
            continue

        node_info = all_nodes[node_id]
        group = [node_id]
        processed.add(node_id)

        for j in range(i + 1, len(node_ids)):
            other_id = node_ids[j]
            if other_id in processed:
                continue

            other_info = all_nodes[other_id]
            distance = haversine_distance(
                node_info["lon"], node_info["lat"], other_info["lon"], other_info["lat"]
            )

            if distance <= threshold_meters:
                group.append(other_id)
                processed.add(other_id)

        merged_groups.append(group)

    node_mapping = {}
    for group in merged_groups:
        representative = group[0]
        for node_id in group:
            node_mapping[node_id] = representative

    filtered_points = []
    filtered_access_nodes = []
    seen_representatives = set()

    for node_id in node_mapping.values():
        if node_id not in seen_representatives:
            seen_representatives.add(node_id)
            node_info = all_nodes[node_id]
            if node_info["type"] == "base":
                filtered_points.append(node_info["data"])
            else:
                filtered_access_nodes.append(node_info["data"])

    filtered_edges = []
    seen_edges = set()

    for edge in edges:
        edge_id, id_way, source, target, name = edge[:5]
        new_source = node_mapping.get(source, source)
        new_target = node_mapping.get(target, target)

        if new_source == new_target:
            continue

        edge_key = (new_source, new_target)
        if edge_key in seen_edges:
            continue

        seen_edges.add(edge_key)
        filtered_edges.append([edge_id, id_way, new_source, new_target, name])

    filtered_access_edges = []
    seen_access_edges = set()

    for edge in access_edges:
        # [id, source, target, source_way_id, road_type, length_m, is_building_link, name]
        edge_id = edge[0]
        source = edge[1]
        target = edge[2]
        rest = edge[3:] if len(edge) > 3 else []

        new_source = node_mapping.get(source, source)
        new_target = node_mapping.get(target, target)

        if new_source == new_target:
            continue

        edge_key = (new_source, new_target)
        if edge_key in seen_access_edges:
            continue

        seen_access_edges.add(edge_key)
        filtered_access_edges.append([edge_id, new_source, new_target] + rest)

    logger.info(
        "[MERGE] Merged nodes: %d -> %d (removed %d close nodes within %.1fm)",
        len(all_nodes),
        len(filtered_points) + len(filtered_access_nodes),
        len(all_nodes) - (len(filtered_points) + len(filtered_access_nodes)),
        threshold_meters,
    )

    return (
        filtered_points,
        filtered_edges,
        filtered_access_nodes,
        filtered_access_edges,
    )


def filter_largest_component(
    points: List[List],
    edges: List[List],
    access_nodes: List[List],
    access_edges: List[List],
) -> Tuple[List[List], List[List], List[List], List[List]]:
    """
    Keep only the largest connected component of the graph.
    Returns filtered points, edges, access_nodes, access_edges.
    """
    G = nx.Graph()

    all_node_ids = set()
    for point in points:
        all_node_ids.add(point[0])
        G.add_node(point[0])

    for node in access_nodes:
        all_node_ids.add(node[0])
        G.add_node(node[0])

    for edge in edges:
        source, target = edge[2], edge[3]
        if source in all_node_ids and target in all_node_ids:
            G.add_edge(source, target)

    for edge in access_edges:
        source, target = edge[1], edge[2]
        if source in all_node_ids and target in all_node_ids:
            G.add_edge(source, target)

    components = list(nx.connected_components(G))

    if not components:
        logger.warning("No connected components found in graph")
        return [], [], [], []

    components.sort(key=len, reverse=True)
    largest_component = components[0]

    component_sizes = [len(c) for c in components[:10]]
    logger.info(
        "[FILTER] Connected components analysis: found %d components", len(components)
    )
    logger.info("[FILTER] Component sizes (first 10): %s", component_sizes)
    logger.info(
        "[FILTER] Keeping largest component: %d nodes (removed %d nodes from smaller components)",
        len(largest_component),
        len(all_node_ids) - len(largest_component),
    )

    filtered_points = [p for p in points if p[0] in largest_component]
    filtered_access_nodes = [n for n in access_nodes if n[0] in largest_component]

    filtered_edges = [
        e for e in edges if e[2] in largest_component and e[3] in largest_component
    ]
    filtered_access_edges = [
        e
        for e in access_edges
        if e[1] in largest_component and e[2] in largest_component
    ]

    return filtered_points, filtered_edges, filtered_access_nodes, filtered_access_edges
