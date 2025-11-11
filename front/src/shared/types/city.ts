import type { Region } from "./region";

export interface City {
  id: number;
  city_name: string;
  property: {
    population: number;
    population_density: number;
    c_longitude: number;
    c_latitude: number;
    time_zone: string;
    time_created: string;
  };
  downloaded: boolean;
  districts: Region[][];
}
