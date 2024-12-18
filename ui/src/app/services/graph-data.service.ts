import { Injectable } from '@angular/core';
import Graph from "graphology";


export interface Edge{
  from: string,
  to: string,
  name?: string,
  way_id?: string,
  id?: string
}

export interface INode{
    lat: number,
    lon: number,
    way_id: number,
    name?: string,
    degree_value?: string,
    in_degree_value?: string,
    out_degree_value?: string,
    eigenvector_value?: string,
    betweenness_value?: string,
    radius_value?: string,
    color_value?: string
}

export interface GraphData{
  nodes: {
    [key: string]: INode
  },
  edges: {
    [key: string]: Edge
  }
}

export interface Metric{
    id: string,
    degree: string,
    in_degree: string,
    out_degree: string,
    eigenvector: string,
    betweenness: string,
    radius: string,
    color: string
  }

@Injectable({providedIn: 'root'})
export class GraphDataService {
    // graph: Graph = new Graph();
    constructor() {}

    getNodesFromCsv(graph: Graph, csvString: string, params?: any){
        const lines = csvString.split('\n');
        lines.slice(1).forEach(line => { 
            const [id, lat, lon] = line.split(',');
            graph.addNode(id, {x: Number(lat), y: Number(lon), ...params});
        })
    }

    getEdgesFromCsv(graph: Graph, csvString: string, params?: any){
        const lines = csvString.split('\n');
        lines.slice(1).forEach(line => { 
            const [src, target, label] = line.split(',');
            graph.addEdge(src, target, {type: 'line', label: label, ...params});
        })
    }

    csv2object<T>(csvString: string, keys: string[]): T[]{
        const lines = csvString.split('\n');
        let result: T[] = [];

        lines.slice(1).forEach(line => {
            const values = line.split(',');
            let tmp: {[K in keyof T]: string } = {} as any;
            keys.forEach((key: string, index: number) =>  (tmp as any)[key] = values[index]);
            result.push(tmp as any);
        })

        return result;
    }

    streetsToIntersections(gd: GraphData): GraphData{
        // TODO
        return gd;
    }
}