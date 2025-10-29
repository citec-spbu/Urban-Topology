//типа town.service

import { api } from "./api";
import { City, Region, GraphData } from "../types";

export const citiesApi = {
  getCities: async (page: number, perPage: number) => {
    const { data } = await api.get<City[]>("/cities/", {
      params: { page, per_page: perPage },
    });
    return data;
  },

  getCity: async (id: number) => {
    const { data } = await api.get<City>("/city/", {
      params: { city_id: id },
    });
    return data;
  },

  getCityRegions: async (id: number) => {
    const { data } = await api.get<Region[]>("/regions/city/", {
      params: { city_id: id },
    });
    return data;
  },

  getGraphFromBbox: async (id: number, nodes: [number, number][]) => {
    const { data } = await api.post<GraphData>(`/city/graph/bbox/${id}`, [
      nodes,
    ]);
    return data;
  },

  getGraphFromRegionID: async (cityId: number, regionId: number) => {
    const { data } = await api.post<GraphData>(
      `/city/graph/region/?city_id=${cityId}`,
      [regionId]
    );
    return data;
  },
};
