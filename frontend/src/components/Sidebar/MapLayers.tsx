import { useState } from 'react';
import { Layers, Droplets, Car, BarChart2, Flame, LandPlot, Building2, MapPinned, DollarSign, Diamond, MapPin, Search, Grid, SlidersHorizontal, Loader2, ShoppingBag, Film, UtensilsCrossed } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';
import { listingsApi } from '../../services/api';

// Layer definitions - ordered with interactive layers at top for visibility
export const MAP_LAYERS = {
  // === Primary layers with inline controls (most used) ===
  csoki_opportunities: {
    id: 'csoki_opportunities',
    name: 'CSOKi Opportunities',
    icon: Diamond,
    color: '#9333EA',
    description: 'ATTOM opportunities + Crexi/LoopNet listings, scored & ranked',
  },
  properties_for_sale: {
    id: 'properties_for_sale',
    name: 'Active Listings',
    icon: DollarSign,
    color: '#22C55E',
    description: 'ATTOM all-properties & team-flagged',
    hasSubToggles: true,
  },
  boundaries: {
    id: 'boundaries',
    name: 'Boundaries Explorer',
    icon: Grid,
    color: '#627BC1',
    description: 'Counties, cities, ZIP codes + demographics',
    hasSubToggles: true,
  },
  // === Analysis layers ===
  activity_heat: {
    id: 'activity_heat',
    name: 'Activity Heat Map',
    icon: Flame,
    color: '#F97316',
    description: 'Foot traffic potential (Shopping + Entertainment + Dining)',
    hasSubToggles: true,
  },
  parcels: {
    id: 'parcels',
    name: 'Parcel Boundaries',
    icon: LandPlot,
    color: '#A16207',
    description: 'Property parcel lines (zoom 14+)',
  },
  zoning: {
    id: 'zoning',
    name: 'Zoning Colors',
    icon: MapPinned,
    color: '#059669',
    description: 'Color-code parcels by zoning type',
  },
  // === Reference layers ===
  traffic: {
    id: 'traffic',
    name: 'Traffic',
    icon: Car,
    color: '#EF4444',
    description: 'Real-time traffic conditions',
  },
  traffic_counts: {
    id: 'traffic_counts',
    name: 'Traffic Counts (AADT)',
    icon: BarChart2,
    color: '#8B5CF6',
    description: 'Annual Avg Daily Traffic (Iowa)',
  },
  fema_flood: {
    id: 'fema_flood',
    name: 'FEMA Flood Zones',
    icon: Droplets,
    color: '#3B82F6',
    description: 'Requires zoom 12+ to display',
  },
} as const;

// Sub-toggle definitions for Properties For Sale layer
const PROPERTY_SUB_TOGGLES = [
  {
    id: 'attom' as const,
    name: 'Opportunities',
    icon: Diamond,
    color: '#8B5CF6', // Purple
    description: 'ATTOM predictive signals',
  },
  {
    id: 'team' as const,
    name: 'Team Flagged',
    icon: MapPin,
    color: '#F97316', // Orange
    description: 'User-contributed properties',
  },
];

// Sub-toggle definitions for Activity Heat Map layer
const ACTIVITY_NODE_SUB_TOGGLES = [
  {
    id: 'shopping' as const,
    name: 'Shopping',
    icon: ShoppingBag,
    color: '#8B5CF6',
    description: 'Big box, malls, major retail',
  },
  {
    id: 'entertainment' as const,
    name: 'Entertainment',
    icon: Film,
    color: '#EC4899',
    description: 'Theaters, gyms, attractions',
  },
  {
    id: 'dining' as const,
    name: 'Dining',
    icon: UtensilsCrossed,
    color: '#10B981',
    description: 'Restaurants, QSR, bars',
  },
];

// Sub-toggle definitions for Boundaries Explorer layer
const BOUNDARY_SUB_TOGGLES = [
  {
    id: 'counties' as const,
    name: 'Counties',
    icon: Grid,
    color: '#3B82F6', // Blue
    description: 'County boundaries',
  },
  {
    id: 'cities' as const,
    name: 'Cities',
    icon: Building2,
    color: '#22C55E', // Green
    description: 'City/place boundaries',
  },
  {
    id: 'zipcodes' as const,
    name: 'ZIP Codes',
    icon: MapPinned,
    color: '#F97316', // Orange
    description: 'ZIP code boundaries',
  },
  {
    id: 'census_tracts' as const,
    name: 'Census Tracts',
    icon: BarChart2,
    color: '#8B5CF6', // Purple
    description: 'Demographics choropleth',
  },
];

export type MapLayerId = keyof typeof MAP_LAYERS;

// Inline Opportunities Filter Component
function InlineOpportunitiesFilter() {
  const { opportunityFilters, setOpportunityFilters } = useMapStore();

  return (
    <div className="ml-6 mt-2 p-3 bg-purple-50 rounded-lg border-l-2 border-purple-300">
      <div className="flex items-center gap-2 mb-2">
        <SlidersHorizontal className="w-3 h-3 text-purple-600" />
        <span className="text-xs font-medium text-purple-800">Filter Criteria</span>
      </div>

      {/* Parcel Size */}
      <div className="mb-2">
        <label className="text-xs text-gray-600">Parcel (acres)</label>
        <div className="flex items-center gap-1 mt-0.5">
          <input
            type="number"
            step="0.1"
            min="0"
            value={opportunityFilters.minParcelAcres}
            onChange={(e) => {
              const num = parseFloat(e.target.value);
              if (!isNaN(num) && num >= 0) setOpportunityFilters({ minParcelAcres: num });
            }}
            className="w-16 px-1.5 py-1 text-xs border rounded focus:ring-1 focus:ring-purple-500"
          />
          <span className="text-xs text-gray-400">-</span>
          <input
            type="number"
            step="0.1"
            min="0"
            value={opportunityFilters.maxParcelAcres}
            onChange={(e) => {
              const num = parseFloat(e.target.value);
              if (!isNaN(num) && num >= 0) setOpportunityFilters({ maxParcelAcres: num });
            }}
            className="w-16 px-1.5 py-1 text-xs border rounded focus:ring-1 focus:ring-purple-500"
          />
        </div>
      </div>

      {/* Building Size */}
      <div className="mb-2">
        <label className="text-xs text-gray-600">Building (sqft)</label>
        <div className="flex items-center gap-1 mt-0.5">
          <input
            type="number"
            step="100"
            min="0"
            value={opportunityFilters.minBuildingSqft}
            onChange={(e) => {
              const num = parseInt(e.target.value, 10);
              if (!isNaN(num) && num >= 0) setOpportunityFilters({ minBuildingSqft: num });
            }}
            className="w-16 px-1.5 py-1 text-xs border rounded focus:ring-1 focus:ring-purple-500"
          />
          <span className="text-xs text-gray-400">-</span>
          <input
            type="number"
            step="100"
            min="0"
            value={opportunityFilters.maxBuildingSqft}
            onChange={(e) => {
              const num = parseInt(e.target.value, 10);
              if (!isNaN(num) && num >= 0) setOpportunityFilters({ maxBuildingSqft: num });
            }}
            className="w-16 px-1.5 py-1 text-xs border rounded focus:ring-1 focus:ring-purple-500"
          />
        </div>
      </div>

      {/* Property Types */}
      <div className="flex flex-wrap gap-1">
        {['Land', 'Retail', 'Office'].map((type) => {
          const key = `include${type}` as 'includeLand' | 'includeRetail' | 'includeOffice';
          const isActive = opportunityFilters[key];
          return (
            <button
              key={type}
              onClick={() => setOpportunityFilters({ [key]: !isActive })}
              className={`px-2 py-0.5 text-xs rounded-full ${
                isActive ? 'bg-purple-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}
            >
              {type}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Inline Crexi CSV Upload Component
function InlineCrexiSearch() {
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<{ total_filtered: number; location: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setResult(null);
    try {
      const response = await listingsApi.uploadCrexiCSV(file);
      setResult({ total_filtered: response.total_filtered, location: response.location });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  return (
    <div className="ml-6 mt-2 p-3 bg-purple-50 rounded-lg border-l-2 border-purple-300">
      <div className="flex items-center gap-2 mb-2">
        <Search className="w-3 h-3 text-purple-600" />
        <span className="text-xs font-medium text-purple-800">Crexi Import</span>
      </div>
      <label className={`flex items-center justify-center gap-1 px-2 py-1.5 rounded text-xs font-medium cursor-pointer transition-colors ${
        isUploading ? 'bg-gray-300 text-gray-500' : 'bg-purple-600 text-white hover:bg-purple-700'
      }`}>
        {isUploading ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
        {isUploading ? 'Uploading...' : 'Upload Crexi CSV'}
        <input type="file" accept=".xlsx,.xls,.csv" onChange={handleFileChange} className="hidden" disabled={isUploading} />
      </label>
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      {result && (
        <p className="text-xs text-gray-600 mt-1">
          Imported {result.total_filtered} listings ({result.location})
        </p>
      )}
    </div>
  );
}

export function MapLayers() {
  const {
    visibleLayers,
    toggleLayer,
    visiblePropertySources,
    togglePropertySource,
    visibleBoundaryTypes,
    toggleBoundaryType,
    visibleActivityNodeCategories,
    toggleActivityNodeCategory,
  } = useMapStore();

  const layerArray = Array.from(visibleLayers);
  const propertySourcesArray = Array.from(visiblePropertySources);
  const boundaryTypesArray = Array.from(visibleBoundaryTypes);
  const activityNodeCategoriesArray = Array.from(visibleActivityNodeCategories);

  return (
    <div className="p-4 border-b border-gray-200">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="w-5 h-5 text-gray-600" />
        <h2 className="font-semibold text-gray-800">Map Layers</h2>
      </div>

      <div className="space-y-2">
        {Object.values(MAP_LAYERS).map((layer) => {
          const isActive = layerArray.includes(layer.id);
          const Icon = layer.icon;
          const hasSubToggles = 'hasSubToggles' in layer && layer.hasSubToggles;

          return (
            <div key={layer.id}>
              <button
                onClick={() => toggleLayer(layer.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${
                  isActive
                    ? 'bg-gray-100 border-2'
                    : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                }`}
                style={{
                  borderColor: isActive ? layer.color : undefined,
                }}
              >
                <div
                  className={`p-1.5 rounded-md transition-colors ${
                    isActive ? 'bg-opacity-20' : 'bg-gray-200'
                  }`}
                  style={{
                    backgroundColor: isActive ? `${layer.color}20` : undefined,
                  }}
                >
                  <Icon
                    className="w-4 h-4"
                    style={{ color: isActive ? layer.color : '#6B7280' }}
                  />
                </div>
                <div className="flex-1 text-left">
                  <div
                    className={`text-sm font-medium ${
                      isActive ? 'text-gray-900' : 'text-gray-600'
                    }`}
                  >
                    {layer.name}
                  </div>
                  <div className="text-xs text-gray-400">{layer.description}</div>
                </div>
                <div
                  className={`w-2 h-2 rounded-full transition-colors ${
                    isActive ? 'bg-green-500' : 'bg-gray-300'
                  }`}
                />
              </button>

              {/* Sub-toggles for Properties For Sale layer */}
              {layer.id === 'properties_for_sale' && hasSubToggles && isActive && (
                <div className="ml-6 mt-1 space-y-1 border-l-2 border-gray-200 pl-3">
                  {PROPERTY_SUB_TOGGLES.map((subToggle) => {
                    const isSubActive = propertySourcesArray.includes(subToggle.id);
                    const SubIcon = subToggle.icon;

                    return (
                      <button
                        key={subToggle.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          togglePropertySource(subToggle.id);
                        }}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all text-left ${
                          isSubActive
                            ? 'bg-gray-50'
                            : 'hover:bg-gray-50 opacity-60'
                        }`}
                      >
                        <SubIcon
                          className="w-3.5 h-3.5"
                          style={{ color: isSubActive ? subToggle.color : '#9CA3AF' }}
                        />
                        <span
                          className={`text-xs font-medium ${
                            isSubActive ? 'text-gray-700' : 'text-gray-400'
                          }`}
                        >
                          {subToggle.name}
                        </span>
                        <div
                          className={`ml-auto w-1.5 h-1.5 rounded-full ${
                            isSubActive ? 'bg-green-500' : 'bg-gray-300'
                          }`}
                        />
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Sub-toggles for Boundaries Explorer layer */}
              {layer.id === 'boundaries' && hasSubToggles && isActive && (
                <div className="ml-6 mt-1 space-y-1 border-l-2 border-gray-200 pl-3">
                  {BOUNDARY_SUB_TOGGLES.map((subToggle) => {
                    const isSubActive = boundaryTypesArray.includes(subToggle.id);
                    const SubIcon = subToggle.icon;

                    return (
                      <button
                        key={subToggle.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleBoundaryType(subToggle.id);
                        }}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all text-left ${
                          isSubActive
                            ? 'bg-gray-50'
                            : 'hover:bg-gray-50 opacity-60'
                        }`}
                      >
                        <SubIcon
                          className="w-3.5 h-3.5"
                          style={{ color: isSubActive ? subToggle.color : '#9CA3AF' }}
                        />
                        <span
                          className={`text-xs font-medium ${
                            isSubActive ? 'text-gray-700' : 'text-gray-400'
                          }`}
                        >
                          {subToggle.name}
                        </span>
                        <div
                          className={`ml-auto w-1.5 h-1.5 rounded-full ${
                            isSubActive ? 'bg-green-500' : 'bg-gray-300'
                          }`}
                        />
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Sub-toggles for Activity Heat Map layer */}
              {layer.id === 'activity_heat' && hasSubToggles && isActive && (
                <div className="ml-6 mt-1 space-y-1 border-l-2 border-gray-200 pl-3">
                  {ACTIVITY_NODE_SUB_TOGGLES.map((subToggle) => {
                    const isSubActive = activityNodeCategoriesArray.includes(subToggle.id);
                    const SubIcon = subToggle.icon;

                    return (
                      <button
                        key={subToggle.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleActivityNodeCategory(subToggle.id);
                        }}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all text-left ${
                          isSubActive
                            ? 'bg-gray-50'
                            : 'hover:bg-gray-50 opacity-60'
                        }`}
                      >
                        <SubIcon
                          className="w-3.5 h-3.5"
                          style={{ color: isSubActive ? subToggle.color : '#9CA3AF' }}
                        />
                        <span
                          className={`text-xs font-medium ${
                            isSubActive ? 'text-gray-700' : 'text-gray-400'
                          }`}
                        >
                          {subToggle.name}
                        </span>
                        <div
                          className={`ml-auto w-1.5 h-1.5 rounded-full ${
                            isSubActive ? 'bg-green-500' : 'bg-gray-300'
                          }`}
                        />
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Inline Opportunities Filter + Crexi Import for CSOKi Opportunities layer */}
              {layer.id === 'csoki_opportunities' && isActive && <InlineOpportunitiesFilter />}
              {layer.id === 'csoki_opportunities' && isActive && <InlineCrexiSearch />}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-gray-400 mt-3 text-center">
        Layers work best when zoomed in
      </p>
    </div>
  );
}
