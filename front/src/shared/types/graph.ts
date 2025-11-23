export interface Edge {
  from: string,
  to: string,
  name?: string,
  way_id?: string,
  id?: string
}

export interface INode {
  lat: number,
  lon: number,
  way_id: number | string,
  name?: string,
  degree_value?: string,
  in_degree_value?: string,
  out_degree_value?: string,
  eigenvector_value?: string,
  betweenness_value?: string,
  radius_value?: string,
  color_value?: string
}

export interface GraphData {
  nodes?: {
    [key: string]: INode
  },
  edges?: {
    [key: string]: Edge
  },
  edges_csv?: string,
  points_csv?: string,
  nodes_csv?: string,
  access_nodes_csv?: string,
  access_edges_csv?: string,
  graph_name?: string
}
