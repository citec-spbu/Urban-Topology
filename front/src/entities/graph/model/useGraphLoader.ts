import { citiesApi } from '@/entities/city';
import { useMutation, useQueryClient } from '@tanstack/react-query';

const logGraphError = (context: string, error: any, params?: any) => {
  console.error(`Ошибка при ${context}:`, {
    message: error.message,
    status: error?.response?.status,
    data: error?.response?.data,
    params,
  });
};

export interface GraphLoadParams {
  cityId: number;
  regionId?: number;
  polygon?: [number, number][];
}

export const useGraphFromRegion = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ cityId, regionId }: { cityId: number; regionId: number }) =>
      citiesApi.getGraphFromRegionID(cityId, regionId),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        ['graph', variables.cityId, 'region', variables.regionId],
        data
      );
    },
    onError: (error, variables) => {
      logGraphError('загрузке графа по району', error, {
        cityId: variables.cityId,
        regionId: variables.regionId,
      });
    },
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 404) return false;
      return failureCount < 2;
    },
  });
};

export const useGraphFromBbox = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ cityId, nodes }: { cityId: number; nodes: [number, number][] }) =>
      citiesApi.getGraphFromBbox(cityId, nodes),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        ['graph', variables.cityId, 'bbox', JSON.stringify(variables.nodes)],
        data
      );
    },
    onError: (error, variables) => {
      logGraphError('загрузке графа по полигону', error, {
        cityId: variables.cityId,
        nodesCount: variables.nodes.length,
      });
    },
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 404) return false;
      if (error?.response?.status === 400) return false;
      return failureCount < 2;
    },
  });
};
