from typing import Tuple
import osmium as o
import traceback


required_ways_tags = {'highway', 'junction', 'lit', 'surface', 
                      'maxspeed:type', 'tunnel', 'bridge', 'oneway', 
                      'living_street', 'lanes', 'maxspeed', 'name'}
required_point_tags = {'population', 'traffic_signals', 'crossing', 
                       'button_operated', 'traffic_calming', 'highway', 
                       'traffic_sign', 'admin_level', 'railway', 'population:date', 
                       'name', 'public_transport', 'motorcar'}

class HighwayWaysHandler(o.SimpleHandler):
    def __init__(self):
        super(HighwayWaysHandler, self).__init__()
        self.required_road_types = {'motorway', 'trunk', 'primary', 'secondary', 
                                    'tertiary', 'unclassified', 'residential', 'road', 
                                    'living_street'} # , 'service', 'pedestrian'
        self.used_nodes_ids = {}
        self.ways_tags = {}

    def way(self, w):
        if ('highway' in w.tags) and (w.tags.get('highway') in self.required_road_types):
            self.ways_tags[w.id] = {tag.k : tag.v for tag in w.tags}
            # if not 'name' in w.tags:
            #     self.ways_tags[w.id]['name'] = parse_name(w.nodes)
           
            graph = []
            for i in range(0, len(w.nodes) - 1):
                graph.append([int(w.nodes[i].ref), int(w.nodes[i+1].ref)])
                self.used_nodes_ids[int(w.nodes[i].ref)] = {'lat':w.nodes[i].lat, 'lon':w.nodes[i].lon}

            i = len(w.nodes) - 1
            self.used_nodes_ids[int(w.nodes[i].ref)] = {'lat':w.nodes[i].lat, 'lon':w.nodes[i].lon}
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
        nodes.apply_file(osm_file_path, locations=False)
    except RuntimeError:
        pass

    return ways.ways_tags, nodes.nodes_tags