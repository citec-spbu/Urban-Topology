import { TownPage } from '@/pages/TownPage';
import { TownsPage } from '@/pages/TownsPage';
import { Toolbar } from '@/shared/ui/Toolbar';
import { Route, Routes } from 'react-router-dom';

export const App = () => {
  return (
    <div className="font-montserrat">
      <Toolbar />
      <Routes>
        <Route path="/" element={<TownsPage />} />
        <Route path="/towns" element={<TownsPage />} />
        <Route path="/towns/:id" element={<TownPage />} />
      </Routes>
    </div>
  );
};
