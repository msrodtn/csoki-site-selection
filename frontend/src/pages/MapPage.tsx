import { Sidebar } from '../components/Sidebar/Sidebar';
import { MapboxMap } from '../components/Map/MapboxMap';
import { AnalysisPanel } from '../components/Analysis/AnalysisPanel';
import { ComparePanel } from '../components/Analysis/ComparePanel';
import { PanelLeftOpen } from 'lucide-react';
import { useMapStore } from '../store/useMapStore';

export function MapPage() {
  const { mapSidebarCollapsed, toggleMapSidebar } = useMapStore();

  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar />
      <div className="flex-1 relative">
        <MapboxMap />
        <AnalysisPanel />
        <ComparePanel />

        {/* Expand button when sidebar is collapsed */}
        {mapSidebarCollapsed && (
          <button
            onClick={toggleMapSidebar}
            title="Expand sidebar"
            className="absolute top-4 left-4 z-10 p-2 bg-white rounded-lg shadow-md border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            <PanelLeftOpen className="w-5 h-5 text-gray-600" />
          </button>
        )}
      </div>
    </div>
  );
}
