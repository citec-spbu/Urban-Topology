import { Injectable } from '@angular/core';
import {HttpClient, HttpHeaders} from '@angular/common/http'
import { Region, Town } from '../interfaces/town';
import { Observable, of, throwError } from 'rxjs';
import { host } from 'src/environments/environment';


export interface csv_result{
  edges_csv: string,
  points_csv: string,
  points_properties_csv: string,
  metrics_csv: string,
  ways_properties_csv: string,
}

@Injectable({
  providedIn: 'root'
})
export class TownService {

  constructor(
    private http: HttpClient
  ) { }

  getHttpOptions(params?: any){
    let httpOptions = {
      headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
      params: params
    }

    return httpOptions;
  }

  getTowns(page: number = 1, per_page: number = 9): Observable<Town[]>{ //Observable - класс (из rxjs). Можно подписаться на изменение данных (.subscribe(func1, func2, func3)). (func1 - обработчик следующего значения, func2 - обработка ошибок, func3 - при завершении подачи данных) Нужен для ассинхронного изменения данных.
    
    return this.http.get<Town[]>(`${host}/cities/?page=${page}&per_page=${per_page}`, this.getHttpOptions());
    // return of(towns)
  }

  getTown(id: string): Observable<Town>{
    
    return this.http.get<Town>(`${host}/city/?city_id=${id}`, this.getHttpOptions());
  }

  // downloadTown(id: string, extension: number = 0): Observable<Town>{
    
  //   return this.http.get<Town>(`${host}/download/city/?city_id=${id}&extension=${extension}`, this.getHttpOptions());
  // }

  // deleteTown(id: string): Observable<Town>{
    
  //   return this.http.get<Town>(`${host}/delete/city/?city_id=${id}`, this.getHttpOptions());
  // }

  getTownRegions(id: number): Observable<Region[]>{
    
    return this.http.get<Region[]>(`${host}/regions/city/?city_id=${id}`, this.getHttpOptions());
  }

  getGraphFromBbox(id: number, nodes: [number, number][]){
    return this.http.post<csv_result>(`${host}/city/graph/bbox/${id}`, [nodes], this.getHttpOptions());
  }
  getGraphFromId(id: number, regionId: number){
    const body = [regionId];
    return this.http.post<csv_result>(`${host}/city/graph/region/?city_id=${id}`, body, this.getHttpOptions());
  }
}

// const towns: Town[] = [
//   {
//     id:'1',
//     name: 'Moscow',
//     file:'/assets/maps/msc.osm',
//     center: {
//       lat: 55.7504461,
//       lon: 37.6174943
//     },
//     districtFolder: 'moscow',
//     districts: {city: [], children: [], subchildren: []}
//   },{
//     id:'2',
//     name: 'Penza',
//     file:'/assets/maps/pnz.osm',
//     center: {
//       lat: 53.1890, 
//       lon: 45.0565
//     },
//     districts: {city: [], children: [], subchildren: []}
//   },{
//     id:'3',
//     name: 'Saint-Petersburg',
//     file:'/assets/maps/spb.osm',
//     center: {
//       lat: 59.9414, 
//       lon: 30.3267
//     },
//     districts: {city: [], children: [], subchildren: []}
//   }
// ]
