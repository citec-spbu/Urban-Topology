import { Component, EventEmitter, Input, OnInit, Output} from '@angular/core';
import * as L from 'leaflet';
import { _district, _coordinates, Region } from '../interfaces/town';
import { GeoJsonObject } from 'geojson';

@Component({
  selector: 'app-map',
  templateUrl: './map.component.html',
  styleUrls: ['./map.component.css']
})
export class MapComponent implements OnInit {
  map?: L.Map;
  minZoom = 9;
  districtLevel = 0;

  clearTools?: any; // кнопка очистки карты 
  graphTools?: any; // кнопки выбора способа выбора полигонов
  distLOD?: any; //ползунок с изменением степени дробления районов

  markers = new L.LayerGroup<L.Marker>([]);
  districts = new L.LayerGroup<L.Polygon>([]);
  polyline =  new L.Polyline([], {color: '#830000', weight: 3});
  tools = new L.LayerGroup([]);

  onClickHandler?: (ev: any) => void; //переменная типа функция 
  markerIcon = L.divIcon({className: 'point'}); //встроенная функция L создающая шаблон иконки маркера со стилем point

  private _center: L.LatLngTuple = [ 46.879966, -121.726909];
  @Input() set center(val: L.LatLngTuple){
    this._center = val;
    this.options = {
      layers: [
          new L.TileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors', maxZoom: 18
          } as L.TileLayerOptions),
          this.markers, 
          this.districts, 
          this.polyline,
        ] as L.Layer[],
      zoom: this.minZoom,
      minZoom: this.minZoom,
      center: val
    };
  } 
  get center(): L.LatLngTuple{return this._center;}

  @Input() set regions(value: Region[][]){
    if(!value) return;
    this.cityFeatures = value;
    if(this.map) this.setTools(this.map, {levels: value.length})
    this.drawDistricts(this.districtLevel);
  }

  cityFeatures: Region[][] = [];


  manualPolygonsMode: boolean = false; //true - задаем районы в ручную false-смотрим на имеющиеся

  options: L.MapOptions = {
    layers: [
      new L.TileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors', maxZoom: 18
      } as L.TileLayerOptions),
    ] as L.Layer[], //скопировано с документации leaflet
    zoom: this.minZoom,
    minZoom: this.minZoom,
    center: this.center,
  };

  polygonOptions = {
    fillColor: 'red', 
    color: '#830000',
    fillOpacity: 0.1
  }

  @Output() graphInfo = new EventEmitter<{name: string, polygon?: any, regionId?: number}>();

  constructor() { }

  ngOnInit(): void {}

  onMapReady(map: L.Map) { //вызывается, когда карта готова
    this.map = map;
    map.setZoom(this.minZoom);
    map.setMaxBounds(map.getBounds()); //получаем текущие ограничения карты (2 координаты) при минимальном зуме и ограничиваем ими движение по карте
    this.setTools(map);
  }

  clearMap(){
    this.districts.clearLayers();
    this.markers.clearLayers();
    this.polyline.setLatLngs([]);
  }

  onManualPolygons(){ //ручной выбор полигонов
    this.manualPolygonsMode = true;
    this.clearMap();
    this.distLOD?.hide();

    const setPolyline = () => {
      this.districts.clearLayers(); //очищает слои в группе districs
      const latlngs = this.markers.getLayers().map(l => (l as L.Marker).getLatLng()); //массив координат всех маркеров
      this.polyline.setLatLngs(latlngs); //построение полилинии по маркерам
      this.polyline.redraw(); 
    }

    const setPolygon = () => {
      this.polyline.setLatLngs([]);
      const latlngs = this.markers.getLayers().map(l => (l as L.Marker).getLatLng());
      const polygon = this.districts.getLayers()[0] as L.Polygon;
      polygon.setLatLngs(latlngs);
      polygon.redraw();
    }
    
    this.onClickHandler = (ev: L.LeafletMouseEvent) => {
      const marker = L.marker(ev.latlng, {
        title: 'You can drag it\nDouble click to remove',
        icon: this.markerIcon,
        draggable: true, //перемещение маркера
        autoPan: true, //перемещение карты за меркером
      }).addTo(this.markers); // marker.addTo(markers) добавление маркера в markers

      //marker.on(событие, функция)- привязывает функцию к конкртному событию

      //создание полигона при нажатии на первый маркер
      marker.on('click', (ev: L.LeafletMouseEvent) => {
        const layers = this.markers.getLayers();
        if(layers.length < 3) return;
        if(this.markers.getLayerId(layers[0]) == this.markers.getLayerId(ev.target)){
          if(this.polyline.getLatLngs().length) this.addPolygon(layers.map(l => (l as L.Marker).getLatLng()));
          this.polyline.setLatLngs([]);
        }
      })
      //удаление маркера при двойном нажатии
      marker.on('dblclick', (ev) => { 
        this.markers.removeLayer(marker);
        const layers = this.markers.getLayers();
        if(layers.length>2 && this.polyline.getLatLngs().length==0){ 
          this.districts.clearLayers();
          this.addPolygon(layers.map(l => (l as L.Marker).getLatLng()));}
        else setPolyline();

      })
      // //при окончании перетаскивания маркера
      // marker.on('dragend', (ev) => {
      //   const markerPoint = marker.getLatLng();
      //   const mId=this.markers.getLayerId(marker)
      //   this.markers.eachLayer(l => {
      //     if(mId!=this.markers.getLayerId(l) && (l as L.Marker).getLatLng().equals(markerPoint)){
      //       this.markers.removeLayer(marker);
      //       this.polyline.setLatLngs([]);
      //       this.addPolygon(
      //         this.markers.getLayers().map(m => (m as L.Marker).getLatLng()), 'Your polygon'
      //       );
      //       return;
      //     }
      //   })
      // })

      //при перетаскивании маркера
      marker.on('drag', (ev) => {
        this.districts.getLayers().length ? setPolygon() : setPolyline();
      })

      setPolyline();
    }
  }

  //полигоны районов 
  onDistrictPolygons(){ 
    this.clearMap();
    this.manualPolygonsMode = false;
    if(!this.map) return;
    delete this.onClickHandler;
    this.distLOD?.show();

    this.drawDistricts(this.districtLevel);
  }

  drawDistricts(depth: number){

    this.districts.clearLayers();

    if(!this.cityFeatures || !this.cityFeatures[depth]) return;

    this.cityFeatures[depth].map(d => {
      this.drawGeoJson({
        type: "Feature",
        properties: {
          osm_id: d.id,
          local_name: d.name
        },
        geometry: {
          type: d.type || 'Polygon',
          coordinates: d.regions
        }
        
      } as GeoJsonObject, d.name)
    });
  }

  getPopup(name?: string){
    return (layer: L.Layer) => {
      const container = document.createElement('div'); //создание div
      container.innerHTML = `<h3>${name ? name : 'Your polygon'}</h3>`;
      const button = document.createElement('button'); //создание кнопки
      button.classList.add('polygonInfo'); //class в css
      button.innerText = 'Get info';
      button.onclick = (ev: MouseEvent) => name ? this.getRegionInfo(name, (layer as any).feature.properties.osm_id) : this.getPolygonInfo('Your polygon', layer); //переход от карты к графам
      container.appendChild(button);
      return container;
    }
  }

  bindEvents(layer: L.Polygon | L.GeoJSON){
    //предотвращает остальные события нажатия (нажатие на карту)
    layer.on('click', (ev: L.LeafletMouseEvent) => {
      L.DomEvent.stopPropagation(ev);
    });
    layer.on('mouseover', () => { //подсвечивание района при наведении
      layer.setStyle({
        fillOpacity: 0.3
      })
    });
    layer.on('mouseout', () => {
      layer.setStyle({
        fillOpacity: 0.1
      })
    });
  }

  drawGeoJson(geojson: GeoJsonObject, name: string){
    const gds = L.geoJSON(geojson).addTo(this.districts);
    gds.setStyle(this.polygonOptions);
    gds.bindPopup(this.getPopup(name)); //прикрепляет this.getPopup(name) при нажатии на полигон
    this.bindEvents(gds);//прикрепляет слушатель событий к слою
  }

  addPolygon(bounds: L.LatLng[], name?: string){
    const polygon = L.polygon(bounds , this.polygonOptions).addTo(this.districts);
    polygon.bindPopup(this.getPopup(name));
    this.bindEvents(polygon);
  }

  getRegionInfo(name:string, id: number){
    this.graphInfo.emit({name: name, regionId: id}); //выстреливает значение в handlePolygon в town.component
  }

  getPolygonInfo(name:string, polygon: any){
    this.graphInfo.emit({name: name, polygon: polygon}); //выстреливает значение в handlePolygon в town.component
  }

  setTools(map: L.Map, options?: {levels: number}){
    this.clearTools?.remove();
    this.graphTools?.remove();
    this.distLOD?.remove();

    const clearTools = ClearMap(() => {
      this.clearMap();
      this.graphTools?.enable();
      this.distLOD?.hide();
    })
    this.clearTools = new clearTools().addTo(map);

    const graphTools = PolygonMode(() => this.onManualPolygons(), () => this.onDistrictPolygons()) //класс (по конструктору класса)
    this.graphTools = new graphTools().addTo(map); //экземпляр класса

    
    if(options?.levels){
      const level = this.districtLevel;
      const distLOD = LODControl((ev: any) => {
        const value = ev.target.value ? Number(ev.target.value) : 0;
        this.districtLevel = value;
        this.drawDistricts(this.districtLevel);
      }, level, this.cityFeatures.length);
      this.distLOD = new distLOD().addTo(map);
    }
  }
}

//создание control кнопок для карты (возвращает конструктор нового класса). при добавлении его на карту будет вызвана onAdd(map: L.Map)
export const PolygonMode = (manualFn: (ev: any) => void, districtFn: (ev: any) => void) => L.Control.extend({
  options: {
		position: 'topleft',
		manualModeText: '<span class="material-symbols-outlined" aria-hidden="true" style="line-height: inherit;">polyline</span>', //вид кнопки
		manualModeTitle: 'Create polygon manually', //подсказочка(высвечивается при наведении)
		districtModeText: '<span class="material-symbols-outlined" aria-hidden="true" style="line-height: inherit;">auto_awesome_mosaic</span>',
		districtModeTitle: 'Select city district',
	},
  onAdd(map: L.Map) {
		const polymodename = 'leaflet-control-polygons', //название класса создаваемой кнопки
    container = L.DomUtil.create('div', `${polymodename} leaflet-bar`), //создает div кнопок внутри карт (встроенно в leaflet)
    options = this.options;
    
		this._manualButton = this._createButton(map, options.manualModeText, options.manualModeTitle, `${polymodename}-manual`, container, (ev: any) => {
        if(this._manualButton.getAttribute('disabled') == 'true') return;
        manualFn(ev);
        this._updateDisabled(this._manualButton);
    });
		this._districtButton = this._createButton(map, options.districtModeText, options.districtModeTitle, `${polymodename}-district`, container, (ev: any) => {
        if(this._districtButton.getAttribute('disabled') == 'true') return;
        districtFn(ev);
        this._updateDisabled(this._districtButton);
    });

		return container;
	},

  _manualButton: document.createElement('a'), //создание пустых мест, где будут кнопки
  _districtButton: document.createElement('a'),

	disable() {this._updateDisabled(this._districtButton, this._manualButton);}, //отключение control

	enable() {this._updateDisabled();}, //включение

	_createButton(map: L.Map, html: string, title: string, className: string, container: HTMLElement, fn: (ev: any) => void) {
		const link = L.DomUtil.create('a', className, container); //создает пустую ссылку
		link.innerHTML = html;
		link.href = '#'; //ссылка никуда не ведет
		link.title = title;
		link.setAttribute('role', 'button'); //превращает ссылку в кнопку
		link.setAttribute('aria-label', title);
		L.DomEvent.disableClickPropagation(link); //отключение других кликов (не срабатывает нажатие на карту при нажатии кнопки)
		L.DomEvent.on(link, 'click', L.DomEvent.stop);
		L.DomEvent.on(link, 'click', fn, this); //по клику сработает функция fn с контекстом this
		L.DomEvent.on(link, 'click', ((ev: any) => {
      if(ev && ev.screenX > 0 && ev.screenY > 0) map.getContainer().focus();
    }));
		return link;
	},

	_updateDisabled(...toDisable: HTMLAnchorElement[]) {
		const className = 'leaflet-disabled';
    //делаем обе кнопки включенными
		L.DomUtil.removeClass(this._manualButton, className); 
		L.DomUtil.removeClass(this._districtButton, className);
    this._manualButton.setAttribute('disabled', 'false');
    this._districtButton.setAttribute('disabled', 'false');
    //отключаем необходимые
    toDisable?.map(t => {
      t.setAttribute('disabled', 'true');
      L.DomUtil.addClass(t, className);
    })
  }
});

export const ClearMap = (mainFn: (ev: any) => void) => L.Control.extend({
  options: {
		position: 'topleft',
		clearText: '<span class="material-symbols-outlined" aria-hidden="true" style="line-height: inherit;">cleaning_services</span>',
		clearTitle: 'Remove all figures from the map',
	},
  onAdd(map: L.Map) {
		const polymodename = 'leaflet-control-clear', container = L.DomUtil.create('div', `${polymodename} leaflet-bar`), options = this.options;
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

export const LODControl = (mainFn: (ev: any) => void, level: number, levels: number) => L.Control.extend({
  options: {
		position: 'topleft',
		controlTitle: 'District size control',
	},
  onAdd(map: L.Map) {
		const polymodename = 'leaflet-control-districtLOD', container = L.DomUtil.create('div', `${polymodename} leaflet-bar`), options = this.options;
		this._lodRange = this._createRange(map, {id: 'district', type: 'range', min: '0', max: `${levels - 1}`, step: '1', value: `${level}`}, options.controlTitle,`${polymodename} mapSlider`, container, mainFn);
    this._container = container;
    this.hide();
		return container;
	},

  hide(){this._container.style.display = 'none';},
  show(){this._container.style.display = 'block';},

  _lodRange: document.createElement('input'),
  _container: document.createElement('div'),
	_createRange(map: L.Map, options: {
    id: string, type: string, min: string, max: string, step: string, value: string
  }, title: string, className: string, container: HTMLElement, fn: (ev: any) => void) {
		const input = L.DomUtil.create('input', className, container);
		input.title = title;
		setAttributes(input, options);
		input.setAttribute('aria-label', title);
    input.setAttribute('orient', 'vertcal');
		L.DomEvent.disableClickPropagation(input);

		L.DomEvent.on(input, 'click', L.DomEvent.stop);
		L.DomEvent.on(input, 'input', fn, this);
		return input;
	},
});

function setAttributes(el: HTMLElement, attrs: any) {
  for(var key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
}