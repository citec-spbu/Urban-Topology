import type { Region } from '@/shared/types';
import { useMemo, useState } from 'react';

export const useLevelOfDetail = (districtGroups: Region[][]) => {
  const [currentLevel, setCurrentLevel] = useState(0);

  const currentDistricts = useMemo(() => {
    return districtGroups[currentLevel] || [];
  }, [districtGroups, currentLevel]);

  const levelCount = districtGroups.length;

  const setLevel = (level: number) => {
    if (level >= 0 && level < levelCount) {
      setCurrentLevel(level);
    }
  };

  const nextLevel = () => {
    setCurrentLevel(prev => Math.min(prev + 1, levelCount - 1));
  };

  const prevLevel = () => {
    setCurrentLevel(prev => Math.max(prev - 1, 0));
  };

  return {
    currentLevel,
    currentDistricts,
    levelCount,
    setLevel,
    nextLevel,
    prevLevel,
  };
};
