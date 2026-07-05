import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { MainLayout } from '@/layouts/MainLayout';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { useAppStore } from '@/store/useAppStore';

import Home from '@/pages/Home';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import Dashboard from '@/pages/Dashboard';
import CropRecommendation from '@/pages/CropRecommendation';
import Irrigation from '@/pages/Irrigation';
import DiseaseDiagnosis from '@/pages/DiseaseDiagnosis';
import Reports from '@/pages/Reports';
import Profile from '@/pages/Profile';
import Placeholder from '@/pages/Placeholder';

function App() {
  const { refreshUser } = useAppStore();

  // Refresh user profile from backend on app load
  useEffect(() => {
    refreshUser();
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/features" element={<Placeholder />} />
          <Route path="/about" element={<Placeholder />} />
          <Route path="/contact" element={<Placeholder />} />
          <Route path="*" element={<Placeholder />} />
        </Route>

        {/* Auth pages (standalone, no layout) */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Dashboard pages */}
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="crop" element={<CropRecommendation />} />
          <Route path="irrigation" element={<Irrigation />} />
          <Route path="disease" element={<DiseaseDiagnosis />} />
          <Route path="reports" element={<Reports />} />
          <Route path="profile" element={<Profile />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
