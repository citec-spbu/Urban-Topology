import { useCallback, useState } from 'react';

export const useTownSection = () => {
  const [activeSection, setActiveSection] = useState<'map' | 'roads'>('map');

  const showMap = useCallback(() => setActiveSection('map'), []);
  const showRoads = useCallback(() => setActiveSection('roads'), []);

  return {
    isMapActive: activeSection === 'map',
    isRoadsActive: activeSection === 'roads',
    showMap,
    showRoads,
  };
};
