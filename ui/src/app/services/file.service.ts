import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class FileService {

  constructor(
    private http: HttpClient
  ) { }

  readFile(fileUrl: string){
    return this.http.get(fileUrl, { responseType: "text" });
  }
  readJson(fileUrl: string){
    return this.http.get(fileUrl, { responseType: "json" });
  }
}
