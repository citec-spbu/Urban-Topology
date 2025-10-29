// hooks/useTown.ts
import React from "react";
import { useQuery } from "@tanstack/react-query";
//import { useNavigate } from "react-router-dom";
import { citiesApi } from "../services/citiesApi";
import { City, Region } from "../types";

/**
 * Группировка районов по admin_level
 * Было в TownComponent.getDistrictsGroups()
 */
const groupRegionsByLevel = (regions: Region[]): Region[][] => {
  const grouped: { [key: number]: Region[] } = {};

  regions.forEach((region) => {
    if (!grouped[region.admin_level]) {
      grouped[region.admin_level] = [];
    }
    grouped[region.admin_level].push(region);
  });

  // Преобразовать объект в массив массивов, отсортированный по admin_level
  return Object.keys(grouped)
    .map(Number)
    .sort((a, b) => a - b)
    .map((level) => grouped[level]);
};

/**
 * Основной хук для работы с городом
 * Заменяет TownComponent + TownService
 */
export const useTown = (townId: string) => {
//   const navigate = useNavigate(); 
  const id = Number(townId);

  // Загрузка города
  const {
    data: town,
    isLoading: isTownLoading,
    error: townError,
  } = useQuery({
    queryKey: ["city", id],
    queryFn: () => citiesApi.getCity(id),
    enabled: !!townId,
    retry: 1,
    // onError: (error: any) => {
    //   if (error?.response?.status === 404) navigate("/towns");
    // },
  });

  // Загрузка районов города
  const { data: regions, isLoading: isRegionsLoading } = useQuery({
    queryKey: ["city", id, "regions"],
    queryFn: () => citiesApi.getCityRegions(id),
    enabled: !!town, // Загружать только если город загружен
  });

  // Группировка районов по уровням
  const districtGroups = regions ? groupRegionsByLevel(regions) : [];

  // Добавить districts в объект города
  const cityWithDistricts: City | undefined = town
    ? {
        ...town,
        districts: districtGroups,
      }
    : undefined;

  return {
    town: cityWithDistricts,
    regions,
    districtGroups,
    isLoading: isTownLoading || isRegionsLoading,
    error: townError,
  };
};

//Хук для переключения секций (map/roads) было в TownComponent.section?

export const useTownSection = () => {
  const [section, setSection] = React.useState<"map" | "roads">("map");

  const showMap = () => setSection("map");
  const showRoads = () => setSection("roads");
  const toggleSection = () =>
    setSection((prev) => (prev === "map" ? "roads" : "map"));

  return {
    section,
    isMapActive: section === "map",
    isRoadsActive: section === "roads",
    showMap,
    showRoads,
    toggleSection,
  };
};
