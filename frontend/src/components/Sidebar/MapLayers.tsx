import { useState, useEffect } from 'react';
import { Layers, Droplets, Car, BarChart2, Flame, LandPlot, Building2, MapPinned, DollarSign, Diamond, MapPin, Search, Grid, SlidersHorizontal, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';
import { listingsApi } from '../../services/api';

// Layer definitions
export const MAP_LAYERS = {
  fema_flood: {
    id: 'fema_flood',
    name: 'FEMA Flood Zones',
    icon: Droplets,
    color: '#3B82F6',
    description: 'Requires zoom 12+ to display',
  },
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
  parcels: {
    id: 'parcels',
    name: 'Parcel Boundaries',
    icon: LandPlot,
    color: '#A16207',
    description: 'Property parcel lines (zoom 14+)',
  },
  competition_heat: {
    id: 'competition_heat',
    name: 'Competition Heat Map',
    icon: Flame,
    color: '#F97316',
    description: 'Store density visualization',
  },
  business_labels: {
    id: 'business_labels',
    name: 'Business Labels',
    icon: Building2,
    color: '#6366F1',
    description: 'Show business names on map',
  },
  zoning: {
    id: 'zoning',
    name: 'Zoning Colors',
    icon: MapPinned,
    color: '#059669',
    description: 'Color-code parcels by zoning type',
  },
  properties_for_sale: {
    id: 'properties_for_sale',
    name: 'Active Listings',
    icon: DollarSign,
    color: '#22C55E',
    description: 'Crexi, LoopNet & team-flagged properties',
    hasSubToggles: true,
  },
  csoki_opportunities: {
    id: 'csoki_opportunities',
    name: 'CSOKi Opportunities',
    icon: Diamond,
    color: '#9333EA',
    description: 'Filtered: 0.8-2ac or 2.5-6k sqft with signals',
  },
  boundaries: {
    id: 'boundaries',
    name: 'Administrative Boundaries',
    icon: Grid,
    color: '#627BC1',
    description: 'Counties, cities, ZIP codes',
  },
} as const;

// Sub-toggle definitions for Properties For Sale layer
const PROPERTY_SUB_TOGGLES = [
  {
    id: 'scraped' as const,
    name: 'Active Listings',
    icon: Search,
    color: '#3B82F6', // Blue
    description: 'Crexi & LoopNet listings',
  },
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

// Inline Crexi Search Component
function InlineCrexiSearch() {
  const [location, setLocation] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState<{ total_filtered: number; cached: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<{
    playwrightAvailable: boolean;
    crexiLoaded: boolean;
    credentialsSet: boolean;
  } | null>(null);

  useEffect(() => {
    listingsApi.getDiagnostics().then((data) => {
      setDiagnostics({
        playwrightAvailable: data.playwright.available,
        crexiLoaded: data.crexi.automation_loaded,
        credentialsSet: data.crexi.credentials.username_set && data.crexi.credentials.password_set,
      });
    }).catch(() => {
      setDiagnostics({ playwrightAvailable: false, crexiLoaded: false, credentialsSet: false });
    });
  }, []);

  const isReady = diagnostics?.playwrightAvailable && diagnostics?.crexiLoaded && diagnostics?.credentialsSet;

  const handleSearch = async () => {
    if (!location.trim()) return;
    setIsSearching(true);
    setError(null);
    try {
      const response = await listingsApi.fetchCrexiArea({ location: location.trim() });
      setResult({ total_filtered: response.total_filtered, cached: response.cached });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="ml-6 mt-2 p-3 bg-blue-50 rounded-lg border-l-2 border-blue-300">
      <div className="flex items-center gap-2 mb-2">
        <Search className="w-3 h-3 text-blue-600" />
        <span className="text-xs font-medium text-blue-800">Crexi Search</span>
        {diagnostics && (
          <span className={`ml-auto ${isReady ? 'text-green-600' : 'text-amber-600'}`}>
            {isReady ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
          </span>
        )}
      </div>

      {isReady ? (
        <>
          <div className="flex gap-1 mb-2">
            <input
              type="text"
              placeholder="Des Moines, IA"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              disabled={isSearching}
              className="flex-1 px-2 py-1 text-xs border rounded focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={handleSearch}
              disabled={isSearching || !location.trim()}
              className="px-2 py-1 bg-blue-600 text-white rounded text-xs disabled:bg-gray-400"
            >
              {isSearching ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Go'}
            </button>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          {result && (
            <p className="text-xs text-gray-600">
              Found {result.total_filtered} opportunities {result.cached && '(cached)'}
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-500">
          {!diagnostics?.playwrightAvailable ? 'Playwright unavailable' : 'Crexi credentials not set'}
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
  } = useMapStore();

  const layerArray = Array.from(visibleLayers);
  const propertySourcesArray = Array.from(visiblePropertySources);

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
              {hasSubToggles && isActive && (
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

              {/* Inline Crexi Search for Active Listings layer */}
              {layer.id === 'properties_for_sale' && isActive && <InlineCrexiSearch />}

              {/* Inline Opportunities Filter for CSOKi Opportunities layer */}
              {layer.id === 'csoki_opportunities' && isActive && <InlineOpportunitiesFilter />}
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
