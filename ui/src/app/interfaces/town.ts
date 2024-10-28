export interface townBounds{
    maxlat: string,
    maxlon: string, 
    minlat: string,
    minlon: string
}

// export enum districtLevels{
//   city = 4,
//   children = 5,
//   subchildren = 8,
// }

export interface _center{
  lat: number,
  lon: number
}

export type _coordinates = L.LatLngTuple[][] | L.LatLngTuple[]

export interface _district{
    type: string,
    properties: {
      osm_id: number,
      local_name: string,
    },
    geometry: {
      type: string,
      coordinates: _coordinates[],
    }
}
  
  export interface _distBounds{
    type: string,
    crs: {
      type: string,
      properties: {
        name: string
      }
    },
    features: _district[]
  }

export interface Region{
  id: number,
  admin_level: number,
  name: string,
  type: 'Polygon'
  regions: _coordinates
}


export interface Town{
  id : number,
  city_name: string,
  property: {
    population: number,
    population_density: number,
    c_longitude: number,
    c_latitude: number,
    time_zone: string,
    time_created: string
  },
  downloaded: boolean,
  districts: Region[][]
}