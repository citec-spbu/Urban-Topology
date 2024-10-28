# from street_name_parser import parse_name
from typing import Tuple
import osmium as o
import pandas as pd


required_ways_tags = ['way_id', 'name', 'maxspeed', 'highway', 'junction', 'lit', 'surface', 
                      'maxspeed:type', 'tunnel', 'bridge', 'oneway', 'living_street', 'lanes']
required_point_tags = ['node_id', 'name', 'traffic_signals', 'crossing', 'traffic_sign', 
                       'button_operated', 'traffic_calming', 'highway', 
                       'railway', 'public_transport', 'motorcar', 
                       'admin_level', 'population', 'population:date']

class HighwayWaysHandler(o.SimpleHandler):
    def __init__(self):
        super(HighwayWaysHandler, self).__init__()
        self.required_road_types = {'motorway', 'trunk', 'primary', 'secondary', 
                                    'tertiary', 'unclassified', 'residential', 'road', 
                                    'living_street', 'service', 'pedestrian'}
        self.used_nodes_ids = {}
        self.ways_tags = {}

    def way(self, w):
        if ('highway' in w.tags) and (w.tags.get('highway') in self.required_road_types):
            # if not 'name' in w.tags:
            #     self.ways_tags[w.id]['name'] = parse_name(w.nodes)
           
            graph = []
            for i in range(0, len(w.nodes) - 1):
                self.used_nodes_ids[int(w.nodes[i].ref)] = {'lat':w.nodes[i].lat, 'lon':w.nodes[i].lon}
                graph.append([int(w.nodes[i].ref), int(w.nodes[i+1].ref)])

            i = len(w.nodes) - 1
            self.used_nodes_ids[int(w.nodes[i].ref)] = {'lat':w.nodes[i].lat, 'lon':w.nodes[i].lon}
    
            self.ways_tags[w.id] = {tag.k : tag.v for tag in w.tags}
            self.ways_tags[w.id]['graph'] = graph
                     

class HighwayNodesHandler(o.SimpleHandler):
   
    def __init__(self, used_nodes_ids):
        super(HighwayNodesHandler, self).__init__()
        self.nodes_tags = used_nodes_ids

    def node(self, n):
        if n.id in self.nodes_tags.keys():  
            dct = {tag.k : tag.v for tag in n.tags}
            if len(dct) == 0:
                return
    
            for k, v in dct.items():
                self.nodes_tags[n.id][k] = v
            

def parse_osm(osm_file_path) -> Tuple[dict, dict]:
    ways = HighwayWaysHandler()
    try:
        ways.apply_file(osm_file_path, locations=False)
    except RuntimeError:
        pass

    nodes = HighwayNodesHandler(ways.used_nodes_ids)
    try:
        nodes.apply_file(osm_file_path, locations=True)
    except RuntimeError:
        pass

    return ways.ways_tags, nodes.nodes_tags


w, n = parse_osm('./Абакан.osm')

ways_df = pd.DataFrame(columns=required_ways_tags)

print(ways_df.head())




def to_csv(w, n):
    ids = []
    lat = []
    lon = []
    for point_id, coords in n.items():
        ids.append(point_id)
        lon.append(coords['lon'])
        lat.append(coords['lat'])

    d = {'node_id': ids, 'lat': lat, 'lon': lon}
    df = pd.DataFrame(data=d)
    df.to_csv('nodes.csv', index=False)

    from_id = []
    to_id = []
    name = []
    for id, info in w.items():
        for edge in info['graph']:
            from_id.append(edge[0])
            to_id.append(edge[1])
            if 'name' in info:
                name.append(info['name'])
            else:
                name.append('-')

    d = {'from': from_id, 'to': to_id, 'street_name': name}
    df = pd.DataFrame(data=d)
    df.to_csv('graph.csv', index=False)


# df_graph = pd.read_csv('./graph.csv')
# df_nodes = pd.read_csv('./nodes.csv')

# graph_ids = set(df_graph['from'])
# nodes_ids = set(df_nodes['node_id'])

# print(graph_ids.difference(nodes_ids))