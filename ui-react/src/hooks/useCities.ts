//старая версия: city-list.component.ts
//избегаем утечек памяти + кэширование + не повторять одинаковые запросы
import { useQuery } from '@tanstack/react-query';
import { citiesApi } from '../services/citiesApi';

const logError = (context: string, error: any) => {
  console.error(`Ошибка при ${context}:`, {
    message: error.message,
    status: error?.response?.status,
    data: error?.response?.data,
  });
};

export const useCities = (page: number, perPage: number) => {
  return useQuery({
    queryKey: ['cities', page, perPage],
    queryFn: () => citiesApi.getCities(page, perPage),
    staleTime: 5 * 60 * 1000, // заменять ли время обновления?
    gcTime: 10 * 60 * 1000, // через сколько удалять кэш? увеличиваем или уменьшаем?
    onError: (error) => logError('загрузке списка городов', error),
  });
};


export const useCity = (id: number) => {
  return useQuery({
    queryKey: ['city', id],
    queryFn: () => citiesApi.getCity(id),
    enabled: typeof id === 'number' && id > 0,
    onError: (error) => logError('загрузке города', error),
  });
};

export const useCityRegions = (cityId: number) => {
  return useQuery({
    queryKey: ['city', cityId, 'regions'],
    queryFn: () => citiesApi.getCityRegions(cityId),
    enabled: !!cityId,
    staleTime: 15 * 60 * 1000, // 15 минут
    gcTime: 60 * 60 * 1000 // 1 час
    onError: (error) => logError('загрузке районов', error),
  });
};