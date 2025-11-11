import type { GraphData } from '@/shared/types';
import { useCallback, useState } from 'react';
import { useGraphFromBbox, useGraphFromRegion, type GraphLoadParams } from './useGraphLoader';

export const useGraphState = () => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [areaName, setAreaName] = useState<string>('');

  const hasGraph = graphData !== null;

  return {
    graphData,
    setGraphData,
    areaName,
    setAreaName,
    hasGraph,
  };
};

export const useGraphLoader = () => {
  const graphFromRegion = useGraphFromRegion();
  const graphFromBbox = useGraphFromBbox();

  const loadGraph = useCallback(async (params: GraphLoadParams) => {
    if (params.regionId) {
      return await graphFromRegion.mutateAsync({
        cityId: params.cityId,
        regionId: params.regionId,
      });
    } else if (params.polygon) {
      return await graphFromBbox.mutateAsync({
        cityId: params.cityId,
        nodes: params.polygon,
      });
    }
    throw new Error('Необходимо указать либо regionId, либо polygon');
  }, [graphFromRegion, graphFromBbox]);

  return {
    loadGraph,
    isLoading: graphFromRegion.isPending || graphFromBbox.isPending,
  };
};
