/**
 * Map Style Switcher Component
 * 
 * Allows users to toggle between different Mapbox map styles:
 * - Streets (default)
 * - Satellite
 * - Satellite Streets (hybrid)
 * - Outdoors/Terrain
 * - Light
 * - Dark
 * - Navigation (3D buildings)
 */

import { useState } from 'react';
import { Map, Layers } from 'lucide-react';

export interface MapStyle {
  id: string;
  name: string;
  url: string;
  description: string;
  icon?: string;
}

export const MAP_STYLES: MapStyle[] = [
  {
    id: 'standard',
    name: '3D Standard',
    url: 'mapbox://styles/mapbox/standard',
    description: '3D buildings with dynamic lighting',
  },
  {
    id: 'streets',
    name: 'Streets',
    url: 'mapbox://styles/mapbox/streets-v12',
    description: 'Classic street map',
  },
  {
    id: 'satellite-streets',
    name: 'Satellite',
    url: 'mapbox://styles/mapbox/satellite-streets-v12',
    description: 'Aerial imagery with labels and POIs',
  },
  {
    id: 'outdoors',
    name: 'Terrain',
    url: 'mapbox://styles/mapbox/outdoors-v12',
    description: 'Topographic and terrain features',
  },
  {
    id: 'light',
    name: 'Light',
    url: 'mapbox://styles/mapbox/light-v11',
    description: 'Minimal light theme',
  },
  {
    id: 'dark',
    name: 'Dark',
    url: 'mapbox://styles/mapbox/dark-v11',
    description: 'Dark mode friendly',
  },
  {
    id: 'navigation-day',
    name: 'Navigation',
    url: 'mapbox://styles/mapbox/navigation-day-v1',
    description: '3D buildings and navigation',
  },
];

interface MapStyleSwitcherProps {
  currentStyle: string;
  onStyleChange: (styleUrl: string) => void;
}

export default function MapStyleSwitcher({ currentStyle, onStyleChange }: MapStyleSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);

  const currentStyleObj = MAP_STYLES.find(s => s.url === currentStyle) || MAP_STYLES[0];

  return (
    <div className="absolute top-4 left-4 z-10">
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-white rounded-lg shadow-lg px-4 py-2 flex items-center gap-2 hover:bg-gray-50 transition-colors"
        title="Change map style"
      >
        <Layers className="w-5 h-5 text-gray-700" />
        <span className="font-medium text-gray-700">{currentStyleObj.name}</span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-0"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute top-12 left-0 bg-white rounded-lg shadow-xl border border-gray-200 w-64 overflow-hidden z-10">
            <div className="p-2 bg-gray-50 border-b border-gray-200">
              <h3 className="font-semibold text-gray-700 text-sm flex items-center gap-2">
                <Map className="w-4 h-4" />
                Map Styles
              </h3>
            </div>

            <div className="max-h-96 overflow-y-auto">
              {MAP_STYLES.map((style) => (
                <button
                  key={style.id}
                  onClick={() => {
                    onStyleChange(style.url);
                    setIsOpen(false);
                  }}
                  className={`
                    w-full px-4 py-3 text-left hover:bg-blue-50 transition-colors
                    border-b border-gray-100 last:border-b-0
                    ${currentStyle === style.url ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''}
                  `}
                >
                  <div className="font-medium text-gray-900">{style.name}</div>
                  <div className="text-xs text-gray-500 mt-1">{style.description}</div>
                </button>
              ))}
            </div>

            <div className="p-2 bg-gray-50 border-t border-gray-200">
              <p className="text-xs text-gray-500 text-center">
                Powered by Mapbox
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
