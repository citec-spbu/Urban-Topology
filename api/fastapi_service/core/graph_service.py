"""Сборка графа по выбранному региону и расчёт метрик центральности."""

from typing import List

import networkx as nx

from repositories import CityRepository, GraphRepository
from core.converters import (
    point_obj_to_list,
    edge_obj_to_list,
    record_obj_to_wprop,
    record_obj_to_pprop,
)

async def graph_from_poly(city_id, polygon):
    """Build graph (points, edges, properties, metrics) for polygon (Shapely polygon)."""
    repo_city = CityRepository()
    city = await repo_city.by_id(city_id)
    if city is None or not city.downloaded:
        return None, None, None, None

    polygon_wkt = polygon.wkt

    repo_graph = GraphRepository()

    # property ids
    prop_id_name = await repo_graph.property_id("name")
    prop_id_highway = await repo_graph.property_id("highway")

    # points in polygon (PostGIS)
    res_points = await repo_graph.points_in_polygon(city_id, polygon_wkt)
    points = list(map(point_obj_to_list, res_points))

    # edges filtered by polygon and highway types (PostGIS)
    road_types = (
        'motorway', 'trunk', 'primary', 'secondary', 'tertiary',
        'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'
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

    # Collect IDs for properties
    ways_prop_ids = {e[1] for e in edges}
    points_prop_ids = {p[0] for p in points}

    res = await repo_graph.way_props(ways_prop_ids)
    ways_prop = list(map(record_obj_to_wprop, res))

    res = repo_graph.point_props_via_temp(points_prop_ids)
    points_prop = list(map(record_obj_to_pprop, res))

    oneway_ids = await repo_graph.oneway_ids(city_id=city_id)
    metrics = await calc_metrics(points, edges, oneway_ids)

    return points, edges, points_prop, ways_prop, metrics


async def calc_metrics(points, edges, oneway_ids):
    # Empty graph -> return empty
    if not points:
        return []

    points_list = [point[0] for point in points]
    edges_list = [(edge[2], edge[3]) for edge in edges]
    reversed_edges_list = [(edge[3], edge[2]) for edge in edges if edge[1] not in oneway_ids]

    G = nx.DiGraph()
    G.add_nodes_from(points_list)
    G.add_edges_from(edges_list)
    G.add_edges_from(reversed_edges_list)

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
    for node_id in in_degree_dict:
        node_betweenness = betweenness_dict[node_id]
        normalized_betweenness = node_betweenness / adjusted_max_betweenness
        radius = get_radius_based_on_metric(normalized_betweenness)
        color = get_color_from_blue_to_red(node_betweenness, min_betweenness, max_betweenness)

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
