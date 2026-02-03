import { Layers, Droplets, Car, Train, Flame, LandPlot, Building2, MapPinned, DollarSign, Diamond, MapPin, Search } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';

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
  transit: {
    id: 'transit',
    name: 'Transit',
    icon: Train,
    color: '#8B5CF6',
    description: 'Public transit routes',
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
    name: 'Properties For Sale',
    icon: DollarSign,
    color: '#22C55E',
    description: 'ATTOM opportunities & team flagged',
    hasSubToggles: true,
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

export function MapLayers() {
  const { visibleLayers, toggleLayer, visiblePropertySources, togglePropertySource } = useMapStore();

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
