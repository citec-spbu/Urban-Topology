import networkx as nx
import matplotlib.pyplot
import numpy as np
from sklearn.neighbors import NearestNeighbors
import osmnx as ox
import shapely

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
        coordinates[i] = (coordinates[i].x, coordinates[i].y)
    k = 5
    nbrs = NearestNeighbors(n_neighbors=k + 1, algorithm='auto').fit(coordinates)
    distances, indices = nbrs.kneighbors(coordinates)
    G = nx.Graph()
    for coord in coordinates:
        G.add_node(coord)

    for i, coord in enumerate(coordinates):
        for j in indices[i][1:]:
            neighbor = coordinates[j]
            G.add_edge(coord, neighbor)

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