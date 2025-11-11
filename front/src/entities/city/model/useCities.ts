import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { citiesApi } from '../api';

const logError = (context: string, error: unknown) => {
  if (error instanceof Error) {
    console.error(`Ошибка при ${context}:`, {
      message: error.message,
      status: (error as any)?.response?.status,
      data: (error as any)?.response?.data,
    });
  } else {
    console.error(`Произошла неизвестная ошибка при ${context}:`, error);
  }
};

export const useCities = (page: number, perPage: number) => {
  const query = useQuery({
    queryKey: ['cities', page, perPage],
    queryFn: () => citiesApi.getCities(page, perPage),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    if (query.error) {
      logError('загрузке списка городов', query.error);
    }
  }, [query.error]);

  return query;
};

export const useCity = (id: number) => {
  const query = useQuery({
    queryKey: ['city', id],
    queryFn: () => citiesApi.getCity(id),
    enabled: typeof id === 'number' && id > 0,
  });

  useEffect(() => {
    if (query.error) {
      logError('загрузке города', query.error);
    }
  }, [query.error]);

  return query;
};
