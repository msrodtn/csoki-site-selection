import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { PasswordGate } from './components/Auth/PasswordGate';
import { AppShell } from './layouts/AppShell';
import { DashboardPage } from './pages/DashboardPage';
import { MapPage } from './pages/MapPage';
import { ScoutLayout } from './pages/scout/ScoutLayout';
import { DeployPage } from './pages/scout/DeployPage';
import { ReportsPage } from './pages/scout/ReportsPage';
import { ReportDetailPage } from './pages/scout/ReportDetailPage';
import { ReviewPage } from './pages/scout/ReviewPage';
import { PropertiesPage } from './pages/PropertiesPage';
import { SettingsPage } from './pages/SettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PasswordGate>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/map" element={<MapPage />} />
              <Route path="/scout" element={<ScoutLayout />}>
                <Route index element={<Navigate to="deploy" replace />} />
                <Route path="deploy" element={<DeployPage />} />
                <Route path="reports" element={<ReportsPage />} />
                <Route path="reports/:reportId" element={<ReportDetailPage />} />
                <Route path="review" element={<ReviewPage />} />
              </Route>
              <Route path="/properties" element={<PropertiesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </PasswordGate>
    </QueryClientProvider>
  );
}

export default App;
