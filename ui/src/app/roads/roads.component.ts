import { ChangeDetectorRef, Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { SearchService } from '../services/search.service';
import { GraphData } from '../services/graph-data.service';
import iwanthue from 'iwanthue';
import Pallete from 'iwanthue/palette';
import { saveText } from '../graph/saveAsPNG';
import * as L from 'leaflet';
import 'leaflet-easyprint';


@Component({
  selector: 'app-roads',
  templateUrl: './roads.component.html',
  styleUrls: ['./roads.component.css']
})
export class RoadsComponent implements OnInit {
  markerIcon = L.divIcon({className: 'roadPoint'});
  private _gd: GraphData | undefined;
  @Input() set graphData(val: GraphData | undefined){
    this._gd = val;
    if(val) this.updateRoads(val);
  }
  get graphData(){ return this._gd }

  @Input() loading: boolean = false;
  printControl: any;
  // gds?: L.GeoJSON;
  private _center: L.LatLngTuple = [46.879966, -121.726909];
  @Input() set center(val: L.LatLngTuple) {
    this._center = val;
    this.options = {
      layers: [
        new L.TileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; OpenStreetMap contributors', maxZoom: 18
        } as L.TileLayerOptions),
        this.roads,
        this.crossroads
      ] as L.Layer[],
      zoom: 10,
      center: val
    };
  }
  get center(): L.LatLngTuple { return this._center; }

  roads = new L.FeatureGroup([]);
  crossroads = new L.FeatureGroup([]);

  @Output() downloadRgraph = new EventEmitter();

  map?: L.Map;
  options: L.MapOptions = {
    layers: [
      new L.TileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors', maxZoom: 18
      } as L.TileLayerOptions),
      this.roads,
      this.crossroads
    ] as L.Layer[],
    center: this.center,//[55.754527, 37.619509],
    zoom: 9,
  };
  constructor(
  ) { }

  ngOnInit(): void {
  }

  onMapReady(map: L.Map){
    this.map = map;
    map.setZoom(10);
    map.setMaxBounds(map.getBounds());
    this.setTools(map);
    if(this.graphData) this.updateRoads(this.graphData);
  }

  updateRoads(gd: GraphData){
    if(!this.map) return;
    this.roads.clearLayers();
    this.crossroads.clearLayers(); // Очистка слоя перекрестков

    let roads: { [key: string]: L.Polyline } = {};
    let nodeWayConnections: { [key: string]: Set<string> } = {}; // Узлы и уникальные дороги

    // Отрисовка дорог и учет уникальных `way_id` для каждого узла
    Object.values(gd.edges).forEach(edge => {
      // Проверка существования way_id
      if (edge.way_id) {
        // Учет уникальных дорог для каждого узла
        if (!nodeWayConnections[edge.from]) nodeWayConnections[edge.from] = new Set();
        if (!nodeWayConnections[edge.to]) nodeWayConnections[edge.to] = new Set();
        nodeWayConnections[edge.from].add(edge.way_id); // Добавляем только если way_id существует
        nodeWayConnections[edge.to].add(edge.way_id);
      }

      // Отрисовка дорог
      if (edge.way_id) {
        if (!roads[edge.way_id]) {
          const road_color = edge.name
            ? iwanthue(1, { seed: edge.name })[0]
            : '#ebebeb';
          roads[edge.way_id] = L.polyline(
            [
              [gd.nodes[edge.from].lat, gd.nodes[edge.from].lon],
              [gd.nodes[edge.to].lat, gd.nodes[edge.to].lon]
            ],
            { color: road_color, weight: 4 }
          )
            .bindTooltip(`<b>Идентификатор</b>: ${edge.way_id} <br> 
                          <b>Название</b>: ${edge.name || 'Неизвестная дорога'}`)
            .addTo(this.roads);
        } else {
          roads[edge.way_id].addLatLng([gd.nodes[edge.from].lat, gd.nodes[edge.from].lon]);
          roads[edge.way_id].addLatLng([gd.nodes[edge.to].lat, gd.nodes[edge.to].lon]);
        }
      }
    });

    // Отрисовка перекрестков: Узлы с более чем одной уникальной дорогой
    Object.entries(nodeWayConnections).forEach(([nodeId, wayIds]) => {
      if (wayIds.size > 1) { // Если узел связан с двумя и более дорогами
        const node = gd.nodes[nodeId];
        if (node) {
          // Собираем названия дорог и их идентификаторы
          const roadNames: string[] = [];
          const roadIds: string[] = [];

          wayIds.forEach((wayId) => {
            const edge = Object.values(gd.edges).find(e => e.way_id === wayId);
            if (edge) {
              roadIds.push(wayId); // Добавляем идентификатор
              roadNames.push(edge.name || 'Неизвестная дорога'); // Добавляем имя дороги
            }
          });

          // Формируем popup с информацией о перекрестке
          const popupContent = `
        <b>Перекресток:</b><br>
        Идентификатор: ${nodeId}<br>
        Уникальных дорог: ${wayIds.size}<br>
        <b>Дороги:</b><br>
        ${roadNames.map((name, index) => `${name} (ID: ${roadIds[index]})`).join('<br>')}
      `;

          // Добавляем перекресток на карту
          L.circleMarker([node.lat, node.lon], {
            radius: 3,
            color: '#ff0000', // Красный цвет для перекрестков
            fillColor: '#ff0000',
            fillOpacity: 0.8
          })
            .bindPopup(popupContent)
            .addTo(this.crossroads);
        }
      }
    });

    this.map.fitBounds(this.roads.getBounds());
  }

  setTools(map: L.Map){
    const exportMap = ExportMap(() => {
      saveText(
        'export.svg',
        (document.getElementsByClassName('leaflet-overlay-pane')[1].lastChild as any).outerHTML,
        'image/svg+xml'
      )
    }, 'svg');
    new exportMap().addTo(map);

    const exportAsCsv = ExportMap(() => this.downloadRgraph.emit(), 'csv');
    new exportAsCsv().addTo(map);
  }

}

export const ExportMap = (mainFn: (ev: any) => void,type: 'svg'|'csv') => L.Control.extend({
  options: {
		position: 'topleft',
		clearText: `<span class="material-symbols-outlined" style="line-height: inherit;">save_alt</span>`,
		clearTitle: `Save as .${type}`,
	},
  onAdd(map: L.Map) {
		const polymodename = 'leaflet-control-export', container = L.DomUtil.create('div', `${polymodename} leaflet-bar`), options = this.options;
		this._clearButton = this._createButton(map, options.clearText, options.clearTitle, `${polymodename}`, container, mainFn);
		return container;
	},
  _clearButton: document.createElement('a'),
	_createButton(map: L.Map, html: string, title: string, className: string, container: HTMLElement, fn: (ev: any) => void) {
		const link = L.DomUtil.create('a', className, container);
		link.innerHTML = html;
		link.href = '#';
		link.title = title;
		link.setAttribute('role', 'button');
		link.setAttribute('aria-label', title);
		L.DomEvent.disableClickPropagation(link);
		L.DomEvent.on(link, 'click', L.DomEvent.stop);
		L.DomEvent.on(link, 'click', fn, this);
		L.DomEvent.on(link, 'click', ((ev: any) => {
      if(ev && ev.screenX > 0 && ev.screenY > 0){
        map.getContainer().focus();
      }
    }));
		return link;
	},
});
