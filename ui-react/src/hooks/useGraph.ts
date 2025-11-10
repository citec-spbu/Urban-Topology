// hooks/useGraph.ts
import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { citiesApi } from '../services/citiesApi';
import type { GraphData } from '../types/graph';

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

// хук для загрузки графа по району
export const useGraphFromRegion = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ cityId, regionId }: { cityId: number; regionId: number }) =>
      citiesApi.getGraphFromRegionID(cityId, regionId),
    onSuccess: (data, variables) => {
      // Кешировать результат
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
      // Не повторять при 404 (район не найден)
      if (error?.response?.status === 404) return false;
      // Максимум 2 попытки
      return failureCount < 2;
    },
  });
};

//хук для загрузки графа по полигону (bbox)
export const useGraphFromBbox = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ cityId, nodes }: { cityId: number; nodes: [number, number][] }) =>
      citiesApi.getGraphFromBbox(cityId, nodes),
    onSuccess: (data, variables) => {
      // кешировать результат
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

    //повторные попытки
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 404) return false;
      if (error?.response?.status === 400) return false; // Невалидный полигон
      return failureCount < 2;
    },
  });
};

//универсальный (заменяет TownComponent.onLoadGraph())

export const useGraphLoader = () => {
  const loadFromRegion = useGraphFromRegion();
  const loadFromBbox = useGraphFromBbox();

  const loadGraph = async (params: GraphLoadParams) => {
    if (params.regionId) {
      // Загрузка по району
      return loadFromRegion.mutateAsync({
        cityId: params.cityId,
        regionId: params.regionId,
      });
    } else if (params.polygon && params.polygon.length >= 3) {
      // Загрузка по полигону
      return loadFromBbox.mutateAsync({
        cityId: params.cityId,
        nodes: params.polygon,
      });
    } else {
      throw new Error('Необходимо указать regionId или polygon');
    }
  };

  return {
    loadGraph,
    isLoading: loadFromRegion.isPending || loadFromBbox.isPending,
    error: loadFromRegion.error || loadFromBbox.error,
    data: loadFromRegion.data || loadFromBbox.data,
  };
};

//для управления состоянием графа (Заменяет TownComponent.RgraphData)
export const useGraphState = () => {
  const [graphData, setGraphData] = React.useState<GraphData | null>(null);
  const [areaName, setAreaName] = React.useState<string>('');

  const clearGraph = () => {
    setGraphData(null);
    setAreaName('');
  };

  return {
    graphData,
    areaName,
    setGraphData,
    setAreaName,
    clearGraph,
    hasGraph: !!graphData,
  };
};