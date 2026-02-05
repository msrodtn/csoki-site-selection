import { BrandFilter } from './BrandFilter';
import { StateFilter } from './StateFilter';
import { MapboxSearchBar } from '../Map/MapboxSearchBar';
import { MapLayers } from './MapLayers';
import { OpportunitiesFilter } from './OpportunitiesFilter';
import { CrexiSearch } from './CrexiSearch';
import { MapPin } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';

export function Sidebar() {
  const { navigateTo, setAllStatesVisible, visibleLayers } = useMapStore();

  const handleSearchSelect = (lng: number, lat: number, _placeName: string) => {
    // Enable all states to show stores in searched area
    setAllStatesVisible(true);
    // Navigate to location
    navigateTo(lat, lng, 12);
  };

  return (
    <div className="w-80 bg-white border-r border-gray-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-red-600 to-red-700">
        <div className="flex items-center gap-2 text-white">
          <MapPin className="w-6 h-6" />
          <div>
            <h1 className="font-bold text-lg">CSOKi Site Selection</h1>
            <p className="text-xs text-red-100">Competitor Analysis Platform</p>
          </div>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        <MapboxSearchBar onSelect={handleSearchSelect} placeholder="Type a city name..." />
        <BrandFilter />
        <StateFilter />
        <MapLayers />
        <OpportunitiesFilter isVisible={visibleLayers.has('csoki_opportunities')} />
        <CrexiSearch isVisible={visibleLayers.has('properties_for_sale')} />
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-gray-50">
        <p className="text-xs text-gray-500 text-center">
          Phase 1 - Competitor Mapping
        </p>
      </div>
    </div>
  );
}
