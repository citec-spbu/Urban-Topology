import matplotlib.pyplot
import osmnx as ox
import shapely

import numpy as np
import networkx as nx

def check_validity(place_name):
    try:
        tags = {"building": True}
        g = ox.features_from_place(place_name, tags)
        return True, g
    except Exception as e:
        return False, str(e)


city = input("Введите название города: ")
plot_type = 3
is_valid, gdf = check_validity(city)
if is_valid:
    gdf = gdf[['geometry']]
    coordinates = gdf['geometry'].values.tolist()
    for i in range(len(coordinates)):
        coordinates[i] = shapely.centroid(coordinates[i])
        coordinates[i] = [coordinates[i].x, coordinates[i].y]
    coordinates = np.asarray(coordinates)

    def create_graph_from_coordinates(coordinates, maxdistance=0.001):
        G = nx.Graph()

        for i in range(len(coordinates)):
            G.add_node(i, pos=coordinates[i])

        for i in range(len(coordinates)):
            for j in range(i + 1, len(coordinates)):
                dist = np.linalg.norm(coordinates[i] - coordinates[j])
                if dist <= maxdistance:
                    G.add_edge(i, j, weight=dist)

        return G


    threshold = 0.002
    G = create_graph_from_coordinates(coordinates, threshold)

    if (plot_type == 1):
        degree_centrality = nx.degree_centrality(G)
        dlist = degree_centrality.values()
        gdf['degree'] = dlist
        norm = matplotlib.colors.Normalize(vmin=min(gdf['degree']), vmax=max(gdf['degree']))
        cmap = matplotlib.cm.inferno
        fig, ax = matplotlib.pyplot.subplots()
        for _, row in gdf.iterrows():
            color = cmap(norm(row['degree']))
            ax.fill(*row['geometry'].exterior.xy, color=color)
        matplotlib.pyplot.show()
    if (plot_type == 2):
        betweenness_centrality = nx.betweenness_centrality(G)
        blist = betweenness_centrality.values()
        gdf['betweenness'] = blist
        norm = matplotlib.colors.Normalize(vmin=min(gdf['betweenness']), vmax=max(gdf['betweenness']))
        cmap = matplotlib.cm.inferno
        fig, ax = matplotlib.pyplot.subplots()
        for _, row in gdf.iterrows():
            color = cmap(norm(row['betweenness']))
            ax.fill(*row['geometry'].exterior.xy, color=color)
        matplotlib.pyplot.show()
    if (plot_type == 3):
        closeness_centrality = nx.closeness_centrality(G)
        clist = closeness_centrality.values()
        gdf['closeness'] = clist
        norm = matplotlib.colors.Normalize(vmin=min(gdf['closeness']), vmax=max(gdf['closeness']))
        cmap = matplotlib.cm.inferno
        fig, ax = matplotlib.pyplot.subplots()
        for _, row in gdf.iterrows():
            color = cmap(norm(row['closeness']))
            ax.fill(*row['geometry'].exterior.xy, color=color)
        matplotlib.pyplot.show()
else:
    print(f"Invalid place name: {gdf}")
