//старая версия: city-list.component.ts
//избегаем утечек памяти + кэширование + не повторять одинаковые запросы
import { useQuery } from '@tanstack/react-query';
import { citiesApi } from '../services/citiesApi';
import { useEffect } from 'react';

const logError = (context: string, error: unknown) => {
  if (error instanceof Error) {
    console.error(`Ошибка при ${context}:`, {
      message: error.message,
      // Assuming error might have response property for axios errors
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
    staleTime: 5 * 60 * 1000, // заменять ли время обновления?
    gcTime: 10 * 60 * 1000, // через сколько удалять кэш? увеличиваем или уменьшаем?
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

export const useCityRegions = (cityId: number) => {
  const query = useQuery({
    queryKey: ['city', cityId, 'regions'],
    queryFn: () => citiesApi.getCityRegions(cityId),
    enabled: !!cityId,
    staleTime: 15 * 60 * 1000, // 15 минут
    gcTime: 60 * 60 * 1000, // 1 час
  });

  useEffect(() => {
    if (query.error) {
      logError('загрузке районов', query.error);
    }
  }, [query.error]);

  return query;
};