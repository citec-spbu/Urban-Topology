import {ChangeDetectorRef, Component, ElementRef, OnDestroy, OnInit, ViewChild} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Region, Town, _distBounds } from '../interfaces/town';
import { FileService } from '../services/file.service';
import { csv_result, TownService } from '../services/town.service';
import { GraphDataService, GraphData, INode, Edge } from '../services/graph-data.service';
import { saveText } from '../graph/saveAsPNG';  

import * as L from 'leaflet'; //* - все

enum sections{
  map = 'map',
  graph = 'graph',
  roads = 'roads'
}


@Component({
  selector: 'app-town',
  templateUrl: './town.component.html',
  styleUrls: ['./town.component.css', './loader.css']
})
export class TownComponent implements OnInit, OnDestroy{

  wayPropsCsv?: string;
  pointPropsCsv?: string;
  rNodes?: string;
  rEdges?: string;

  id?: number;
  town?: Town;
  RgraphData?: GraphData;
  LgraphData?: GraphData;

  // currentCsv?: csv_result;

  graphName = '';
  // roadBounds?: L.LatLngBounds;
  loading: boolean = false;

  private _section: sections = sections.map;
  set section(val: sections | string){
    this._section = val as sections;
    const achor = document.getElementsByName(val)[0];
    achor?.scrollIntoView({behavior: 'smooth'});
  } get section(){return this._section}; // section=val вызывает set section(val), val=section вызывает get section

  townSub?: any;

  constructor(
    private townService: TownService,
    private route: ActivatedRoute,
    private router: Router,
    private fileService: FileService,
    private cdRef: ChangeDetectorRef,
    private graphDataService: GraphDataService
  ) { 
    this.section = sections.map;
    this.route.paramMap.subscribe(params=>{
      let id = params.get('id');
      if(id){
        this.townSub?.unsubscribe();
        this.id= Number(id);
        this.townSub = this.townService.getTown( id ).subscribe(
          town=>{
            this.town = town;
            this.getDistricts(town);
          },
          error=>{this.router.navigate(['/towns'])}
        )
      } else {
        this.router.navigate(['/towns']);
      }
    })
  }

  
  ngOnInit(): void {}
  ngOnDestroy(): void {
    this.townSub?.unsubscribe();
  }

  getCenter(): L.LatLngTuple{
    if(!this.town) return [59.9414, 30.3267];
    return [ this.town.property.c_latitude, this.town.property.c_longitude ];
  }

  getDistricts(town: Town): void{
    this.townService.getTownRegions(town.id).subscribe(res => {
      const levels: any = {};
      res.forEach(value => {
        if( !levels[value.admin_level] ) levels[value.admin_level] = [];

        levels[value.admin_level].push(value);
      })
      town.districts = Object.keys(levels).map(key => levels[key]);
    })
  }

  handlePolygon(ev: {name: string, regionId?: number, polygon?: any}){
    if(!this.id) return;
    this.graphName = ev.name;
    delete this.wayPropsCsv;
    delete this.pointPropsCsv;
    delete this.rNodes;
    delete this.rEdges;
    delete this.LgraphData;
    delete this.RgraphData;

    if(ev.regionId){
      this.loading = true;
      this.cdRef.detectChanges();
      this.townService.getGraphFromId(this.id, ev.regionId).subscribe(this.graphSubscriber)
      return;
    }
    if(ev.polygon){
      const nodes = ev.polygon.getLatLngs()[0] as L.LatLng[];
      const body: [number, number][] = nodes.map(node => [node.lng, node.lat]);
      this.loading = true;
      this.cdRef.detectChanges();
      this.townService.getGraphFromBbox(this.id, body).subscribe(this.graphSubscriber);
      return;
    }
  }
  
  graphSubscriber = (res: csv_result) => {
    this.pointPropsCsv = res.points_properties_csv;
    this.wayPropsCsv = res.ways_properties_csv;
    this.rNodes = res.reversed_nodes_csv;
    this.rEdges = res.reversed_edges_csv;

    this.getRgraph(res.points_csv, res.edges_csv);
    this.getLgraph(res.reversed_nodes_csv, res.reversed_edges_csv);
    this.loading = false;
    this.section = sections.graph;
    this.cdRef.detectChanges();
  }

  handleDownload(type: 'r' | 'l'){
    let nodes_text = '';
    let edges_text = '';
    if(type == 'l'){
      if(!this.LgraphData) return;
      nodes_text = 'id_way,name\n' + Object.values(this.LgraphData.nodes).map((node, index) => `${node.way_id},"${node.name}"`).join('\n');
      edges_text = 'source_way,target_way\n' + Object.values(this.LgraphData.edges).map(edge => `${edge.from},${edge.to},${edge.id}`).join('\n');
      saveText('points.csv', nodes_text, 'text/csv');
      saveText('edges.csv', edges_text, 'text/csv');
    } else {
      if(this.rNodes)
        saveText('reversed_nodes.csv', this.rNodes, 'text/csv');
      if(this.rEdges)
        saveText('reversed_edges.csv', this.rEdges, 'text/csv');
      if(this.pointPropsCsv) 
        saveText('points_properties.csv', this.pointPropsCsv, 'text/csv');
      if(this.wayPropsCsv) 
        saveText('ways_properties.csv', this.wayPropsCsv, 'text/csv');
    }
  }

  getRgraph(nodes_str: string, edges_str: string){
    const nodes: { [key: string]: INode } = {};
    const edges: { [key: string]: Edge } = {};

    const node_lines = nodes_str.split('\n')
    node_lines.slice(1).forEach((line, index) => {
      const [id, longitude, latitude] = line.split(',');
      if(id){
        nodes[Number(id)] = {
          lat: Number(latitude),
          lon: Number(longitude),
          way_id: Number(id)
        }
      }
    })

    const edge_lines = edges_str.split('\n')
    edge_lines.slice(1).forEach((line, index) => {
      const [id,id_way,source,target,name] = line.split(',');
      if(id){
        edges[Number(id)] = {
          from: source,
          to: target,
          id: id,
          way_id: id_way,
          name: name
        }
      }
    })

    this.RgraphData = {
      nodes: nodes,
      edges: edges,
    }
    // console.log(this.RgraphData)
  }
  
  getLgraph(nodes_str: string, edges_str: string){
    const nodes: { [key: string]: INode } = {};
    const edges: { [key: string]: Edge } = {};

    // const names = this.RgraphData ? Object.values(this.RgraphData.edges).map(edge => ({id: edge.way_id, name: edge.name}) ) : [];

    const node_lines = nodes_str.split('\n')
    node_lines.slice(1).forEach((line, index) => {
      const [id_way, name, street_ways] = line.split(',');
      // const id_way = line.split(',"')[0];

      // const name = names.find(n => n.id == id_way)?.name;

      if(id_way && name){
        nodes[Number(id_way)] = {
          lat: 0,
          lon: 0,
          way_id: Number(id_way),
          name: name
        }
      }
    })

    const edge_lines = edges_str.split('\n')
    edge_lines.slice(1).forEach((line, index) => {
      const [source_way,target_way] = line.split(',');
      if(source_way && nodes[Number(source_way)] && nodes[Number(target_way)]){
        edges[index] = {
          from: source_way,
          to: target_way,
          id: index.toString(),
        }
      }
    })

    this.LgraphData = {
      nodes: nodes,
      edges: edges,
    }
  }
}
