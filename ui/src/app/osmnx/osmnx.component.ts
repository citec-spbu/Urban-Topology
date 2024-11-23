import { ChangeDetectorRef, Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { SearchService } from '../services/search.service';
import { GraphData, OSMNXGraphData } from '../services/graph-data.service';
import iwanthue from 'iwanthue';
import Pallete from 'iwanthue/palette';
import { saveText } from '../graph/saveAsPNG';
import * as L from 'leaflet';
import { GeoJsonObject } from 'geojson';
import 'leaflet-easyprint';


@Component({
  selector: 'app-osmnx',
  templateUrl: './osmnx.component.html',
  styleUrls: ['./osmnx.component.css']
})
export class OsmnxComponent implements OnInit {
  markerIcon = L.divIcon({ className: 'roadPoint' });

  private _osmnx_gd: OSMNXGraphData | undefined;

  @Input() set OSMNXGraphData(val: OSMNXGraphData | undefined) {
    this._osmnx_gd = val;
    if (val) this.updateOSMNXGraph(val);
  }
  get OSMNXGraphData() { return this._osmnx_gd }

  @Input() loading: boolean = false;
  printControl: any;

  roads = new L.FeatureGroup([]);


  @Output() downloadRgraph = new EventEmitter();

  map?: L.Map;
  options: L.MapOptions = {
    layers: [
      this.roads
    ] as L.Layer[],
    center: [55.754527, 37.619509],
    zoom: 10,
  };
  constructor(
  ) { }

  ngOnInit(): void {
  }

  onMapReady(map: L.Map) {
    this.map = map;
    this.setTools(map);
    if (this.OSMNXGraphData) this.updateOSMNXGraph(this.OSMNXGraphData);
  }

  updateOSMNXGraph(osmnx_gd: OSMNXGraphData) {
    if (!this.map) return;
    this.roads.clearLayers(); // Очищаем текущие слои

    // Парсим данные узлов и рёбер
    const nodesGeoJSON = JSON.parse(osmnx_gd.nodes);
    const edgesGeoJSON = JSON.parse(osmnx_gd.edges);

    // Добавляем узлы
    const nodesLayer = L.geoJSON(nodesGeoJSON, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 4, // Радиус маркера
          fillColor: '#ff7800', // Цвет заливки
          color: '#000', // Цвет границы
          weight: 1, // Толщина границы
          opacity: 1, // Прозрачность границы
          fillOpacity: 0.8 // Прозрачность заливки
        }).bindTooltip(`${feature.properties?.id || 'Unknown ID'}`);
      }
    }).addTo(this.roads);

    // Добавляем рёбра
    const edgesLayer = L.geoJSON(edgesGeoJSON, {
      style: (feature) => ({
        color: '#3388ff', // Цвет линии
        weight: 3, // Толщина линии
        opacity: 0.8 // Прозрачность линии
      }),
      onEachFeature: (feature, layer) => {
        const edgeName = feature.properties?.name ? String(feature.properties.name) : 'Unnamed Edge';
        layer.bindTooltip(edgeName);
      }
    }).addTo(this.roads);

    // Устанавливаем границы карты, чтобы включить все элементы
    this.map.fitBounds(this.roads.getBounds());
  }
  setTools(map: L.Map) {
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

export const ExportMap = (mainFn: (ev: any) => void, type: 'svg' | 'csv') => L.Control.extend({
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
      if (ev && ev.screenX > 0 && ev.screenY > 0) {
        map.getContainer().focus();
      }
    }));
    return link;
  },
});
