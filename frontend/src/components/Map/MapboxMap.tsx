/**
 * Mapbox GL JS Map Component
 *
 * Full-featured map component using Mapbox as the primary mapping provider.
 * Replaces Google Maps implementation with feature parity.
 */
import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import Map, {
  Marker,
  Popup,
  Source,
  Layer,
  ScaleControl,
} from '@vis.gl/react-mapbox';
import type { MapRef, ViewStateChangeEvent, MarkerEvent } from '@vis.gl/react-mapbox';
import type {
  HeatmapLayerSpecification,
  FillLayerSpecification,
  LineLayerSpecification,
} from 'mapbox-gl';
import * as turf from '@turf/turf';
import { wktToGeoJSON } from '@terraformer/wkt';
import { useStores } from '../../hooks/useStores';
import { useMapStore } from '../../store/useMapStore';
import { analysisApi, teamPropertiesApi, opportunitiesApi, activityNodesApi } from '../../services/api';
import {
  BRAND_COLORS,
  BRAND_LABELS,
  BRAND_LOGOS,
  POI_CATEGORY_COLORS,
  POI_CATEGORY_LABELS,
  PROPERTY_TYPE_COLORS,
  TEAM_PROPERTY_COLOR,
  TEAM_PROPERTY_SOURCE_LABELS,
  type Store,
  type BrandKey,
  type POICategory,
  type PropertyListing,
  type TeamProperty,
  type ParcelInfo,
  type OpportunityRanking,
  type ActivityNode,
} from '../../types/store';
import { FEMALegend } from './FEMALegend';
import { HeatMapLegend } from './HeatMapLegend';
import { ParcelLegend } from './ParcelLegend';
import { ZoningLegend } from './ZoningLegend';
import { TrafficCountsLegend } from './TrafficCountsLegend';
import { QuickStatsBar } from './QuickStatsBar';
import { DraggableParcelInfo } from './DraggableParcelInfo';
import { PropertyInfoCard } from './PropertyInfoCard';
import { PropertyLegend } from './PropertyLegend';
import { TeamPropertyForm } from './TeamPropertyForm';
import MapStyleSwitcher from './MapStyleSwitcher';
import IsochroneControl, { type IsochroneSettings, type TravelMode } from './IsochroneControl';
import { fetchIsochrone, getIsochroneColor, getIsochroneOpacity } from '../../services/mapbox-isochrone';
import {
  buildActivityNodeHeatmapPaint,
} from '../../utils/mapbox-expressions';
import CompetitorAccessPanel from '../Analysis/CompetitorAccessPanel';
import { MapboxOverlay } from '@deck.gl/mapbox';
// Hexagon layer removed - not useful for site selection workflow
// import { createOpportunityHexagonLayer } from './layers/OpportunityHexagonLayer';
import { createCompetitorArcLayer } from './layers/CompetitorArcLayer';
import { POILayer } from './layers/POILayer';
import { BuildingLayer, type BuildingInfo } from './layers/BuildingLayer';
import { NavigationControl, GeolocateControl, ScreenshotControl, DrawControl, MeasurementControl } from './controls';
import { MeasurementLayer } from './layers/MeasurementLayer';
import { PulsingOpportunityMarker } from './PulsingOpportunityMarker';

// Feature flag for native POI layers (set to true to use new performant layers)
const USE_NATIVE_POI_LAYERS = true;

// Mapbox access token - try runtime config first (for Docker), then build-time env vars
const MAPBOX_TOKEN = 
  (window as any).RUNTIME_CONFIG?.MAPBOX_TOKEN || 
  import.meta.env.VITE_MAPBOX_TOKEN || 
  import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 
  '';

// Initial map view (Iowa/Nebraska region)
const INITIAL_VIEW = {
  longitude: -96.0,
  latitude: 41.5,
  zoom: 6,
};

// Mapbox Tileset IDs for administrative boundaries (Census TIGER data)
// NOTE: source-layer names are assigned by Mapbox during upload - found in Mapbox Studio
const BOUNDARY_TILESETS = {
  counties: {
    id: 'msrodtn.national-counties',
    sourceLayer: 'national_counties',
  },
  cities: {
    id: 'msrodtn.national-cities',
    sourceLayer: 'national_cities',
  },
  zctas: {
    id: 'msrodtn.national-zctas',
    sourceLayer: 'national_zctas',
  },
  tracts: {
    id: 'msrodtn.national-tracts',
    sourceLayer: 'national_tracts',
  },
};

// Helper to parse WKT to GeoJSON
function parseWKTToGeoJSON(wkt: string): GeoJSON.Geometry | null {
  if (!wkt) return null;
  try {
    return wktToGeoJSON(wkt) as GeoJSON.Geometry;
  } catch (e) {
    console.error('Failed to parse WKT geometry:', e);
    return null;
  }
}

// Calculate zoom-based marker size for competitor/brand markers
// MUST be significantly larger than POI markers at all zoom levels
function getZoomBasedSize(zoom: number, isSelected: boolean): number {
  // Base size: zoom 6 → 24px, zoom 10 → 32px, zoom 14 → 40px, zoom 18 → 48px
  // These are large enough to be clearly visible as primary markers
  let baseSize: number;
  if (zoom <= 6) {
    baseSize = 24;
  } else if (zoom <= 10) {
    baseSize = 24 + ((zoom - 6) / 4) * 8; // 24 to 32
  } else if (zoom <= 14) {
    baseSize = 32 + ((zoom - 10) / 4) * 8; // 32 to 40
  } else {
    baseSize = 40 + ((zoom - 14) / 4) * 8; // 40 to 48
  }
  // Selected markers are 25% larger
  return isSelected ? Math.round(baseSize * 1.25) : Math.round(baseSize);
}

// Calculate zoom-based marker size for POI markers
// Always MUCH smaller than brand markers - these are secondary indicators
function getPOIZoomBasedSize(zoom: number, isSelected: boolean): number {
  // POI SVG uses size*2 for width/height, so actual sizes will be:
  // zoom 6 → 12px, zoom 10 → 16px, zoom 14 → 20px, zoom 18 → 24px
  // Half or less of brand marker sizes
  let baseSize: number;
  if (zoom <= 6) {
    baseSize = 6;
  } else if (zoom <= 10) {
    baseSize = 6 + ((zoom - 6) / 4) * 2; // 6 to 8
  } else if (zoom <= 14) {
    baseSize = 8 + ((zoom - 10) / 4) * 2; // 8 to 10
  } else {
    baseSize = 10 + ((zoom - 14) / 4) * 2; // 10 to 12
  }
  return isSelected ? Math.round(baseSize * 1.3) : Math.round(baseSize);
}

// Brand marker component with zoom-dependent sizing
function BrandMarker({
  store,
  isSelected,
  onClick,
  zoom = 10,
}: {
  store: Store;
  isSelected: boolean;
  onClick: () => void;
  zoom?: number;
}) {
  const brand = store.brand as BrandKey;
  const color = BRAND_COLORS[brand] || '#666666';
  const logo = BRAND_LOGOS[brand];
  const size = getZoomBasedSize(zoom, isSelected);

  if (!store.latitude || !store.longitude) return null;

  return (
    <Marker
      longitude={store.longitude}
      latitude={store.latitude}
      anchor="center"
      onClick={(e: MarkerEvent<MouseEvent>) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
      style={{ zIndex: isSelected ? 2000 : 500 }}
    >
      <div
        className="cursor-pointer transition-transform duration-150"
        style={{
          transform: isSelected ? 'scale(1.3)' : 'scale(1)',
        }}
      >
        {logo ? (
          <img
            src={logo}
            alt={brand}
            style={{
              width: size,
              height: size,
              borderRadius: '50%',
              border: `2px solid ${isSelected ? '#000' : color}`,
              boxShadow: isSelected ? '0 0 8px rgba(0,0,0,0.5)' : '0 2px 4px rgba(0,0,0,0.3)',
              backgroundColor: 'white',
            }}
          />
        ) : (
          <div
            style={{
              width: size,
              height: size,
              borderRadius: '50%',
              backgroundColor: color,
              border: `2px solid ${isSelected ? '#000' : 'white'}`,
              boxShadow: isSelected ? '0 0 8px rgba(0,0,0,0.5)' : '0 2px 4px rgba(0,0,0,0.3)',
            }}
          />
        )}
      </div>
    </Marker>
  );
}

// POI marker component with zoom-responsive sizing and name labels
function POIMarker({
  poi,
  isSelected,
  onClick,
  zoom = 10,
}: {
  poi: {
    place_id: string;
    name: string;
    category: POICategory;
    latitude: number;
    longitude: number;
    address: string | null;
    rating: number | null;
  };
  isSelected: boolean;
  onClick: () => void;
  zoom?: number;
}) {
  const color = POI_CATEGORY_COLORS[poi.category] || '#666';
  const size = getPOIZoomBasedSize(zoom, isSelected);
  const showLabel = zoom >= 16; // Show POI names at street level

  return (
    <Marker
      longitude={poi.longitude}
      latitude={poi.latitude}
      anchor="center"
      onClick={(e: MarkerEvent<MouseEvent>) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
      style={{ zIndex: isSelected ? 50 : 10, cursor: 'pointer' }}
    >
      <div className="flex flex-col items-center">
        {showLabel && (
          <span
            className="text-[10px] bg-white/90 px-1 rounded shadow-sm mb-0.5 whitespace-nowrap max-w-[100px] truncate"
            style={{ color: color }}
          >
            {poi.name}
          </span>
        )}
        <svg
          width={size * 2}
          height={size * 2}
          viewBox="0 0 24 24"
          style={{ filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.3))' }}
        >
          <path
            d="M12 2L4 12l8 10 8-10L12 2z"
            fill={color}
            stroke="white"
            strokeWidth={isSelected ? 2 : 1.5}
          />
        </svg>
      </div>
    </Marker>
  );
}

// Property marker component (ATTOM)
function PropertyMarker({
  property,
  isSelected,
  onClick,
}: {
  property: PropertyListing;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isOpportunity = property.listing_type === 'opportunity';
  const typeColor = PROPERTY_TYPE_COLORS[property.property_type] || '#22C55E';
  const size = isSelected ? 20 : 14;

  return (
    <Marker
      longitude={property.longitude}
      latitude={property.latitude}
      anchor="center"
      onClick={(e: MarkerEvent<MouseEvent>) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
      style={{ zIndex: isSelected ? 1500 : 200 }}
    >
      {isOpportunity ? (
        // Diamond shape for opportunities
        <svg width={size} height={size} viewBox="0 0 24 24">
          <path
            d="M12 2L22 12L12 22L2 12L12 2z"
            fill="#8B5CF6"
            stroke={isSelected ? 'white' : '#6D28D9'}
            strokeWidth={isSelected ? 3 : 2}
          />
        </svg>
      ) : (
        // Circle for active listings
        <svg width={size} height={size} viewBox="0 0 24 24">
          <circle
            cx="12"
            cy="12"
            r="10"
            fill={typeColor}
            stroke={isSelected ? 'white' : typeColor}
            strokeWidth={isSelected ? 3 : 2}
          />
        </svg>
      )}
    </Marker>
  );
}

// Team property marker component
function TeamPropertyMarker({
  property,
  isSelected,
  onClick,
}: {
  property: TeamProperty;
  isSelected: boolean;
  onClick: () => void;
}) {
  const size = isSelected ? 20 : 14;

  return (
    <Marker
      longitude={property.longitude}
      latitude={property.latitude}
      anchor="center"
      onClick={(e: MarkerEvent<MouseEvent>) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
      style={{ zIndex: isSelected ? 1600 : 250 }}
    >
      <svg width={size * 1.5} height={size * 2} viewBox="0 0 24 32">
        <path
          d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20c0-6.6-5.4-12-12-12z"
          fill={TEAM_PROPERTY_COLOR}
          stroke={isSelected ? 'white' : '#EA580C'}
          strokeWidth={isSelected ? 3 : 2}
        />
      </svg>
    </Marker>
  );
}

// Store popup component
function StorePopup({
  store,
  onClose,
  onAnalyze,
  isAnalyzing,
}: {
  store: Store;
  onClose: () => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}) {
  const brand = store.brand as BrandKey;
  const brandLabel = BRAND_LABELS[brand] || store.brand;
  const brandColor = BRAND_COLORS[brand] || '#666666';

  if (!store.latitude || !store.longitude) return null;

  return (
    <Popup
      longitude={store.longitude}
      latitude={store.latitude}
      anchor="bottom"
      onClose={onClose}
      closeButton={true}
      closeOnClick={false}
      className="store-popup"
    >
      <div className="min-w-[200px] p-1">
        <div
          className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white"
          style={{ backgroundColor: brandColor }}
        >
          {brandLabel}
        </div>
        <div className="text-sm">
          {store.street && <p className="font-medium">{store.street}</p>}
          <p>
            {store.city}, {store.state} {store.postal_code}
          </p>
        </div>
        <button
          onClick={onAnalyze}
          disabled={isAnalyzing}
          className="mt-3 w-full bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
        >
          {isAnalyzing ? 'Analyzing...' : 'Analyze Trade Area'}
        </button>
        <a
          href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${store.latitude},${store.longitude}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 w-full flex items-center justify-center gap-1.5 bg-yellow-500 hover:bg-yellow-600 text-gray-900 text-xs font-medium py-2 px-3 rounded transition-colors"
        >
          Street View
        </a>
      </div>
    </Popup>
  );
}

// POI popup component
function POIPopup({
  poi,
  onClose,
}: {
  poi: {
    place_id: string;
    name: string;
    category: POICategory;
    latitude: number;
    longitude: number;
    address: string | null;
    rating: number | null;
  };
  onClose: () => void;
}) {
  return (
    <Popup
      longitude={poi.longitude}
      latitude={poi.latitude}
      anchor="bottom"
      onClose={onClose}
      closeButton={true}
      closeOnClick={false}
    >
      <div className="min-w-[180px] p-1">
        <div
          className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white"
          style={{ backgroundColor: POI_CATEGORY_COLORS[poi.category] }}
        >
          {POI_CATEGORY_LABELS[poi.category]}
        </div>
        <div className="text-sm">
          <p className="font-medium">{poi.name}</p>
          {poi.address && (
            <p className="text-gray-600 text-xs mt-1">{poi.address}</p>
          )}
          {poi.rating && (
            <p className="text-gray-500 text-xs mt-1">{poi.rating} ★</p>
          )}
        </div>
        <a
          href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${poi.latitude},${poi.longitude}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 w-full flex items-center justify-center gap-1 bg-yellow-500 hover:bg-yellow-600 text-gray-900 text-xs font-medium py-2 px-2 rounded transition-colors"
        >
          Street View
        </a>
      </div>
    </Popup>
  );
}

// Team property popup component
function TeamPropertyPopup({
  property,
  onClose,
}: {
  property: TeamProperty;
  onClose: () => void;
}) {
  return (
    <Popup
      longitude={property.longitude}
      latitude={property.latitude}
      anchor="bottom"
      onClose={onClose}
      closeButton={true}
      closeOnClick={false}
    >
      <div className="min-w-[220px] p-1">
        <div
          className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white flex items-center gap-1"
          style={{ backgroundColor: TEAM_PROPERTY_COLOR }}
        >
          <span>Team Flagged</span>
          {property.source_type && (
            <span className="opacity-75">
              • {TEAM_PROPERTY_SOURCE_LABELS[property.source_type]}
            </span>
          )}
        </div>
        <div className="text-sm">
          <p className="font-medium">{property.address}</p>
          <p className="text-gray-600">
            {property.city}, {property.state} {property.postal_code || ''}
          </p>
          {property.price && (
            <p className="text-green-700 font-medium mt-1">
              ${property.price.toLocaleString()}
            </p>
          )}
          {property.sqft && (
            <p className="text-gray-500 text-xs">
              {property.sqft.toLocaleString()} sqft
            </p>
          )}
          {property.notes && (
            <p className="text-gray-600 text-xs mt-2 italic border-t pt-2">
              "{property.notes}"
            </p>
          )}
          {property.contributor_name && (
            <p className="text-gray-400 text-xs mt-1">
              — {property.contributor_name}
            </p>
          )}
        </div>
        <div className="space-y-2 mt-2">
          {property.listing_url && (
            <a
              href={property.listing_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center bg-orange-600 hover:bg-orange-700 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
            >
              View Listing
            </a>
          )}
          <a
            href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${property.latitude},${property.longitude}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full text-center bg-yellow-500 hover:bg-yellow-600 text-gray-900 text-xs font-medium py-2 px-3 rounded transition-colors"
          >
            Street View
          </a>
        </div>
      </div>
    </Popup>
  );
}

// Activity Node heatmap layer - uses weight property from each POI for intensity
const activityHeatmapLayer: HeatmapLayerSpecification = {
  id: 'activity-heat',
  type: 'heatmap',
  source: 'activity-nodes',
  maxzoom: 16,
  paint: buildActivityNodeHeatmapPaint() as HeatmapLayerSpecification['paint'],
};

// Analysis radius circle layers
const radiusFillLayer: FillLayerSpecification = {
  id: 'analysis-radius-fill',
  type: 'fill',
  source: 'analysis-radius',
  paint: {
    'fill-color': '#E31837',
    'fill-opacity': 0.08,
  },
};

const radiusLineLayer: LineLayerSpecification = {
  id: 'analysis-radius-line',
  type: 'line',
  source: 'analysis-radius',
  paint: {
    'line-color': '#E31837',
    'line-width': 2,
    'line-opacity': 0.5,
  },
};

// Parcel boundary layers
const parcelFillLayer: FillLayerSpecification = {
  id: 'parcel-fill',
  type: 'fill',
  source: 'parcel-boundary',
  paint: {
    'fill-color': '#FEF3C7',
    'fill-opacity': 0.4,
  },
};

const parcelLineLayer: LineLayerSpecification = {
  id: 'parcel-line',
  type: 'line',
  source: 'parcel-boundary',
  paint: {
    'line-color': '#D97706',
    'line-width': 4,
    'line-opacity': 1,
  },
};

export function MapboxMap() {
  const mapRef = useRef<MapRef>(null);
  const [viewState, setViewState] = useState(INITIAL_VIEW);
  const [mapStyle, setMapStyle] = useState('mapbox://styles/mapbox/standard');
  
  // Isochrone state
  const [isochroneSettings, setIsochroneSettings] = useState<IsochroneSettings>({
    enabled: false,
    minutes: 10,
    mode: 'driving' as TravelMode,
    coordinates: null,
  });
  const [isochronePolygon, setIsochronePolygon] = useState<GeoJSON.Feature<GeoJSON.Polygon> | null>(null);
  const [isIsochroneLoading, setIsIsochroneLoading] = useState(false);
  const [isochroneError, setIsochroneError] = useState<string | null>(null);

  // Map store state
  const {
    selectedStore,
    setSelectedStore,
    visibleBrands,
    visibleStates,
    analysisResult,
    setAnalysisResult,
    setAnalyzedStore,
    isAnalyzing,
    setIsAnalyzing,
    setAnalysisError,
    visiblePOICategories,
    hiddenPOIs,
    setSelectedPOIId,
    setShowAnalysisPanel,
    analysisRadius,
    setMapInstance,
    visibleLayers,
    visiblePropertySources,
    visibleBoundaryTypes,
    visibleActivityNodeCategories,
    demographicMetric,
    // deck.gl 3D visualization state
    show3DVisualization,
    deckLayerVisibility,
    arcSettings,
    setArcSettings,
    competitorAccessResult,
    showCompetitorAccessPanel,
    setShowCompetitorAccessPanel,
    // Opportunity filters
    opportunityFilters,
    // Building layer state
    showBuildingLayer,
    // Draw-to-analyze
    drawnPolygon,
    setDrawnPolygon,
    isDrawMode,
    setIsDrawMode,
    // Measurement
    isMeasureMode,
    setIsMeasureMode,
    clearMeasurement,
    // Traffic Counts (Streetlight)
    trafficData,
  } = useMapStore();

  // Local state
  const [selectedPOI, setSelectedPOI] = useState<{
    place_id: string;
    name: string;
    category: POICategory;
    latitude: number;
    longitude: number;
    address: string | null;
    rating: number | null;
  } | null>(null);

  // Parcel info state
  const [selectedParcel, setSelectedParcel] = useState<ParcelInfo | null>(null);
  const [isLoadingParcel, setIsLoadingParcel] = useState(false);
  const [parcelError, setParcelError] = useState<string | null>(null);
  const [parcelClickPosition, setParcelClickPosition] = useState<{ lat: number; lng: number } | null>(null);

  // Map bounds for filtering
  const [mapBounds, setMapBounds] = useState<{
    north: number;
    south: number;
    east: number;
    west: number;
  } | null>(null);

  // Property search state (ATTOM)
  const [properties, setProperties] = useState<PropertyListing[]>([]);
  const [isLoadingProperties, setIsLoadingProperties] = useState(false);
  const [propertyError, setPropertyError] = useState<string | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);

  // Team properties state
  const [teamProperties, setTeamProperties] = useState<TeamProperty[]>([]);
  const [isLoadingTeamProperties, setIsLoadingTeamProperties] = useState(false);
  const [selectedTeamProperty, setSelectedTeamProperty] = useState<TeamProperty | null>(null);

  // Team property form state
  const [showTeamPropertyForm, setShowTeamPropertyForm] = useState(false);
  const [teamPropertyFormCoords, setTeamPropertyFormCoords] = useState<{ lat: number; lng: number } | null>(null);

  // CSOKi Opportunities state
  const [opportunities, setOpportunities] = useState<OpportunityRanking[]>([]);
  const [isLoadingOpportunities, setIsLoadingOpportunities] = useState(false);
  const [selectedOpportunity, setSelectedOpportunity] = useState<OpportunityRanking | null>(null);
  const opportunityClickedRef = useRef(false);

  // Traffic counts hover state
  const [hoveredTraffic, setHoveredTraffic] = useState<{
    longitude: number;
    latitude: number;
    aadt: number;
    route: string;
  } | null>(null);

  // StreetLight bubble hover state
  const [hoveredStreetlightSegment, setHoveredStreetlightSegment] = useState<{
    longitude: number;
    latitude: number;
    trips_volume: number;
    avg_speed: number;
    vmt: number;
    segment_id: string;
    rank?: number;
  } | null>(null);

  // Census Tracts hover state (now using vector tileset)
  const [hoveredTractId, setHoveredTractId] = useState<string | number | null>(null);
  const [hoveredTractInfo, setHoveredTractInfo] = useState<{
    name: string;
    population: number;
    income: number;
    density: number;
    lngLat: [number, number];
  } | null>(null);

  // County hover state (now using vector tileset with data-driven styling)
  const [hoveredCountyId, setHoveredCountyId] = useState<string | number | null>(null);
  const [hoveredCountyInfo, setHoveredCountyInfo] = useState<{
    name: string;
    population: number;
    income: number;
    density: number;
    lngLat: [number, number];
  } | null>(null);

  // City hover state (for tileset-based boundaries)
  const [hoveredCityId, setHoveredCityId] = useState<string | null>(null);
  const [hoveredCityInfo, setHoveredCityInfo] = useState<{
    name: string;
    population: number;
    lngLat: [number, number];
  } | null>(null);

  // ZIP Code hover state (for tileset-based boundaries)
  const [hoveredZipId, setHoveredZipId] = useState<string | null>(null);
  const [hoveredZipInfo, setHoveredZipInfo] = useState<{
    zipCode: string;
    population: number;
    lngLat: [number, number];
  } | null>(null);

  // Track analysis center for re-analysis
  const analysisCenterRef = useRef<{ lat: number; lng: number } | null>(null);

  // Fetch stores data
  const { data: storeData, isLoading } = useStores({ limit: 5000 });

  // Convert Sets to Arrays
  const visibleBrandsArray = useMemo(() => Array.from(visibleBrands), [visibleBrands]);
  const visibleStatesArray = useMemo(() => Array.from(visibleStates), [visibleStates]);
  const visiblePOICategoriesArray = useMemo(() => Array.from(visiblePOICategories), [visiblePOICategories]);
  const visibleLayersArray = useMemo(() => Array.from(visibleLayers), [visibleLayers]);

  // Filter stores
  const visibleStores = useMemo(() => {
    if (!storeData?.stores) return [];
    return storeData.stores.filter(
      (store) =>
        store.latitude != null &&
        store.longitude != null &&
        store.state != null &&
        visibleBrandsArray.includes(store.brand as BrandKey) &&
        visibleStatesArray.includes(store.state)
    );
  }, [storeData?.stores, visibleBrandsArray, visibleStatesArray]);

  // Filter POIs (by category and individual visibility)
  const hiddenPOIsArray = useMemo(() => Array.from(hiddenPOIs), [hiddenPOIs]);
  const visiblePOIs = useMemo(() => {
    if (!analysisResult?.pois) return [];
    const filtered = analysisResult.pois.filter((poi) =>
      visiblePOICategoriesArray.includes(poi.category) && !hiddenPOIsArray.includes(poi.place_id)
    );
    return filtered.slice(0, 100);
  }, [analysisResult?.pois, visiblePOICategoriesArray, hiddenPOIsArray]);

  // POI Clustering - group nearby POIs when zoomed out
  const POI_CLUSTER_ZOOM_THRESHOLD = 14; // Show clusters below this zoom
  const poiClusters = useMemo(() => {
    if (viewState.zoom >= POI_CLUSTER_ZOOM_THRESHOLD || visiblePOIs.length === 0) {
      return []; // Show individual markers at high zoom
    }

    // Simple grid-based clustering
    const gridSize = 0.01 * Math.pow(2, 14 - viewState.zoom); // Adjust grid size based on zoom
    const clusters: Record<string, { lat: number; lng: number; pois: typeof visiblePOIs }> = {};

    visiblePOIs.forEach((poi) => {
      const gridX = Math.floor(poi.longitude / gridSize);
      const gridY = Math.floor(poi.latitude / gridSize);
      const key = `${gridX},${gridY}`;

      if (!clusters[key]) {
        clusters[key] = { lat: poi.latitude, lng: poi.longitude, pois: [] };
      }
      clusters[key].pois.push(poi);
    });

    // Convert to array and calculate cluster centers
    return Object.values(clusters).map((cluster) => {
      const avgLat = cluster.pois.reduce((sum, p) => sum + p.latitude, 0) / cluster.pois.length;
      const avgLng = cluster.pois.reduce((sum, p) => sum + p.longitude, 0) / cluster.pois.length;
      return {
        id: `cluster-${avgLat.toFixed(4)}-${avgLng.toFixed(4)}`,
        latitude: avgLat,
        longitude: avgLng,
        count: cluster.pois.length,
        pois: cluster.pois,
      };
    });
  }, [visiblePOIs, viewState.zoom]);

  // Determine if we should show clusters or individual POIs
  const showPOIClusters = viewState.zoom < POI_CLUSTER_ZOOM_THRESHOLD && poiClusters.length > 0;

  // Stores in view for stats
  const storesInView = useMemo(() => {
    if (!mapBounds) return visibleStores;
    return visibleStores.filter((store) => {
      if (!store.latitude || !store.longitude) return false;
      return (
        store.latitude >= mapBounds.south &&
        store.latitude <= mapBounds.north &&
        store.longitude >= mapBounds.west &&
        store.longitude <= mapBounds.east
      );
    });
  }, [visibleStores, mapBounds]);

  // ============================================
  // Activity Node Heat Map data
  // ============================================
  const [activityNodes, setActivityNodes] = useState<ActivityNode[]>([]);
  const [, setIsLoadingActivityNodes] = useState(false);

  // Fetch activity nodes when layer is visible and viewport changes
  useEffect(() => {
    const showActivityHeat = visibleLayersArray.includes('activity_heat');

    if (showActivityHeat && mapBounds) {
      const debounceTimer = setTimeout(async () => {
        setIsLoadingActivityNodes(true);
        try {
          const result = await activityNodesApi.getInBounds({
            min_lat: mapBounds.south,
            max_lat: mapBounds.north,
            min_lng: mapBounds.west,
            max_lng: mapBounds.east,
          });
          setActivityNodes(result.nodes);
        } catch (error) {
          console.error('[Activity Nodes] Error fetching:', error);
          setActivityNodes([]);
        } finally {
          setIsLoadingActivityNodes(false);
        }
      }, 500);
      return () => clearTimeout(debounceTimer);
    } else if (!showActivityHeat) {
      setActivityNodes([]);
    }
  }, [visibleLayersArray, mapBounds]);

  // GeoJSON for activity node heatmap — client-side filtered by visible categories
  const activityNodesGeoJSON = useMemo(() => {
    const filtered = activityNodes.filter((node) =>
      visibleActivityNodeCategories.has(node.node_category)
    );
    return {
      type: 'FeatureCollection' as const,
      features: filtered.map((node) => ({
        type: 'Feature' as const,
        properties: {
          id: node.id,
          node_category: node.node_category,
          weight: node.weight,
          name: node.name,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [node.longitude, node.latitude],
        },
      })),
    };
  }, [activityNodes, visibleActivityNodeCategories]);

  // GeoJSON for clustered properties
  const propertiesGeoJSON = useMemo(() => {
    return {
      type: 'FeatureCollection' as const,
      features: properties.map((property) => ({
        type: 'Feature' as const,
        properties: {
          id: property.id,
          property_type: property.property_type,
          listing_type: property.listing_type,
          price: property.price,
          address: property.address,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [property.longitude, property.latitude],
        },
      })),
    };
  }, [properties]);

  // GeoJSON for analysis radius circle (using Turf.js)
  const radiusGeoJSON = useMemo(() => {
    if (!analysisResult) return null;
    return turf.circle(
      [analysisResult.center_longitude, analysisResult.center_latitude],
      analysisRadius,
      { units: 'miles' }
    );
  }, [analysisResult, analysisRadius]);

  // GeoJSON for parcel boundary
  const parcelGeoJSON = useMemo(() => {
    if (!selectedParcel?.geometry) return null;
    const geometry = parseWKTToGeoJSON(selectedParcel.geometry);
    if (!geometry) return null;
    return {
      type: 'Feature' as const,
      properties: {},
      geometry,
    };
  }, [selectedParcel]);

  // GeoJSON for competitor route lines
  const competitorRoutesGeoJSON = useMemo((): GeoJSON.FeatureCollection | null => {
    if (!arcSettings.siteLocation || !competitorAccessResult?.competitors?.length) return null;

    const [siteLng, siteLat] = arcSettings.siteLocation;
    const features: GeoJSON.Feature[] = competitorAccessResult.competitors.map((competitor: any) => ({
      type: 'Feature' as const,
      properties: {
        brand: competitor.brand,
        travelTime: competitor.travel_time_minutes,
        distance: competitor.distance_miles,
      },
      geometry: {
        type: 'LineString' as const,
        coordinates: [
          [siteLng, siteLat],
          [competitor.longitude, competitor.latitude],
        ],
      },
    }));

    return {
      type: 'FeatureCollection' as const,
      features,
    };
  }, [arcSettings.siteLocation, competitorAccessResult]);

  // GeoJSON for StreetLight traffic bubbles at segment midpoints (analysis-triggered)
  const streetlightSegmentsGeoJSON = useMemo((): GeoJSON.FeatureCollection | null => {
    if (!trafficData?.segments?.length) return null;

    const valid = trafficData.segments
      .filter((seg) => seg.geometry !== null && seg.geometry.type === 'LineString')
      .sort((a, b) => (b.trips_volume ?? 0) - (a.trips_volume ?? 0)); // Rank by volume

    if (valid.length === 0) return null;

    const features: GeoJSON.Feature[] = valid.map((seg, i) => {
      // Compute midpoint of the LineString (middle vertex)
      const coords = seg.geometry!.coordinates;
      const mid = coords[Math.floor(coords.length / 2)];
      const vol = seg.trips_volume ?? 0;

      return {
        type: 'Feature' as const,
        properties: {
          segment_id: seg.segment_id,
          trips_volume: vol,
          avg_speed: seg.avg_speed ?? 0,
          vmt: seg.vmt ?? 0,
          rank: i + 1,
          adt_label: vol >= 1000
            ? `${(vol / 1000).toFixed(1).replace(/\.0$/, '')}K`
            : String(vol),
        },
        geometry: {
          type: 'Point' as const,
          coordinates: mid,
        },
      };
    });

    return {
      type: 'FeatureCollection' as const,
      features,
    };
  }, [trafficData]);

  // Run trade area analysis
  const runAnalysis = useCallback(async (lat: number, lng: number, radius: number) => {
    setSelectedStore(null);
    setSelectedPOI(null);
    setIsAnalyzing(true);
    setAnalysisError(null);
    setShowAnalysisPanel(true);

    try {
      const result = await analysisApi.analyzeTradeArea({
        latitude: lat,
        longitude: lng,
        radius_miles: radius,
      });
      setAnalysisResult(result);
      analysisCenterRef.current = { lat, lng };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to analyze area';
      setAnalysisError(message);
    } finally {
      setIsAnalyzing(false);
    }
  }, [setSelectedStore, setAnalysisResult, setIsAnalyzing, setAnalysisError, setShowAnalysisPanel]);

  // Handle analyze button
  const handleAnalyzeArea = useCallback(() => {
    if (!selectedStore?.latitude || !selectedStore?.longitude) return;
    setAnalyzedStore(selectedStore);
    runAnalysis(selectedStore.latitude, selectedStore.longitude, analysisRadius);
  }, [selectedStore, analysisRadius, runAnalysis, setAnalyzedStore]);

  // Handle drawn polygon analysis
  const runPolygonAnalysis = useCallback(async (polygon: GeoJSON.Feature) => {
    setDrawnPolygon(polygon);
    setSelectedStore(null);
    setIsAnalyzing(true);
    setAnalysisError(null);
    setShowAnalysisPanel(true);
    setAnalyzedStore(null);

    try {
      const centroid = turf.centroid(polygon as turf.AllGeoJSON);
      const [lng, lat] = centroid.geometry.coordinates;
      const areaM2 = turf.area(polygon as turf.AllGeoJSON);
      // Equivalent radius in miles (circle with same area)
      const equivalentRadiusMiles = Math.sqrt(areaM2 / Math.PI) / 1609.34;
      // Fetch slightly larger radius to ensure we get all edge POIs
      const fetchRadius = Math.max(equivalentRadiusMiles * 1.3, 0.5);

      analysisCenterRef.current = { lat, lng };

      const result = await analysisApi.analyzeTradeArea({
        latitude: lat,
        longitude: lng,
        radius_miles: fetchRadius,
      });

      // Filter POIs to only those inside the drawn polygon
      const filteredPois = result.pois.filter((poi) => {
        const pt = turf.point([poi.longitude, poi.latitude]);
        return turf.booleanPointInPolygon(pt, polygon as GeoJSON.Feature<GeoJSON.Polygon>);
      });

      // Recompute summary counts
      const summary: Record<string, number> = {};
      for (const poi of filteredPois) {
        summary[poi.category] = (summary[poi.category] || 0) + 1;
      }

      setAnalysisResult({
        ...result,
        pois: filteredPois,
        summary,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to analyze area';
      setAnalysisError(message);
    } finally {
      setIsAnalyzing(false);
    }
  }, [setSelectedStore, setAnalysisResult, setIsAnalyzing, setAnalysisError, setShowAnalysisPanel, setAnalyzedStore, setDrawnPolygon]);

  // Auto-refresh analysis when radius changes
  useEffect(() => {
    if (analysisCenterRef.current && analysisResult) {
      runAnalysis(analysisCenterRef.current.lat, analysisCenterRef.current.lng, analysisRadius);
    }
  }, [analysisRadius]);

  // Handle map click
  const handleMapClick = useCallback(async (e: mapboxgl.MapMouseEvent) => {
    // Skip if an opportunity marker was just clicked (ref set by PulsingOpportunityMarker)
    if (opportunityClickedRef.current) {
      opportunityClickedRef.current = false;
      return;
    }

    // Measurement mode intercept — read directly from store to avoid stale closures
    // (@vis.gl/react-mapbox may not re-register the onClick handler on every render)
    const storeState = useMapStore.getState();
    if (storeState.isMeasureMode && e.lngLat) {
      storeState.addMeasurePoint([e.lngLat.lng, e.lngLat.lat]);
      return;
    }

    const map = mapRef.current?.getMap();

    // Check if click was on a cluster (only if layer exists)
    if (map && map.getLayer('clusters')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['clusters']
      });
      
      if (features.length > 0) {
        const clusterId = features[0].properties?.cluster_id;
        const source = map.getSource('properties') as mapboxgl.GeoJSONSource;
        
        if (source && clusterId !== undefined) {
          source.getClusterExpansionZoom(clusterId, (err, zoom) => {
            if (err || !features[0].geometry || features[0].geometry.type !== 'Point') return;
            
            const coordinates = features[0].geometry.coordinates as [number, number];
            map.easeTo({
              center: coordinates,
              zoom: zoom || viewState.zoom + 2,
              duration: 500,
            });
          });
        }
        return; // Don't process other click logic
      }
    }
    
    setSelectedStore(null);
    setSelectedPOI(null);
    setSelectedProperty(null);
    setSelectedTeamProperty(null);
    setSelectedOpportunity(null);

    // Get click coordinates
    if (!e.lngLat) return;
    const lat = e.lngLat.lat;
    const lng = e.lngLat.lng;

    // Set analysis pin location for competitor access & isochrone
    setArcSettings({ siteLocation: [lng, lat] });

    // Update isochrone center if drive time is enabled
    if (isochroneSettings.enabled) {
      setIsochroneSettings({
        ...isochroneSettings,
        coordinates: [lng, lat],
      });
    }

    // Show competitor access panel
    setShowCompetitorAccessPanel(true);

    const isParcelLayerVisible = visibleLayersArray.includes('parcels');
    const currentZoom = viewState.zoom;

    if (isParcelLayerVisible && currentZoom >= 14) {
      setParcelClickPosition({ lat, lng });
      setIsLoadingParcel(true);
      setParcelError(null);
      setSelectedParcel(null);

      try {
        const parcelInfo = await analysisApi.getParcelInfo({
          latitude: lat,
          longitude: lng,
        });
        setSelectedParcel(parcelInfo);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load parcel info';
        setParcelError(message);
        setSelectedParcel(null);
      } finally {
        setIsLoadingParcel(false);
      }
    } else {
      setSelectedParcel(null);
      setParcelError(null);
      setParcelClickPosition(null);
    }
  }, [setSelectedStore, visibleLayersArray, viewState.zoom, isochroneSettings, setArcSettings, setShowCompetitorAccessPanel]);

  // Handle double-click to complete measurement
  const handleMapDblClick = useCallback((e: mapboxgl.MapMouseEvent) => {
    // Read directly from store to avoid stale closures
    const storeState = useMapStore.getState();
    if (!storeState.isMeasureMode) return;
    e.preventDefault();
    // The dblclick is preceded by two click events that each added a point.
    // Remove the last duplicate point from the second click of the double-click.
    const correctedPoints = storeState.measurePoints.slice(0, -1);
    useMapStore.setState({
      measurePoints: correctedPoints,
      isMeasurementComplete: true,
      isMeasureMode: false,
    });
  }, []);

  // Crosshair cursor when measurement mode is active
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    map.getCanvas().style.cursor = isMeasureMode ? 'crosshair' : '';
  }, [isMeasureMode]);

  // Handle right-click for flagging property
  const handleMapRightClick = useCallback((e: mapboxgl.MapMouseEvent) => {
    if (e.lngLat) {
      setTeamPropertyFormCoords({
        lat: e.lngLat.lat,
        lng: e.lngLat.lng,
      });
      setShowTeamPropertyForm(true);
    }
  }, []);

  // On map load
  const onLoad = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (map) {
      setMapInstance(map);

      // Globe atmosphere
      map.setFog({
        color: 'rgb(186, 210, 235)',
        'high-color': 'rgb(36, 92, 223)',
        'horizon-blend': 0.02,
        'space-color': 'rgb(11, 11, 25)',
        'star-intensity': 0.6,
      });

      // Change cursor on cluster hover (only add if layer exists)
      const addClusterHoverEffects = () => {
        if (map.getLayer('clusters')) {
          map.on('mouseenter', 'clusters', () => {
            map.getCanvas().style.cursor = 'pointer';
          });
          map.on('mouseleave', 'clusters', () => {
            map.getCanvas().style.cursor = '';
          });
        }
      };
      
      // Try to add immediately, or wait for style to load
      if (map.isStyleLoaded()) {
        addClusterHoverEffects();
      } else {
        map.once('styledata', addClusterHoverEffects);
      }
    }
  }, [setMapInstance]);

  // Re-apply fog after map style changes (setFog resets on style load)
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const applyFog = () => {
      map.setFog({
        color: 'rgb(186, 210, 235)',
        'high-color': 'rgb(36, 92, 223)',
        'horizon-blend': 0.02,
        'space-color': 'rgb(11, 11, 25)',
        'star-intensity': 0.6,
      });
    };
    if (map.isStyleLoaded()) {
      applyFog();
    } else {
      map.once('style.load', applyFog);
    }
  }, [mapStyle]);

  // Update bounds on move
  const onMoveEnd = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    const bounds = map.getBounds();
    if (bounds) {
      setMapBounds({
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest(),
      });
    }
  }, []);

  // Handle traffic counts layer hover
  const handleTrafficMouseMove = useCallback((e: mapboxgl.MapMouseEvent) => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    // Handle StreetLight traffic bubbles (takes priority)
    if (map.getLayer('streetlight-bubbles')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['streetlight-bubbles'],
      });

      if (features && features.length > 0) {
        const feature = features[0];
        map.getCanvas().style.cursor = 'pointer';
        setHoveredStreetlightSegment({
          longitude: e.lngLat.lng,
          latitude: e.lngLat.lat,
          trips_volume: feature.properties?.trips_volume || 0,
          avg_speed: feature.properties?.avg_speed || 0,
          vmt: feature.properties?.vmt || 0,
          segment_id: feature.properties?.segment_id || '',
          rank: feature.properties?.rank || undefined,
        });
        return;
      } else {
        setHoveredStreetlightSegment(null);
      }
    }

    // Handle traffic counts layer
    if (map.getLayer('traffic-counts-layer')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['traffic-counts-layer'],
      });

      if (features && features.length > 0) {
        const feature = features[0];
        map.getCanvas().style.cursor = 'pointer';
        setHoveredTraffic({
          longitude: e.lngLat.lng,
          latitude: e.lngLat.lat,
          aadt: feature.properties?.aadt || 0,
          route: feature.properties?.route || 'Unknown',
        });
        return; // Early return if traffic feature found
      } else {
        setHoveredTraffic(null);
      }
    }

    // Handle census tract layer
    if (map.getLayer('census-tract-fill')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['census-tract-fill'],
      });

      if (features && features.length > 0) {
        const feature = features[0];
        map.getCanvas().style.cursor = 'pointer';
        setHoveredTractId(feature.properties?.GEOID || null);
        setHoveredTractInfo({
          name: feature.properties?.NAME || 'Unknown Tract',
          population: feature.properties?.POPULATION || 0,
          income: feature.properties?.MEDIAN_INCOME || 0,
          density: feature.properties?.POP_DENSITY || 0,
          lngLat: [e.lngLat.lng, e.lngLat.lat],
        });
        return;
      } else {
        setHoveredTractId(null);
        setHoveredTractInfo(null);
      }
    }

    // Handle county demographics layer
    if (map.getLayer('county-demographics-fill')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['county-demographics-fill'],
      });

      if (features && features.length > 0) {
        const feature = features[0];
        map.getCanvas().style.cursor = 'pointer';
        setHoveredCountyId(feature.properties?.GEOID || null);
        setHoveredCountyInfo({
          name: feature.properties?.NAME || 'Unknown County',
          population: feature.properties?.POPULATION || 0,
          income: feature.properties?.MEDIAN_INCOME || 0,
          density: feature.properties?.POP_DENSITY || 0,
          lngLat: [e.lngLat.lng, e.lngLat.lat],
        });
        return;
      } else {
        setHoveredCountyId(null);
        setHoveredCountyInfo(null);
      }
    }

    // Handle city boundaries layer (tileset)
    if (map.getLayer('city-boundaries-fill')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['city-boundaries-fill'],
      });

      if (features && features.length > 0) {
        const feature = features[0];
        map.getCanvas().style.cursor = 'pointer';

        // Set ID for layer highlighting (use NAME as unique identifier)
        const cityId = feature.properties?.NAME || feature.properties?.BASENAME || null;
        setHoveredCityId(cityId);

        setHoveredCityInfo({
          name: cityId || 'Unknown City',
          population: feature.properties?.POPULATION || feature.properties?.POP100 || 0,
          lngLat: [e.lngLat.lng, e.lngLat.lat],
        });
        return;
      } else {
        setHoveredCityId(null);
        setHoveredCityInfo(null);
      }
    }

    // Handle ZIP code boundaries layer (tileset)
    if (map.getLayer('zipcode-boundaries-fill')) {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['zipcode-boundaries-fill'],
      });

      if (features && features.length > 0) {
        const feature = features[0];
        map.getCanvas().style.cursor = 'pointer';

        // Use ZCTA5CE20 or GEOID20 for unique ID (these are the ZIP code itself)
        const zipCode = feature.properties?.ZCTA5CE20 || feature.properties?.GEOID20 || feature.properties?.NAME || 'Unknown';
        setHoveredZipId(zipCode);

        setHoveredZipInfo({
          zipCode,
          population: feature.properties?.POPULATION || feature.properties?.POP100 || feature.properties?.DP0010001 || 0,
          lngLat: [e.lngLat.lng, e.lngLat.lat],
        });
        return;
      } else {
        setHoveredZipId(null);
        setHoveredZipInfo(null);
      }
    }

    map.getCanvas().style.cursor = '';
  }, []);

  const handleTrafficMouseLeave = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (map) {
      map.getCanvas().style.cursor = '';
    }
    setHoveredTractId(null);
    setHoveredTractInfo(null);
    setHoveredCountyId(null);
    setHoveredCountyInfo(null);
    setHoveredCityId(null);
    setHoveredCityInfo(null);
    setHoveredZipId(null);
    setHoveredZipInfo(null);
    setHoveredTraffic(null);
    setHoveredStreetlightSegment(null);
  }, []);

  // Property search when layer is toggled
  useEffect(() => {
    const showProperties = visibleLayersArray.includes('properties_for_sale');

    if (showProperties && mapBounds) {
      const searchProperties = async () => {
        setIsLoadingProperties(true);
        setPropertyError(null);

        try {
          const result = await analysisApi.searchPropertiesByBounds({
            min_lat: mapBounds.south,
            max_lat: mapBounds.north,
            min_lng: mapBounds.west,
            max_lng: mapBounds.east,
            limit: 50,
          });
          setProperties(result.properties || []);
        } catch (error: any) {
          console.error('[PropertySearch] Error:', error);
          setPropertyError(error.response?.data?.detail || 'Failed to search properties');
          setProperties([]);
        } finally {
          setIsLoadingProperties(false);
        }
      };

      searchProperties();
    } else if (!showProperties) {
      setProperties([]);
      setSelectedProperty(null);
      setPropertyError(null);
    }
  }, [visibleLayersArray.includes('properties_for_sale'), mapBounds]);

  // Team properties when layer is enabled
  useEffect(() => {
    const showProperties = visibleLayersArray.includes('properties_for_sale');

    if (showProperties && mapBounds) {
      const loadTeamProperties = async () => {
        setIsLoadingTeamProperties(true);
        try {
          const result = await teamPropertiesApi.getInBounds({
            min_lat: mapBounds.south,
            max_lat: mapBounds.north,
            min_lng: mapBounds.west,
            max_lng: mapBounds.east,
            status: 'active',
          });
          setTeamProperties(result.properties || []);
        } catch (error: any) {
          console.error('[TeamProperties] Error loading:', error);
          setTeamProperties([]);
        } finally {
          setIsLoadingTeamProperties(false);
        }
      };

      loadTeamProperties();
    } else if (!showProperties) {
      setTeamProperties([]);
      setSelectedTeamProperty(null);
    }
  }, [visibleLayersArray.includes('properties_for_sale'), mapBounds]);

  // CSOKi Opportunities when layer is toggled or filters change
  // Debounced to avoid burning ATTOM API calls on every pan/zoom
  useEffect(() => {
    const showOpportunities = visibleLayersArray.includes('csoki_opportunities');

    if (showOpportunities && mapBounds) {
      const debounceTimer = setTimeout(async () => {
        setIsLoadingOpportunities(true);
        try {
          const result = await opportunitiesApi.search({
            min_lat: mapBounds.south,
            max_lat: mapBounds.north,
            min_lng: mapBounds.west,
            max_lng: mapBounds.east,
            min_parcel_acres: opportunityFilters.minParcelAcres,
            max_parcel_acres: opportunityFilters.maxParcelAcres,
            min_building_sqft: opportunityFilters.minBuildingSqft,
            max_building_sqft: opportunityFilters.maxBuildingSqft,
            include_retail: opportunityFilters.includeRetail,
            include_office: opportunityFilters.includeOffice,
            include_land: opportunityFilters.includeLand,
            limit: 100,
          });
          setOpportunities(result.opportunities || []);
        } catch (error: any) {
          console.error('[CSOKi Opportunities] Error fetching:', error);
          setOpportunities([]);
        } finally {
          setIsLoadingOpportunities(false);
        }
      }, 800);  // Wait 800ms after last bounds change before fetching

      return () => clearTimeout(debounceTimer);
    } else if (!showOpportunities) {
      setOpportunities([]);
      setSelectedOpportunity(null);
    }
  }, [visibleLayersArray, mapBounds, opportunityFilters]);

  // Handle team property form success
  const handleTeamPropertySuccess = useCallback(() => {
    if (mapBounds && visibleLayersArray.includes('properties_for_sale')) {
      teamPropertiesApi.getInBounds({
        min_lat: mapBounds.south,
        max_lat: mapBounds.north,
        min_lng: mapBounds.west,
        max_lng: mapBounds.east,
        status: 'active',
      }).then(result => {
        setTeamProperties(result.properties || []);
      }).catch(console.error);
    }
  }, [mapBounds, visibleLayersArray]);

  // Auto-set isochrone coordinates when Drive Time is enabled and there's a site location
  useEffect(() => {
    if (isochroneSettings.enabled && !isochroneSettings.coordinates && arcSettings.siteLocation) {
      setIsochroneSettings({
        ...isochroneSettings,
        coordinates: arcSettings.siteLocation,
      });
    }
  }, [isochroneSettings.enabled, arcSettings.siteLocation]);

  // Fetch isochrone when settings change or coordinates update
  useEffect(() => {
    if (isochroneSettings.enabled && isochroneSettings.coordinates && MAPBOX_TOKEN) {
      setIsIsochroneLoading(true);
      setIsochroneError(null);

      fetchIsochrone(
        {
          coordinates: isochroneSettings.coordinates,
          minutes: isochroneSettings.minutes,
          mode: isochroneSettings.mode,
        },
        MAPBOX_TOKEN
      ).then((polygon) => {
        setIsochronePolygon(polygon);
        if (!polygon) {
          setIsochroneError('Could not calculate travel area for this location.');
        }
      }).catch((error) => {
        console.error('Failed to fetch isochrone:', error);
        setIsochronePolygon(null);
        setIsochroneError(error instanceof Error ? error.message : 'Failed to calculate travel area.');
      }).finally(() => {
        setIsIsochroneLoading(false);
      });
    } else {
      setIsochronePolygon(null);
      setIsochroneError(null);
    }
  }, [isochroneSettings]);

  // deck.gl overlay reference
  const deckOverlayRef = useRef<MapboxOverlay | null>(null);

  // Manage deck.gl 3D visualization layers
  useEffect(() => {
    if (!mapRef.current) return;

    const map = mapRef.current.getMap();
    if (!map) return;

    // Remove existing overlay if present
    if (deckOverlayRef.current) {
      try {
        map.removeControl(deckOverlayRef.current);
      } catch (e) {
        // Overlay may not be attached
      }
      deckOverlayRef.current = null;
    }

    // Only create overlay if 3D visualization is enabled
    if (!show3DVisualization) return;

    const layers: any[] = [];

    // Add competitor arc layer if enabled and we have analysis data
    if (deckLayerVisibility.competitorArcs && arcSettings.siteLocation && competitorAccessResult?.competitors) {
      layers.push(
        createCompetitorArcLayer({
          siteLocation: arcSettings.siteLocation,
          competitors: competitorAccessResult.competitors,
          visible: true,
          highlightedCompetitorId: arcSettings.highlightedCompetitorId,
        })
      );
    }

    // Create and add overlay if we have layers
    if (layers.length > 0) {
      const overlay = new MapboxOverlay({
        layers,
        interleaved: true,
      });
      map.addControl(overlay);
      deckOverlayRef.current = overlay;
    }

    // Cleanup on unmount
    return () => {
      if (deckOverlayRef.current && map) {
        try {
          map.removeControl(deckOverlayRef.current);
        } catch (e) {
          // Map may be unmounted
        }
        deckOverlayRef.current = null;
      }
    };
  }, [
    show3DVisualization,
    deckLayerVisibility,
    properties,
    arcSettings,
    competitorAccessResult,
  ]);

  // Census tracts now use Mapbox vector tileset - no dynamic fetch needed

  // County demographics now use Mapbox vector tileset with data-driven styling - no dynamic fetch needed

  // Check for token
  if (!MAPBOX_TOKEN) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100">
        <div className="text-center p-8 bg-white rounded-lg shadow-lg max-w-md">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Mapbox Token Required</h2>
          <p className="text-gray-600 mb-4">
            To use the map, add your access token to the environment:
          </p>
          <code className="block bg-gray-100 p-3 rounded text-sm text-left">
            VITE_MAPBOX_TOKEN=pk.your_token_here
          </code>
          <p className="text-sm text-gray-500 mt-4">
            Get a free token at{' '}
            <a
              href="https://account.mapbox.com/access-tokens/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              mapbox.com
            </a>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Loading indicator */}
      {isLoading && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-white px-4 py-2 rounded-lg shadow-md">
          Loading stores...
        </div>
      )}

      {/* Quick Stats Bar */}
      <QuickStatsBar stores={storesInView} />

      {/* Legends */}
      <FEMALegend isVisible={visibleLayersArray.includes('fema_flood')} />
      <HeatMapLegend isVisible={visibleLayersArray.includes('activity_heat')} />
      <ParcelLegend isVisible={visibleLayersArray.includes('parcels')} />
      <ZoningLegend isVisible={visibleLayersArray.includes('zoning')} />
      <TrafficCountsLegend isVisible={visibleLayersArray.includes('traffic_counts')} />
      <PropertyLegend
        isVisible={visibleLayersArray.includes('properties_for_sale')}
        propertyCount={properties.length}
        isLoading={isLoadingProperties}
        error={propertyError}
      />

      {/* Map Style Switcher */}
      <MapStyleSwitcher 
        currentStyle={mapStyle}
        onStyleChange={setMapStyle}
      />

      {/* Isochrone Control */}
      <IsochroneControl
        settings={isochroneSettings}
        onSettingsChange={setIsochroneSettings}
        isLoading={isIsochroneLoading}
        error={isochroneError}
        onClearError={() => setIsochroneError(null)}
        onShowCompetitorAccess={() => {
          if (isochroneSettings.coordinates) {
            setArcSettings({ siteLocation: isochroneSettings.coordinates });
            setShowCompetitorAccessPanel(true);
          }
        }}
      />

      {/* Property loading indicator */}
      {isLoadingProperties && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 bg-purple-600 text-white px-4 py-2 rounded-lg shadow-md text-sm flex items-center gap-2">
          <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
          Searching properties...
        </div>
      )}

      {/* Note: All boundaries now load from Mapbox tilesets - no loading indicator needed */}

      {/* Property error display */}
      {propertyError && visibleLayersArray.includes('properties_for_sale') && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 bg-red-600 text-white px-4 py-2 rounded-lg shadow-md text-sm">
          {propertyError}
        </div>
      )}

      {/* Isolation wrapper: contains marker z-indices (up to 2000) so they don't
           paint above sibling panels like PropertyInfoCard and DraggableParcelInfo */}
      <div style={{ isolation: 'isolate', width: '100%', height: '100%' }}>
      <Map
        ref={mapRef}
        {...viewState}
        projection="globe"
        preserveDrawingBuffer={true}
        onMove={(evt: ViewStateChangeEvent) => setViewState(evt.viewState)}
        onMoveEnd={onMoveEnd}
        onLoad={onLoad}
        onClick={handleMapClick}
        onDblClick={handleMapDblClick}
        doubleClickZoom={!isMeasureMode}
        onContextMenu={handleMapRightClick}
        onMouseMove={handleTrafficMouseMove}
        onMouseLeave={handleTrafficMouseLeave}
        interactiveLayerIds={[
          ...(streetlightSegmentsGeoJSON ? ['streetlight-bubbles'] : []),
          ...(visibleLayersArray.includes('traffic_counts') ? ['traffic-counts-layer'] : []),
          ...(visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('census_tracts') ? ['census-tract-fill'] : []),
          ...(visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('counties') ? ['county-demographics-fill'] : []),
          ...(visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('cities') ? ['city-boundaries-fill'] : []),
          ...(visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('zipcodes') ? ['zipcode-boundaries-fill'] : []),
        ]}
        style={{ width: '100%', height: '100%' }}
        mapStyle={mapStyle}
        mapboxAccessToken={MAPBOX_TOKEN}
      >
        {/* Navigation controls */}
        <NavigationControl map={mapRef.current} position="top-right" />
        <ScaleControl position="bottom-right" />
        <GeolocateControl map={mapRef.current} position="top-right" />
        <ScreenshotControl map={mapRef.current} />
        <DrawControl
          map={mapRef.current}
          isDrawMode={isDrawMode}
          onDrawModeChange={(active) => {
            setIsDrawMode(active);
            if (active) { clearMeasurement(); setIsMeasureMode(false); }
          }}
          onPolygonCreated={runPolygonAnalysis}
          onPolygonCleared={() => {
            setDrawnPolygon(null);
            setIsDrawMode(false);
          }}
          hasPolygon={!!drawnPolygon}
        />
        <MeasurementControl />
        <MeasurementLayer />

        {/* Traffic Layer */}
        {visibleLayersArray.includes('traffic') && (
          <Source
            id="mapbox-traffic"
            type="vector"
            url="mapbox://mapbox.mapbox-traffic-v1"
          >
            <Layer
              id="traffic-layer"
              type="line"
              source-layer="traffic"
              paint={{
                'line-width': 2,
                'line-color': [
                  'match',
                  ['get', 'congestion'],
                  'low', '#00ff00',
                  'moderate', '#ffff00',
                  'heavy', '#ff8800',
                  'severe', '#ff0000',
                  '#666666'
                ],
                'line-opacity': 0.7,
              }}
            />
          </Source>
        )}

        {/* Iowa Traffic Counts (AADT) Layer */}
        {visibleLayersArray.includes('traffic_counts') && (
          <Source
            id="ia-traffic-counts"
            type="vector"
            url="mapbox://msrodtn.ia-traffic"
          >
            <Layer
              id="traffic-counts-layer"
              type="line"
              source-layer="traffic"
              minzoom={8}
              paint={{
                'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 14, 4],
                'line-color': [
                  'step',
                  ['get', 'aadt'],
                  '#3B82F6',      // 0-999: Blue
                  1000, '#10B981', // 1000-1999: Green
                  2000, '#F59E0B', // 2000-4999: Orange
                  5000, '#EF4444', // 5000+: Red
                ],
                'line-opacity': 0.8,
              }}
            />
          </Source>
        )}

        {/* StreetLight Traffic Bubbles (analysis-triggered) */}
        {streetlightSegmentsGeoJSON && (
          <Source id="streetlight-segments" type="geojson" data={streetlightSegmentsGeoJSON}>
            {/* Circle bubble sized and colored by traffic volume */}
            <Layer
              id="streetlight-bubbles"
              type="circle"
              paint={{
                'circle-radius': [
                  'interpolate', ['linear'], ['get', 'trips_volume'],
                  0, 16,
                  5000, 22,
                  15000, 30,
                  30000, 38,
                ],
                'circle-color': [
                  'step',
                  ['get', 'trips_volume'],
                  '#3B82F6',       // 0-999: Blue (low traffic)
                  1000, '#10B981', // 1000-4999: Green
                  5000, '#F59E0B', // 5000-14999: Amber
                  15000, '#EF4444', // 15000+: Red (high traffic)
                ],
                'circle-opacity': 0.88,
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 2.5,
              }}
            />
            {/* ADT text label inside the bubble */}
            <Layer
              id="streetlight-bubble-labels"
              type="symbol"
              layout={{
                'text-field': ['get', 'adt_label'],
                'text-size': 11,
                'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'],
                'text-allow-overlap': true,
                'text-ignore-placement': true,
              }}
              paint={{
                'text-color': '#ffffff',
                'text-halo-color': 'rgba(0,0,0,0.25)',
                'text-halo-width': 0.5,
              }}
            />
          </Source>
        )}

        {/* Traffic Counts Hover Popup */}
        {hoveredTraffic && (
          <Popup
            longitude={hoveredTraffic.longitude}
            latitude={hoveredTraffic.latitude}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={10}
          >
            <div className="text-sm">
              <div className="font-semibold text-gray-800">
                {hoveredTraffic.aadt.toLocaleString()} vehicles/day
              </div>
              <div className="text-xs text-gray-500">{hoveredTraffic.route}</div>
            </div>
          </Popup>
        )}

        {/* StreetLight Bubble Hover Popup */}
        {hoveredStreetlightSegment && (
          <Popup
            longitude={hoveredStreetlightSegment.longitude}
            latitude={hoveredStreetlightSegment.latitude}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={20}
          >
            <div className="text-sm p-1">
              <div className="font-semibold text-gray-800">
                {hoveredStreetlightSegment.trips_volume.toLocaleString()} vehicles/day
              </div>
              <div className="text-xs text-gray-600">
                Avg Speed: {hoveredStreetlightSegment.avg_speed} mph
              </div>
              <div className="text-xs text-gray-600">
                VMT: {hoveredStreetlightSegment.vmt.toLocaleString()}
              </div>
              <div className="text-[10px] text-gray-400 mt-1">
                {hoveredStreetlightSegment.rank ? `#${hoveredStreetlightSegment.rank} | ` : ''}StreetLight SATC
              </div>
            </div>
          </Popup>
        )}

        {/* Census Tract Tooltip */}
        {hoveredTractInfo && (
          <Popup
            longitude={hoveredTractInfo.lngLat[0]}
            latitude={hoveredTractInfo.lngLat[1]}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={10}
            className="!z-[100]"
          >
            <div className="text-sm min-w-[160px]">
              <div className="font-semibold text-purple-700 mb-1">
                Census Tract
              </div>
              <div className="text-xs text-gray-700 mb-1">
                {hoveredTractInfo.name}
              </div>
              <div className="text-xs text-gray-600">
                Pop: {hoveredTractInfo.population.toLocaleString()}
              </div>
              <div className="text-xs text-green-700">
                Income: ${hoveredTractInfo.income.toLocaleString()}
              </div>
              <div className="text-xs text-gray-600">
                Density: {hoveredTractInfo.density.toLocaleString()}/sq mi
              </div>
            </div>
          </Popup>
        )}

        {/* County Demographics Tooltip */}
        {hoveredCountyInfo && (
          <Popup
            longitude={hoveredCountyInfo.lngLat[0]}
            latitude={hoveredCountyInfo.lngLat[1]}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={10}
            className="!z-[100]"
          >
            <div className="text-sm min-w-[160px]">
              <div className="font-semibold text-blue-700 mb-1">
                {hoveredCountyInfo.name}
              </div>
              <div className="text-xs text-gray-600">
                Pop: {hoveredCountyInfo.population.toLocaleString()}
              </div>
              {hoveredCountyInfo.income > 0 && (
                <div className="text-xs text-green-700">
                  Income: ${hoveredCountyInfo.income.toLocaleString()}
                </div>
              )}
              <div className="text-xs text-gray-600">
                Density: {hoveredCountyInfo.density.toLocaleString()}/sq mi
              </div>
            </div>
          </Popup>
        )}

        {/* City Boundary Tooltip */}
        {hoveredCityInfo && (
          <Popup
            longitude={hoveredCityInfo.lngLat[0]}
            latitude={hoveredCityInfo.lngLat[1]}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={10}
            className="!z-[100]"
          >
            <div className="text-sm min-w-[140px]">
              <div className="font-semibold text-green-700 mb-1">
                {hoveredCityInfo.name}
              </div>
              {hoveredCityInfo.population > 0 && (
                <div className="text-xs text-gray-600">
                  Pop: {hoveredCityInfo.population.toLocaleString()}
                </div>
              )}
            </div>
          </Popup>
        )}

        {/* ZIP Code Boundary Tooltip */}
        {hoveredZipInfo && (
          <Popup
            longitude={hoveredZipInfo.lngLat[0]}
            latitude={hoveredZipInfo.lngLat[1]}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={10}
            className="!z-[100]"
          >
            <div className="text-sm min-w-[120px]">
              <div className="font-semibold text-orange-700 mb-1">
                ZIP: {hoveredZipInfo.zipCode}
              </div>
              {hoveredZipInfo.population > 0 && (
                <div className="text-xs text-gray-600">
                  Pop: {hoveredZipInfo.population.toLocaleString()}
                </div>
              )}
            </div>
          </Popup>
        )}

        {/* FEMA Flood Zones Layer */}
        {visibleLayersArray.includes('fema_flood') && (
          <Source
            id="fema-flood"
            type="raster"
            tiles={[
              'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&format=png32&transparent=true&layers=show:27,28&dpi=96&f=image'
            ]}
            tileSize={256}
          >
            <Layer
              id="fema-layer"
              type="raster"
              minzoom={12}
              paint={{ 'raster-opacity': 0.7 }}
            />
          </Source>
        )}

        {/* Isochrone Layer - Drive Time Areas */}
        {isochronePolygon && (
          <Source id="isochrone" type="geojson" data={isochronePolygon}>
            <Layer
              id="isochrone-fill"
              type="fill"
              paint={{
                'fill-color': getIsochroneColor(isochroneSettings.mode),
                'fill-opacity': getIsochroneOpacity(),
              }}
            />
            <Layer
              id="isochrone-outline"
              type="line"
              paint={{
                'line-color': getIsochroneColor(isochroneSettings.mode),
                'line-width': 2,
                'line-opacity': 0.8,
              }}
            />
          </Source>
        )}

        {/* Drawn Analysis Polygon */}
        {drawnPolygon && (
          <Source id="drawn-polygon" type="geojson" data={drawnPolygon}>
            <Layer
              id="drawn-polygon-fill"
              type="fill"
              paint={{
                'fill-color': '#3B82F6',
                'fill-opacity': 0.1,
              }}
            />
            <Layer
              id="drawn-polygon-outline"
              type="line"
              paint={{
                'line-color': '#3B82F6',
                'line-width': 2.5,
                'line-dasharray': [3, 2],
                'line-opacity': 0.8,
              }}
            />
          </Source>
        )}

        {/* Competitor Route Lines - shows paths from site to competitors */}
        {competitorRoutesGeoJSON && showCompetitorAccessPanel && (
          <Source id="competitor-routes" type="geojson" data={competitorRoutesGeoJSON}>
            {/* Background line for visibility */}
            <Layer
              id="competitor-routes-bg"
              type="line"
              paint={{
                'line-color': '#ffffff',
                'line-width': 5,
                'line-opacity': 0.8,
              }}
            />
            {/* Main route line - color by travel time */}
            <Layer
              id="competitor-routes-line"
              type="line"
              paint={{
                'line-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'travelTime'],
                  0, '#22c55e',   // Green for < 5 min
                  5, '#84cc16',   // Lime for 5-10 min
                  10, '#eab308',  // Yellow for 10-15 min
                  15, '#f97316',  // Orange for 15-20 min
                  20, '#ef4444',  // Red for > 20 min
                ],
                'line-width': 3,
                'line-opacity': 0.9,
              }}
            />
          </Source>
        )}

        {/* Parcel Boundaries Layer */}
        {visibleLayersArray.includes('parcels') && (
          <Source
            id="parcels-tiles"
            type="raster"
            tiles={[
              'https://tiles.arcgis.com/tiles/KzeiCaQsMoeCfoCq/arcgis/rest/services/Regrid_Nationwide_Parcel_Boundaries_v1/MapServer/tile/{z}/{y}/{x}'
            ]}
            tileSize={256}
          >
            <Layer
              id="parcels-layer"
              type="raster"
              minzoom={14}
              paint={{ 'raster-opacity': 1.0 }}
            />
          </Source>
        )}

        {/* County Boundaries - Mapbox Vector Tileset with data-driven choropleth */}
        {visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('counties') && (
          <Source
            id="county-boundaries-source"
            type="vector"
            url={`mapbox://${BOUNDARY_TILESETS.counties.id}`}
          >
            {/* Fill with data-driven color based on demographicMetric */}
            <Layer
              id="county-demographics-fill"
              type="fill"
              source-layer={BOUNDARY_TILESETS.counties.sourceLayer}
              minzoom={6}
              paint={{
                'fill-color': demographicMetric === 'income'
                  ? [
                      'interpolate',
                      ['linear'],
                      ['coalesce', ['get', 'MEDIAN_INCOME'], 0],
                      0, '#EFF6FF',
                      30000, '#BFDBFE',
                      50000, '#60A5FA',
                      75000, '#2563EB',
                      100000, '#1E40AF',
                    ]
                  : demographicMetric === 'density'
                  ? [
                      'interpolate',
                      ['linear'],
                      ['coalesce', ['get', 'POP_DENSITY'], 0],
                      0, '#EFF6FF',
                      50, '#BFDBFE',
                      200, '#60A5FA',
                      500, '#2563EB',
                      1000, '#1E40AF',
                    ]
                  : [
                      'interpolate',
                      ['linear'],
                      ['coalesce', ['get', 'POPULATION'], 0],
                      0, '#EFF6FF',
                      10000, '#BFDBFE',
                      25000, '#60A5FA',
                      50000, '#2563EB',
                      100000, '#1E40AF',
                    ],
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'GEOID'], hoveredCountyId],
                  0.5,
                  0.25,
                ],
              }}
            />
            {/* Outline with hover highlight */}
            <Layer
              id="county-demographics-outline"
              type="line"
              source-layer={BOUNDARY_TILESETS.counties.sourceLayer}
              minzoom={6}
              paint={{
                'line-color': '#3B82F6',
                'line-width': [
                  'case',
                  ['==', ['get', 'GEOID'], hoveredCountyId],
                  4,
                  ['interpolate', ['linear'], ['zoom'], 6, 1.5, 10, 2.5, 14, 3],
                ],
                'line-opacity': [
                  'case',
                  ['==', ['get', 'GEOID'], hoveredCountyId],
                  1,
                  0.9,
                ],
              }}
            />
          </Source>
        )}

        {/* City Boundaries - Mapbox Tileset */}
        {visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('cities') && (
          <Source
            id="city-boundaries-source"
            type="vector"
            url={`mapbox://${BOUNDARY_TILESETS.cities.id}`}
          >
            {/* Green fill with dynamic hover highlighting */}
            <Layer
              id="city-boundaries-fill"
              type="fill"
              source-layer={BOUNDARY_TILESETS.cities.sourceLayer}
              minzoom={6}
              paint={{
                'fill-color': '#22C55E',  // Green
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'NAME'], hoveredCityId],  // Dynamic hover check
                  0.35,  // Hovered
                  0.1,   // Normal
                ],
              }}
            />
            <Layer
              id="city-boundaries"
              type="line"
              source-layer={BOUNDARY_TILESETS.cities.sourceLayer}
              minzoom={6}
              paint={{
                'line-color': '#22C55E',  // Green
                'line-width': [
                  'case',
                  ['==', ['get', 'NAME'], hoveredCityId],  // Dynamic hover check
                  4,     // Hovered
                  ['interpolate', ['linear'], ['zoom'], 6, 1, 10, 1.5, 14, 2],  // Normal - thicker
                ],
                'line-opacity': [
                  'case',
                  ['==', ['get', 'NAME'], hoveredCityId],  // Dynamic hover check
                  1,     // Hovered
                  0.9,   // Normal - more visible
                ],
              }}
            />
          </Source>
        )}

        {/* ZIP Code Boundaries - Mapbox Tileset */}
        {visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('zipcodes') && (
          <Source
            id="zipcode-boundaries-source"
            type="vector"
            url={`mapbox://${BOUNDARY_TILESETS.zctas.id}`}
          >
            {/* Orange fill with dynamic hover highlighting */}
            <Layer
              id="zipcode-boundaries-fill"
              type="fill"
              source-layer={BOUNDARY_TILESETS.zctas.sourceLayer}
              minzoom={6}
              paint={{
                'fill-color': '#F97316',  // Orange
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'ZCTA5CE20'], hoveredZipId],  // Dynamic hover check
                  0.35,  // Hovered
                  0.08,  // Normal
                ],
              }}
            />
            <Layer
              id="zipcode-boundaries"
              type="line"
              source-layer={BOUNDARY_TILESETS.zctas.sourceLayer}
              minzoom={6}
              paint={{
                'line-color': '#F97316',  // Orange
                'line-width': [
                  'case',
                  ['==', ['get', 'ZCTA5CE20'], hoveredZipId],  // Dynamic hover check
                  4,    // Hovered
                  ['interpolate', ['linear'], ['zoom'], 6, 1, 10, 1.5, 14, 2],  // Normal - thicker
                ],
                'line-dasharray': [2, 2],
                'line-opacity': [
                  'case',
                  ['==', ['get', 'ZCTA5CE20'], hoveredZipId],  // Dynamic hover check
                  1,    // Hovered
                  0.85, // Normal - more visible
                ],
              }}
            />
          </Source>
        )}

        {/* Census Tracts Layer - Mapbox Vector Tileset with purple fill */}
        {visibleLayersArray.includes('boundaries') && visibleBoundaryTypes.has('census_tracts') && (
          <Source
            id="census-tracts-source"
            type="vector"
            url={`mapbox://${BOUNDARY_TILESETS.tracts.id}`}
          >
            {/* Purple fill with hover highlighting */}
            <Layer
              id="census-tract-fill"
              type="fill"
              source-layer={BOUNDARY_TILESETS.tracts.sourceLayer}
              minzoom={8}
              paint={{
                'fill-color': '#8B5CF6',
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'GEOID'], hoveredTractId],
                  0.35,
                  0.12,
                ],
              }}
            />
            {/* Outline with hover highlight */}
            <Layer
              id="census-tract-outline"
              type="line"
              source-layer={BOUNDARY_TILESETS.tracts.sourceLayer}
              minzoom={8}
              paint={{
                'line-color': '#8B5CF6',
                'line-width': [
                  'case',
                  ['==', ['get', 'GEOID'], hoveredTractId],
                  4,
                  1,
                ],
                'line-opacity': [
                  'case',
                  ['==', ['get', 'GEOID'], hoveredTractId],
                  1,
                  0.8,
                ],
              }}
            />
          </Source>
        )}

        {/* Activity Node Heat Map Layer */}
        {visibleLayersArray.includes('activity_heat') && (
          <Source id="activity-nodes" type="geojson" data={activityNodesGeoJSON}>
            <Layer {...activityHeatmapLayer} />
          </Source>
        )}

        {/* Analysis Radius Circle */}
        {radiusGeoJSON && (
          <Source id="analysis-radius" type="geojson" data={radiusGeoJSON}>
            <Layer {...radiusFillLayer} />
            <Layer {...radiusLineLayer} />
          </Source>
        )}

        {/* Parcel Boundary Polygon */}
        {parcelGeoJSON && (
          <Source id="parcel-boundary" type="geojson" data={parcelGeoJSON}>
            <Layer {...parcelFillLayer} />
            <Layer {...parcelLineLayer} />
          </Source>
        )}

        {/* Clustered Property Markers (ATTOM) */}
        {visiblePropertySources.has('attom') && properties.length > 0 && (
          <Source
            id="properties"
            type="geojson"
            data={propertiesGeoJSON}
            cluster={true}
            clusterMaxZoom={14}
            clusterRadius={50}
          >
            {/* Cluster circles */}
            <Layer
              id="clusters"
              type="circle"
              filter={['has', 'point_count']}
              paint={{
                'circle-color': [
                  'step',
                  ['get', 'point_count'],
                  '#8B5CF6', // Purple for < 10
                  10,
                  '#7C3AED', // Darker purple for 10-25
                  25,
                  '#6D28D9', // Even darker for > 25
                ],
                'circle-radius': [
                  'step',
                  ['get', 'point_count'],
                  20, // Small circles for < 10
                  10,
                  30, // Medium for 10-25
                  25,
                  40, // Large for > 25
                ],
                'circle-stroke-width': 2,
                'circle-stroke-color': '#fff',
              }}
            />

            {/* Cluster count text */}
            <Layer
              id="cluster-count"
              type="symbol"
              filter={['has', 'point_count']}
              layout={{
                'text-field': '{point_count_abbreviated}',
                'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
                'text-size': 14,
              }}
              paint={{
                'text-color': '#ffffff',
              }}
            />

            {/* Unclustered individual points as small circles */}
            <Layer
              id="unclustered-point"
              type="circle"
              filter={['!', ['has', 'point_count']]}
              paint={{
                'circle-color': '#8B5CF6',
                'circle-radius': 6,
                'circle-stroke-width': 2,
                'circle-stroke-color': '#fff',
              }}
            />
          </Source>
        )}
        
        {/* Individual property markers - only show when zoomed in enough (no clusters) */}
        {visiblePropertySources.has('attom') && 
         viewState.zoom >= 14 && 
         properties.map((property) => (
          <PropertyMarker
            key={property.id}
            property={property}
            isSelected={selectedProperty?.id === property.id}
            onClick={() => {
              setSelectedProperty(property);
              setSelectedTeamProperty(null);
              setSelectedStore(null);
              setSelectedPOI(null);
              // Set isochrone center if enabled
              if (isochroneSettings.enabled && property.longitude && property.latitude) {
                setIsochroneSettings({
                  ...isochroneSettings,
                  coordinates: [property.longitude, property.latitude],
                });
              }
            }}
          />
        ))}

        {/* Team property markers */}
        {visiblePropertySources.has('team') && teamProperties.map((property) => (
          <TeamPropertyMarker
            key={`team-${property.id}`}
            property={property}
            isSelected={selectedTeamProperty?.id === property.id}
            onClick={() => {
              setSelectedTeamProperty(property);
              setSelectedProperty(null);
              setSelectedStore(null);
              setSelectedPOI(null);
            }}
          />
        ))}

        {/* CSOKi Opportunity markers (top 5 pulse) */}
        {visibleLayersArray.includes('csoki_opportunities') && opportunities.map((opp) => (
          <PulsingOpportunityMarker
            key={`opportunity-${opp.property.id}`}
            opportunity={opp}
            isSelected={selectedOpportunity?.property.id === opp.property.id}
            zoom={viewState.zoom}
            onClick={(e: MarkerEvent<MouseEvent>) => {
              e.originalEvent.stopPropagation();
              opportunityClickedRef.current = true;
              setSelectedOpportunity(opp);
              setSelectedProperty(null);
              setSelectedTeamProperty(null);
            }}
            onSelect={(selected) => {
              opportunityClickedRef.current = true;
              setSelectedOpportunity(selected);
              setSelectedProperty(null);
              setSelectedTeamProperty(null);
            }}
          />
        ))}

        {/* POI Cluster markers (shown when zoomed out) */}
        {showPOIClusters && poiClusters.map((cluster) => (
          <Marker
            key={cluster.id}
            longitude={cluster.longitude}
            latitude={cluster.latitude}
            anchor="center"
            onClick={(e: MarkerEvent<MouseEvent>) => {
              e.originalEvent.stopPropagation();
              // Zoom in to show individual POIs
              mapRef.current?.flyTo({
                center: [cluster.longitude, cluster.latitude],
                zoom: POI_CLUSTER_ZOOM_THRESHOLD,
                duration: 500,
              });
            }}
            style={{ zIndex: 20, cursor: 'pointer' }}
          >
            <div
              className="flex items-center justify-center rounded-full bg-purple-600 text-white font-bold shadow-lg border-2 border-white"
              style={{
                width: Math.min(24 + cluster.count * 2, 48),
                height: Math.min(24 + cluster.count * 2, 48),
                fontSize: cluster.count > 99 ? '10px' : '12px',
              }}
            >
              {cluster.count}
            </div>
          </Marker>
        ))}

        {/* POI Layer - Native Mapbox GL layer for better performance */}
        {USE_NATIVE_POI_LAYERS && analysisResult?.pois && (
          <POILayer
            map={mapRef.current}
            pois={analysisResult.pois}
            onPOIClick={(poi) => {
              setSelectedPOI({
                place_id: poi.place_id,
                name: poi.name,
                category: poi.category,
                latitude: poi.latitude,
                longitude: poi.longitude,
                address: poi.address,
                rating: poi.rating,
              });
              setSelectedPOIId(poi.place_id);
            }}
            onPOIHover={() => {
              // Hover state is handled by feature state in the layer
            }}
          />
        )}

        {/* Building Layer - Interactive building footprints */}
        <BuildingLayer
          map={mapRef.current}
          visible={showBuildingLayer}
          onBuildingClick={(_building: BuildingInfo) => {
            // Building click handler - future: add info popup
          }}
        />

        {/* Legacy POI markers (fallback when native layers disabled) */}
        {!USE_NATIVE_POI_LAYERS && !showPOIClusters && visiblePOIs.map((poi) => (
          <POIMarker
            key={poi.place_id}
            poi={{
              place_id: poi.place_id,
              name: poi.name,
              category: poi.category,
              latitude: poi.latitude,
              longitude: poi.longitude,
              address: poi.address,
              rating: poi.rating,
            }}
            isSelected={selectedPOI?.place_id === poi.place_id}
            onClick={() => setSelectedPOI({
              place_id: poi.place_id,
              name: poi.name,
              category: poi.category,
              latitude: poi.latitude,
              longitude: poi.longitude,
              address: poi.address,
              rating: poi.rating,
            })}
            zoom={viewState.zoom}
          />
        ))}

        {/* Store markers with zoom-dependent sizing */}
        {visibleStores.map((store) => (
          <BrandMarker
            key={store.id}
            store={store}
            isSelected={selectedStore?.id === store.id}
            zoom={viewState.zoom}
            onClick={() => {
              setSelectedStore(store);
              setSelectedPOI(null);
              setSelectedPOIId(null);
              setSelectedProperty(null);
              setSelectedTeamProperty(null);
              // Set isochrone center if enabled
              if (isochroneSettings.enabled && store.longitude && store.latitude) {
                setIsochroneSettings({
                  ...isochroneSettings,
                  coordinates: [store.longitude, store.latitude],
                });
              }
            }}
          />
        ))}

        {/* Store popup */}
        {selectedStore && selectedStore.latitude && selectedStore.longitude && (
          <StorePopup
            store={selectedStore}
            onClose={() => setSelectedStore(null)}
            onAnalyze={handleAnalyzeArea}
            isAnalyzing={isAnalyzing}
          />
        )}

        {/* POI popup */}
        {selectedPOI && (
          <POIPopup
            poi={selectedPOI}
            onClose={() => {
              setSelectedPOI(null);
              setSelectedPOIId(null);
            }}
          />
        )}

        {/* Team property popup */}
        {selectedTeamProperty && (
          <TeamPropertyPopup
            property={selectedTeamProperty}
            onClose={() => setSelectedTeamProperty(null)}
          />
        )}

      </Map>
      </div>

      {/* Draggable Parcel Info Panel */}
      {(selectedParcel || isLoadingParcel || parcelError) && parcelClickPosition && (
        <DraggableParcelInfo
          parcel={selectedParcel}
          isLoading={isLoadingParcel}
          error={parcelError}
          onClose={() => {
            setSelectedParcel(null);
            setParcelError(null);
            setParcelClickPosition(null);
          }}
        />
      )}

      {/* Property Info Card */}
      {selectedProperty && (
        <PropertyInfoCard
          property={selectedProperty}
          onClose={() => setSelectedProperty(null)}
        />
      )}

      {/* Opportunity Info Card (CSOKi Opportunities) */}
      {selectedOpportunity && (
        <PropertyInfoCard
          property={selectedOpportunity.property}
          onClose={() => setSelectedOpportunity(null)}
          opportunityRank={selectedOpportunity.rank}
          opportunitySignals={selectedOpportunity.priority_signals}
        />
      )}

      {/* Competitor Access Panel - Drive time analysis to competitors */}
      {showCompetitorAccessPanel && arcSettings.siteLocation && (
        <CompetitorAccessPanel
          latitude={arcSettings.siteLocation[1]}
          longitude={arcSettings.siteLocation[0]}
          onClose={() => {
            setShowCompetitorAccessPanel(false);
            setArcSettings({ siteLocation: null });
            // Don't clear isochrone coordinates - let user keep the drive time polygon visible
            // User can clear via the X button on IsochroneControl if desired
          }}
          onNavigateToCompetitor={(lat, lng) => {
            mapRef.current?.getMap()?.flyTo({
              center: [lng, lat],
              zoom: 15,
              duration: 1000,
            });
          }}
        />
      )}

      {/* Flag Property FAB */}
      {visibleLayersArray.includes('properties_for_sale') && (
        <button
          onClick={() => {
            setTeamPropertyFormCoords(null);
            setShowTeamPropertyForm(true);
          }}
          className="absolute bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-3 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-full shadow-lg transition-all hover:scale-105"
          title="Flag a property (or right-click on map)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          <span>Flag Property</span>
        </button>
      )}

      {/* Team Property loading indicator */}
      {isLoadingTeamProperties && visibleLayersArray.includes('properties_for_sale') && (
        <div className="absolute bottom-20 right-6 z-40 bg-orange-100 text-orange-800 px-3 py-2 rounded-lg shadow text-sm flex items-center gap-2">
          <div className="animate-spin w-4 h-4 border-2 border-orange-600 border-t-transparent rounded-full" />
          Loading team properties...
        </div>
      )}

      {/* CSOKi Opportunities loading indicator */}
      {isLoadingOpportunities && visibleLayersArray.includes('csoki_opportunities') && (
        <div className="absolute bottom-32 right-6 z-40 bg-purple-100 text-purple-800 px-3 py-2 rounded-lg shadow text-sm flex items-center gap-2">
          <div className="animate-spin w-4 h-4 border-2 border-purple-600 border-t-transparent rounded-full" />
          Loading CSOKi opportunities...
        </div>
      )}

      {/* Team Property Form Modal */}
      <TeamPropertyForm
        isOpen={showTeamPropertyForm}
        onClose={() => {
          setShowTeamPropertyForm(false);
          setTeamPropertyFormCoords(null);
        }}
        onSuccess={handleTeamPropertySuccess}
        initialLatitude={teamPropertyFormCoords?.lat}
        initialLongitude={teamPropertyFormCoords?.lng}
      />
    </div>
  );
}
