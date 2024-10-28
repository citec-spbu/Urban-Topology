import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, switchMap } from 'rxjs';

const xml2js = require("xml2js");

@Injectable({
  providedIn: 'root'
})
export class SearchService {
  constructor(
    private http: HttpClient
  ) { }

  getSearch(search: string): Observable<any>{
    return this.http.get(`https://www.openstreetmap.org/geocoder/search_osm_nominatim?query=${encodeURIComponent(search)}`)
  }

  getJsonFromOsm(fileUrl: string){
    return this.http
      .get(fileUrl, { responseType: "text" })
      .pipe(
        switchMap(async xml => await this.parseXmlToJson(xml))
      );
  }

  getRoadsOsm(bbox: {s: number, w: number, n: number, e: number}){
    // const formData: FormData = new FormData();
    // const blob = new Blob([osm_script(bbox)], { type: 'text/plain' });
    // formData.append('foo.xml', blob);

    return this.http.post('https://overpass-api.de/api/interpreter', osm_script(bbox),{ responseType: "json" });
  }

  async parseXmlToJson(xml: any) {
    return await xml2js.parseStringPromise(xml, { explicitArray: false })
    // .then((response: any) => response.Employees.Employee);
  }
}

const osm_script = (bbox: {s: number, w: number, n: number, e: number}) => `<osm-script output="json" timeout="25">
  <!-- gather results -->
  <union>
    <!-- query part for: “highway=* and highway!=footway and highway!=pedestrian and "-highway"!=path” -->
    <query type="way">
      <has-kv k="highway"/>
      <has-kv k="highway" modv="not" v="footway"/>
      <has-kv k="highway" modv="not" v="pedestrian"/>
      <has-kv k="-highway" modv="not" v="path"/>
      <bbox-query s="${bbox.s}" w="${bbox.w}" n="${bbox.n}" e="${bbox.e}"/>
    </query>
    <query type="relation">
      <has-kv k="highway"/>
      <has-kv k="highway" modv="not" v="footway"/>
      <has-kv k="highway" modv="not" v="pedestrian"/>
      <has-kv k="-highway" modv="not" v="path"/>
      <bbox-query s="${bbox.s}" w="${bbox.w}" n="${bbox.n}" e="${bbox.e}"/>
    </query>
  </union>
  <!-- print results -->
  <print mode="body"/>
  <recurse type="down"/>
  <print mode="skeleton" order="quadtile"/>
</osm-script>`
