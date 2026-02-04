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
  NavigationControl,
  ScaleControl,
  GeolocateControl,
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
import { analysisApi, teamPropertiesApi, listingsApi } from '../../services/api';
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
  type ScrapedListing,
} from '../../types/store';
import { FEMALegend } from './FEMALegend';
import { HeatMapLegend } from './HeatMapLegend';
import { ParcelLegend } from './ParcelLegend';
import { ZoningLegend } from './ZoningLegend';
import { QuickStatsBar } from './QuickStatsBar';
import { DraggableParcelInfo } from './DraggableParcelInfo';
import { PropertyInfoCard } from './PropertyInfoCard';
import { PropertyLegend } from './PropertyLegend';
import { TeamPropertyForm } from './TeamPropertyForm';
import MapStyleSwitcher from './MapStyleSwitcher';
import IsochroneControl, { type IsochroneSettings, type TravelMode } from './IsochroneControl';
import { fetchIsochrone, getIsochroneColor, getIsochroneOpacity } from '../../services/mapbox-isochrone';

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

// Brand marker component
function BrandMarker({
  store,
  isSelected,
  onClick,
}: {
  store: Store;
  isSelected: boolean;
  onClick: () => void;
}) {
  const brand = store.brand as BrandKey;
  const color = BRAND_COLORS[brand] || '#666666';
  const logo = BRAND_LOGOS[brand];
  const size = isSelected ? 32 : 22;

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

// POI marker component
function POIMarker({
  poi,
  isSelected,
  onClick,
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
}) {
  const color = POI_CATEGORY_COLORS[poi.category] || '#666';
  const size = isSelected ? 16 : 10;

  return (
    <Marker
      longitude={poi.longitude}
      latitude={poi.latitude}
      anchor="center"
      onClick={(e: MarkerEvent<MouseEvent>) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
      style={{ zIndex: isSelected ? 1000 : 100 }}
    >
      <svg width={size * 2} height={size * 2} viewBox="0 0 24 24">
        <path
          d="M12 2L4 12l8 10 8-10L12 2z"
          fill={color}
          stroke={isSelected ? 'white' : color}
          strokeWidth={isSelected ? 2 : 1}
        />
      </svg>
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

// Scraped listing marker component
function ScrapedListingMarker({
  listing,
  isSelected,
  onClick,
}: {
  listing: ScrapedListing;
  isSelected: boolean;
  onClick: () => void;
}) {
  if (!listing.latitude || !listing.longitude) return null;

  const size = isSelected ? 36 : 28;
  const color = isSelected ? '#1D4ED8' : '#3B82F6';

  return (
    <Marker
      longitude={listing.longitude}
      latitude={listing.latitude}
      anchor="center"
      onClick={(e: MarkerEvent<MouseEvent>) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
      style={{ zIndex: isSelected ? 1700 : 300 }}
    >
      <svg width={size} height={size} viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" fill={color} stroke="white" strokeWidth="2" />
        <text x="12" y="16" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">$</text>
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
          className="mt-2 w-full flex items-center justify-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
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
          className="mt-3 w-full flex items-center justify-center gap-1 bg-green-600 hover:bg-green-700 text-white text-xs font-medium py-2 px-2 rounded transition-colors"
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
            className="block w-full text-center bg-green-600 hover:bg-green-700 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
          >
            Street View
          </a>
        </div>
      </div>
    </Popup>
  );
}

// Heatmap layer configuration
const heatmapLayer: HeatmapLayerSpecification = {
  id: 'stores-heat',
  type: 'heatmap',
  source: 'stores',
  maxzoom: 15,
  paint: {
    'heatmap-weight': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
    'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
    'heatmap-color': [
      'interpolate',
      ['linear'],
      ['heatmap-density'],
      0, 'rgba(0, 255, 0, 0)',
      0.2, 'rgba(0, 255, 0, 0.5)',
      0.4, 'rgba(255, 255, 0, 0.7)',
      0.6, 'rgba(255, 165, 0, 0.8)',
      0.8, 'rgba(255, 0, 0, 0.9)',
      1, 'rgba(255, 0, 0, 1)',
    ],
    'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 15, 30],
    'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 7, 0.8, 15, 0.3],
  },
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
    setShowAnalysisPanel,
    analysisRadius,
    setMapInstance,
    visibleLayers,
    visiblePropertySources,
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

  // Scraped listings state
  const [scrapedListings, setScrapedListings] = useState<ScrapedListing[]>([]);
  const [isLoadingScrapedListings, setIsLoadingScrapedListings] = useState(false);

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

  // Filter POIs
  const visiblePOIs = useMemo(() => {
    if (!analysisResult?.pois) return [];
    const filtered = analysisResult.pois.filter((poi) =>
      visiblePOICategoriesArray.includes(poi.category)
    );
    return filtered.slice(0, 100);
  }, [analysisResult?.pois, visiblePOICategoriesArray]);

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

  // GeoJSON for stores heatmap
  const storesGeoJSON = useMemo(() => {
    return {
      type: 'FeatureCollection' as const,
      features: visibleStores.map((store) => ({
        type: 'Feature' as const,
        properties: {
          id: store.id,
          brand: store.brand,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [store.longitude!, store.latitude!],
        },
      })),
    };
  }, [visibleStores]);

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

  // Auto-refresh analysis when radius changes
  useEffect(() => {
    if (analysisCenterRef.current && analysisResult) {
      runAnalysis(analysisCenterRef.current.lat, analysisCenterRef.current.lng, analysisRadius);
    }
  }, [analysisRadius]);

  // Handle map click
  const handleMapClick = useCallback(async (e: mapboxgl.MapMouseEvent) => {
    const map = mapRef.current?.getMap();
    
    // Check if click was on a cluster
    if (map) {
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

    const isParcelLayerVisible = visibleLayersArray.includes('parcels');
    const currentZoom = viewState.zoom;

    if (isParcelLayerVisible && currentZoom >= 14 && e.lngLat) {
      const lat = e.lngLat.lat;
      const lng = e.lngLat.lng;

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
  }, [setSelectedStore, visibleLayersArray, viewState.zoom]);

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
      
      // Change cursor on cluster hover
      map.on('mouseenter', 'clusters', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'clusters', () => {
        map.getCanvas().style.cursor = '';
      });
    }
  }, [setMapInstance]);

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

  // Scraped listings when toggle is enabled
  useEffect(() => {
    const showScraped = visiblePropertySources.has('scraped');

    if (showScraped && mapBounds) {
      const fetchScrapedListings = async () => {
        setIsLoadingScrapedListings(true);
        try {
          const result = await listingsApi.searchByBounds({
            min_lat: mapBounds.south,
            max_lat: mapBounds.north,
            min_lng: mapBounds.west,
            max_lng: mapBounds.east,
            limit: 100,
          });
          setScrapedListings(result.listings || []);
        } catch (error: any) {
          console.error('[ScrapedListings] Error fetching:', error);
          setScrapedListings([]);
        } finally {
          setIsLoadingScrapedListings(false);
        }
      };

      fetchScrapedListings();
    } else if (!showScraped) {
      setScrapedListings([]);
    }
  }, [visiblePropertySources, mapBounds]);

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

  // Fetch isochrone when settings change or coordinates update
  useEffect(() => {
    if (isochroneSettings.enabled && isochroneSettings.coordinates && MAPBOX_TOKEN) {
      fetchIsochrone(
        {
          coordinates: isochroneSettings.coordinates,
          minutes: isochroneSettings.minutes,
          mode: isochroneSettings.mode,
        },
        MAPBOX_TOKEN
      ).then((polygon) => {
        setIsochronePolygon(polygon);
      }).catch((error) => {
        console.error('Failed to fetch isochrone:', error);
        setIsochronePolygon(null);
      });
    } else {
      setIsochronePolygon(null);
    }
  }, [isochroneSettings]);

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
      <HeatMapLegend isVisible={visibleLayersArray.includes('competition_heat')} />
      <ParcelLegend isVisible={visibleLayersArray.includes('parcels')} />
      <ZoningLegend isVisible={visibleLayersArray.includes('zoning')} />
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
      />

      {/* Property loading indicator */}
      {isLoadingProperties && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 bg-purple-600 text-white px-4 py-2 rounded-lg shadow-md text-sm flex items-center gap-2">
          <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
          Searching properties...
        </div>
      )}

      {/* Property error display */}
      {propertyError && visibleLayersArray.includes('properties_for_sale') && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 bg-red-600 text-white px-4 py-2 rounded-lg shadow-md text-sm">
          {propertyError}
        </div>
      )}

      <Map
        ref={mapRef}
        {...viewState}
        onMove={(evt: ViewStateChangeEvent) => setViewState(evt.viewState)}
        onMoveEnd={onMoveEnd}
        onLoad={onLoad}
        onClick={handleMapClick}
        onContextMenu={handleMapRightClick}
        style={{ width: '100%', height: '100%' }}
        mapStyle={mapStyle}
        mapboxAccessToken={MAPBOX_TOKEN}
      >
        {/* Navigation controls */}
        <NavigationControl position="top-right" />
        <ScaleControl position="bottom-right" />
        <GeolocateControl position="top-right" />

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

        {/* Heatmap Layer */}
        {visibleLayersArray.includes('competition_heat') && (
          <Source id="stores" type="geojson" data={storesGeoJSON}>
            <Layer {...heatmapLayer} />
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

        {/* Scraped listing markers */}
        {visiblePropertySources.has('scraped') && scrapedListings.map((listing) => (
          <ScrapedListingMarker
            key={`scraped-${listing.id}`}
            listing={listing}
            isSelected={false}
            onClick={() => {
              // No popup for scraped listings per user request
            }}
          />
        ))}

        {/* POI markers */}
        {visiblePOIs.map((poi) => (
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
          />
        ))}

        {/* Store markers */}
        {visibleStores.map((store) => (
          <BrandMarker
            key={store.id}
            store={store}
            isSelected={selectedStore?.id === store.id}
            onClick={() => {
              setSelectedStore(store);
              setSelectedPOI(null);
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
            onClose={() => setSelectedPOI(null)}
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

      {/* Scraped Listings loading indicator */}
      {isLoadingScrapedListings && visiblePropertySources.has('scraped') && (
        <div className="absolute bottom-32 right-6 z-40 bg-blue-100 text-blue-800 px-3 py-2 rounded-lg shadow text-sm flex items-center gap-2">
          <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full" />
          Loading active listings...
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
