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

  onMapReady(map: L.Map){
    this.map = map;
    this.setTools(map);
    if(this.graphData) this.updateRoads(this.graphData);
  }

  updateRoads(gd: GraphData){
    if(!this.map) return;
    this.roads.clearLayers();

    let roads: { [key: string]: L.Polyline} = {};

    Object.values(gd.edges).forEach(edge => {
      if(edge.way_id)
      if(!roads[edge.way_id]) {
        if (edge.name) {
          var road_color = iwanthue(1, {seed: edge.name})[0]
        } else {
          var road_color = '#ebebeb'
        }
        roads[edge.way_id] = L.polyline([
          [gd.nodes[edge.from].lat, gd.nodes[edge.from].lon],
          [gd.nodes[edge.to].lat, gd.nodes[edge.to].lon], 
        ], {color: road_color, weight: 4}
        ).bindTooltip(edge.name || 'null').addTo(this.roads);
      } else {
        roads[edge.way_id].addLatLng([gd.nodes[edge.from].lat, gd.nodes[edge.from].lon]);
        roads[edge.way_id].addLatLng([gd.nodes[edge.to].lat, gd.nodes[edge.to].lon]);
      }
    })

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
