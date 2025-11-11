import type { City, Region } from "@/shared/types";
import { useQuery } from "@tanstack/react-query";
import { citiesApi } from "../api";

const groupRegionsByLevel = (regions: Region[]): Region[][] => {
  const grouped: { [key: number]: Region[] } = {};

  regions.forEach((region) => {
    if (!grouped[region.admin_level]) {
      grouped[region.admin_level] = [];
    }
    grouped[region.admin_level].push(region);
  });

  return Object.keys(grouped)
    .map(Number)
    .sort((a, b) => a - b)
    .map((level) => grouped[level]);
};

export const useTown = (townId: string) => {
  const id = Number(townId);

  const {
    data: town,
    isLoading: isTownLoading,
    error: townError,
  } = useQuery({
    queryKey: ["city", id],
    queryFn: () => citiesApi.getCity(id),
    enabled: !!townId,
    retry: 1,
  });

  const { data: regions, isLoading: isRegionsLoading } = useQuery({
    queryKey: ["city", id, "regions"],
    queryFn: () => citiesApi.getCityRegions(id),
    enabled: !!town,
  });

  const districtGroups = regions ? groupRegionsByLevel(regions) : [];

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
