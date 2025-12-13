import { api } from "@/shared/api";
import type { City, GraphData, Region } from "@/shared/types";

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

  getGraphFromRegionID: async (
    cityId: number,
    regionId: number,
    options?: { useCache?: boolean }
  ) => {
    const { data } = await api.post<GraphData>(
      `/city/graph/region/`,
      [regionId],
      {
        params: {
          city_id: cityId,
          use_cache: options?.useCache ?? false,
        },
      }
    );
    return data;
  },

  downloadGraphExport: async (
    cityId: number,
    regionIds: number[],
    options?: { useCache?: boolean }
  ) => {
    const response = await api.post(
      `/city/graph/region/export/`,
      regionIds,
      {
        params: {
          city_id: cityId,
          use_cache: options?.useCache ?? false,
        },
        responseType: 'blob',
      }
    );
    return response.data as Blob;
  },
};
