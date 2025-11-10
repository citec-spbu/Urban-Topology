import Toolbar from './components/Toolbar';

import { Route, Routes } from 'react-router-dom';
import { TownsPage } from './pages/TownsPage/TownsPage';
import { TownPage } from './pages/TownPage/TownPage';

const App = () => {
  return (
    <>
      <Toolbar />
      <Routes>
        <Route path="/" element={<TownsPage />} />
        <Route path="/towns" element={<TownsPage />} />
        <Route path="/towns/:id" element={<TownPage />} />
      </Routes>
    </>
  );
};

export default App;
