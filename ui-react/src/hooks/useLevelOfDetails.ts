//TownComponent.districtsLOD -> useLevelOfDetail -- управление уровнями детализации районов
import { useState, useMemo } from 'react';
import { Region } from '../types';


export const useLevelOfDetail = (districtGroups: Region[][]) => {
  const [currentLevel, setCurrentLevel] = useState(0);

  // Текущие районы выбранного уровня
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
    hasNextLevel: currentLevel < levelCount - 1,
    hasPrevLevel: currentLevel > 0,
  };
};