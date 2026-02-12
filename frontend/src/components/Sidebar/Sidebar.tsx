import { useState, useEffect, useCallback } from 'react';
import { BrandFilter } from './BrandFilter';
import { StateFilter } from './StateFilter';
import { MapboxSearchBar } from '../Map/MapboxSearchBar';
import { MapLayers } from './MapLayers';
import { MapPin, PanelLeftClose } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';

const MIN_WIDTH = 240;
const MAX_WIDTH = 480;
const COLLAPSE_SNAP = 120;

export function Sidebar() {
  const {
    navigateTo,
    setAllStatesVisible,
    mapSidebarWidth,
    setMapSidebarWidth,
    mapSidebarCollapsed,
    setMapSidebarCollapsed,
    toggleMapSidebar,
  } = useMapStore();
  const [isDragging, setIsDragging] = useState(false);

  const handleSearchSelect = (lng: number, lat: number, _placeName: string) => {
    setAllStatesVisible(true);
    navigateTo(lat, lng, 12);
  };

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const sidebarEl = document.getElementById('map-sidebar');
      if (!sidebarEl) return;
      const rect = sidebarEl.getBoundingClientRect();
      const newWidth = e.clientX - rect.left;
      if (newWidth < COLLAPSE_SNAP) {
        setMapSidebarCollapsed(true);
        setIsDragging(false);
      } else {
        setMapSidebarCollapsed(false);
        setMapSidebarWidth(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth)));
      }
    };

    const handleMouseUp = () => setIsDragging(false);

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, setMapSidebarWidth, setMapSidebarCollapsed]);

  if (mapSidebarCollapsed) return null;

  return (
    <div
      id="map-sidebar"
      className="relative bg-white border-r border-gray-200 flex flex-col h-full overflow-hidden flex-shrink-0"
      style={{
        width: mapSidebarWidth,
        transition: isDragging ? 'none' : 'width 200ms ease',
      }}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-red-600 to-red-700">
        <div className="flex items-center justify-between text-white">
          <div className="flex items-center gap-2">
            <MapPin className="w-6 h-6" />
            <div>
              <h1 className="font-bold text-lg">CSOKi Site Selection</h1>
              <p className="text-xs text-red-100">Competitor Analysis Platform</p>
            </div>
          </div>
          <button
            onClick={toggleMapSidebar}
            title="Collapse sidebar"
            className="p-1 rounded hover:bg-white/20 transition-colors"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        <MapboxSearchBar onSelect={handleSearchSelect} placeholder="Type a city name..." />
        <BrandFilter />
        <StateFilter />
        <MapLayers />
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-gray-50">
        <p className="text-xs text-gray-500 text-center">
          Phase 1 - Competitor Mapping
        </p>
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-red-500/20 active:bg-red-500/30 transition-colors z-10"
      />
    </div>
  );
}
