import { ChangeDetectorRef, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Region, Town, _distBounds } from '../interfaces/town';
import { FileService } from '../services/file.service';
import { csv_result, TownService } from '../services/town.service';
import { GraphDataService, GraphData, INode, Edge, Metric } from '../services/graph-data.service';
import { saveText } from '../graph/saveAsPNG';

import * as L from 'leaflet'; //* - все

enum sections {
  map = 'map',
  roads = 'roads'
}


@Component({
  selector: 'app-town',
  templateUrl: './town.component.html',
  styleUrls: ['./town.component.css', './loader.css']
})
export class TownComponent implements OnInit, OnDestroy {

  wayPropsCsv?: string;
  pointPropsCsv?: string;
  metrics?: string;

  id?: number;
  town?: Town;
  RgraphData?: GraphData;
  // currentCsv?: csv_result;

  graphName = '';
  // roadBounds?: L.LatLngBounds;
  loading: boolean = false;

  private _section: sections = sections.map;
  set section(val: sections | string) {
    this._section = val as sections;
    const achor = document.getElementsByName(val)[0];
    achor?.scrollIntoView({ behavior: 'smooth' });
  } get section() { return this._section }; // section=val вызывает set section(val), val=section вызывает get section

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
    this.route.paramMap.subscribe(params => {
      let id = params.get('id');
      if (id) {
        this.townSub?.unsubscribe();
        this.id = Number(id);
        this.townSub = this.townService.getTown(id).subscribe(
          town => {
            this.town = town;
            this.getDistricts(town);
          },
          error => { this.router.navigate(['/towns']) }
        )
      } else {
        this.router.navigate(['/towns']);
      }
    })
  }


  ngOnInit(): void { }
  ngOnDestroy(): void {
    this.townSub?.unsubscribe();
  }

  getCenter(): L.LatLngTuple {
    if (!this.town) return [59.9414, 30.3267];
    return [this.town.property.c_latitude, this.town.property.c_longitude];
  }

  getDistricts(town: Town): void {
    this.townService.getTownRegions(town.id).subscribe(res => {
      const levels: any = {};
      res.forEach(value => {
        if (!levels[value.admin_level]) levels[value.admin_level] = [];

        levels[value.admin_level].push(value);
      })
      town.districts = Object.keys(levels).map(key => levels[key]);
    })
  }

  handlePolygon(ev: { name: string, regionId?: number, polygon?: any }) {
    if (!this.id) return;
    this.graphName = ev.name;
    delete this.wayPropsCsv;
    delete this.pointPropsCsv;
    delete this.metrics;
    delete this.RgraphData;

    if (ev.regionId) {
      this.loading = true;
      this.cdRef.detectChanges();
      this.townService.getGraphFromId(this.id, ev.regionId).subscribe(this.graphSubscriber)
      return;
    }
    if (ev.polygon) {
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
    this.metrics = res.metrics_csv;

    this.getRgraph(res.points_csv, res.edges_csv, res.metrics_csv);
    this.loading = false;
    this.section = sections.roads;
    this.cdRef.detectChanges();
  }

  handleDownload(){
    if(this.pointPropsCsv)
      saveText('points_properties.csv', this.pointPropsCsv, 'text/csv');
    if(this.wayPropsCsv)
      saveText('ways_properties.csv', this.wayPropsCsv, 'text/csv');
    if(this.metrics)
      saveText('metrics_csv.csv', this.metrics, 'text/csv');
  }

  getRgraph(nodesStr: string, edgesStr: string, metricsStr: string): void {
    const parsedMetrics = this.parseCSV(metricsStr)
    const metrics = this.parseMetrics(parsedMetrics);
    const nodes = this.parseNodes(this.parseCSV(nodesStr), metrics);
    const edges = this.parseEdges(this.parseCSV(edgesStr));
    this.RgraphData = { nodes, edges } as GraphData;
  }

  private parseCSV = (csvStr: string, header: boolean = true): string[][] => {
    const lines = csvStr.split('\n');
    const data = header ? lines.slice(1) : lines;
  
    return data.map(line => {

      // Разбиваем строку на столбцы
      const columns = line.split(',').slice(0, 7);
  
      // Извлекаем 7-й столбец (цвет)
      let colorParts = line.split(',').slice(7).join(',');
  
      // Удаляем лишние кавычки вокруг цвета
      colorParts = colorParts.replace(/^"|"$/g, '').trim(); 
  
      // Создаем новый массив с цветом в последнем столбце
      const result = [...columns, colorParts];
  
      return result;
    }).filter(row => row[0]); // Фильтруем пустые строки
  };  

  private parseMetrics = (metricsData: string[][]): { [key: number]: Metric } => {
    const metrics: { [key: number]: Metric } = {};
    metricsData.forEach(([id, degree, in_degree, out_degree, eigenvector, betweenness, radius, color]) => {
      metrics[Number(id)] = {
        id: id,
        degree: degree,
        in_degree: in_degree,
        out_degree: out_degree,
        eigenvector: eigenvector,
        betweenness: betweenness,
        radius: radius,
        color: color
      };
    });
    return metrics;
  };

  private parseNodes = (nodesData: string[][], metrics: { [key: number]: Metric }): { [key: number]: INode } => {
    const nodes: { [key: number]: INode } = {};
    nodesData.forEach(([id, longitude, latitude]) => {
      const metric = metrics[Number(id)] || {};
      nodes[Number(id)] = {
        lat: Number(latitude),
        lon: Number(longitude),
        way_id: Number(id),
        degree_value: metric.degree,
        in_degree_value: metric.in_degree,
        out_degree_value: metric.out_degree,
        eigenvector_value: metric.eigenvector,
        betweenness_value: metric.betweenness,
        radius_value: metric.radius,
        color_value: metric.color
      };
    });
    return nodes;
  };

  private parseEdges = (edgesData: string[][]): { [key: number]: Edge } => {
    const edges: { [key: number]: Edge } = {};
    edgesData.forEach(([id, way_id, source, target, name]) => {
      edges[Number(id)] = {
        from: source,
        to: target,
        id: id,
        way_id: way_id,
        name: name,
      };
    });
    return edges;
  };
}
