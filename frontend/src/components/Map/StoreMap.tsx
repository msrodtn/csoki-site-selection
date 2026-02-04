import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, CircleF, PolygonF } from '@react-google-maps/api';
import { useMapStore } from '../../store/useMapStore';
import { useStores } from '../../hooks/useStores';
import { analysisApi, teamPropertiesApi, listingsApi, opportunitiesApi } from '../../services/api';
import {
  BRAND_COLORS,
  BRAND_LABELS,
  BRAND_LOGOS,
  POI_CATEGORY_COLORS,
  POI_CATEGORY_LABELS,
  PROPERTY_TYPE_COLORS,
  TEAM_PROPERTY_COLOR,
  TEAM_PROPERTY_SOURCE_LABELS,
  type BrandKey,
  type POICategory,
  type PropertyListing,
  type TeamProperty,
  type OpportunityRanking,
} from '../../types/store';
import type { Store, ParcelInfo, ScrapedListing } from '../../types/store';
import { FEMALegend } from './FEMALegend';
import { HeatMapLegend } from './HeatMapLegend';
import { ParcelLegend } from './ParcelLegend';
import { ZoningLegend, ZONING_COLORS, getZoningCategory } from './ZoningLegend';
import { QuickStatsBar } from './QuickStatsBar';
import { DraggableParcelInfo } from './DraggableParcelInfo';
import { PropertyInfoCard } from './PropertyInfoCard';
import { PropertyLegend } from './PropertyLegend';
import { TeamPropertyForm } from './TeamPropertyForm';

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

// Initial map position (Iowa/Nebraska region)
const INITIAL_CENTER = { lat: 41.5, lng: -96.0 };
const INITIAL_ZOOM = 6;

const mapContainerStyle = {
  width: '100%',
  height: '100%',
};

// Base map options (styles will be set dynamically)
const baseMapOptions: google.maps.MapOptions = {
  disableDefaultUI: false,
  zoomControl: true,
  mapTypeControl: true,
  scaleControl: true,
  streetViewControl: true,
  rotateControl: true,
  fullscreenControl: true,
  clickableIcons: true,
  gestureHandling: 'greedy',
};

// Map styles for hiding POI labels (default)
const hidePOIStyles: google.maps.MapTypeStyle[] = [
  {
    featureType: 'poi',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
];

// Map styles for showing POI labels (business labels enabled)
const showPOIStyles: google.maps.MapTypeStyle[] = [
  {
    featureType: 'poi.business',
    elementType: 'labels',
    stylers: [{ visibility: 'on' }],
  },
  {
    featureType: 'poi.attraction',
    elementType: 'labels',
    stylers: [{ visibility: 'on' }],
  },
  {
    featureType: 'poi.place_of_worship',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'poi.school',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'poi.medical',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'poi.government',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
];

// Libraries to load with Google Maps (must be constant to avoid re-renders)
const GOOGLE_MAPS_LIBRARIES: ('places' | 'visualization')[] = ['places', 'visualization'];

// Parse WKT geometry to Google Maps LatLng array
function parseWKTToLatLng(wkt: string): google.maps.LatLngLiteral[] | null {
  if (!wkt) return null;

  try {
    // Handle MULTIPOLYGON and POLYGON formats
    // MULTIPOLYGON(((-93.123 41.456, -93.124 41.457, ...)))
    // POLYGON((-93.123 41.456, -93.124 41.457, ...))

    // Remove the type prefix and get just the coordinate part
    let coordString = wkt;

    // For MULTIPOLYGON, extract the first polygon's outer ring
    if (wkt.startsWith('MULTIPOLYGON')) {
      // MULTIPOLYGON(((...))) - we want the innermost coordinates
      const match = wkt.match(/MULTIPOLYGON\s*\(\(\(([^)]+)\)/i);
      if (match) {
        coordString = match[1];
      }
    } else if (wkt.startsWith('POLYGON')) {
      // POLYGON((...)) - get the outer ring
      const match = wkt.match(/POLYGON\s*\(\(([^)]+)\)/i);
      if (match) {
        coordString = match[1];
      }
    }

    // Parse coordinate pairs (lng lat, lng lat, ...)
    const coords = coordString.split(',').map(pair => {
      const parts = pair.trim().split(/\s+/);
      if (parts.length >= 2) {
        const lng = parseFloat(parts[0]);
        const lat = parseFloat(parts[1]);
        return { lat, lng };
      }
      return { lat: NaN, lng: NaN };
    });

    // Filter out invalid coordinates
    const validCoords = coords.filter(c => !isNaN(c.lat) && !isNaN(c.lng));

    if (validCoords.length < 3) {
      console.warn('WKT parsed but insufficient valid coordinates:', validCoords.length);
      return null;
    }

    return validCoords;
  } catch (e) {
    console.error('Failed to parse WKT geometry:', wkt, e);
    return null;
  }
}

export function StoreMap() {
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

  const [selectedPOI, setSelectedPOI] = useState<{
    place_id: string;
    name: string;
    category: POICategory;
    latitude: number;
    longitude: number;
    address: string | null;
    rating: number | null;
  } | null>(null);

  // Parcel info state (for map click queries)
  const [selectedParcel, setSelectedParcel] = useState<ParcelInfo | null>(null);
  const [isLoadingParcel, setIsLoadingParcel] = useState(false);
  const [parcelError, setParcelError] = useState<string | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [parcelBoundary, setParcelBoundary] = useState<google.maps.LatLngLiteral[] | null>(null);
  const [parcelClickPosition, setParcelClickPosition] = useState<{ lat: number; lng: number } | null>(null);

  // Map bounds for filtering "In View" stats
  const [mapBounds, setMapBounds] = useState<{
    north: number;
    south: number;
    east: number;
    west: number;
  } | null>(null);

  // Property search state (ATTOM-powered)
  const [properties, setProperties] = useState<PropertyListing[]>([]);
  const [isLoadingProperties, setIsLoadingProperties] = useState(false);
  const [propertyError, setPropertyError] = useState<string | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);

  // Team properties state (user-contributed)
  const [teamProperties, setTeamProperties] = useState<TeamProperty[]>([]);
  const [isLoadingTeamProperties, setIsLoadingTeamProperties] = useState(false);
  const [selectedTeamProperty, setSelectedTeamProperty] = useState<TeamProperty | null>(null);

  // Team property form state
  const [showTeamPropertyForm, setShowTeamPropertyForm] = useState(false);
  const [teamPropertyFormCoords, setTeamPropertyFormCoords] = useState<{ lat: number; lng: number } | null>(null);

  // Scraped listings state (Active Listings from Crexi/LoopNet)
  const [scrapedListings, setScrapedListings] = useState<ScrapedListing[]>([]);
  const [isLoadingScrapedListings, setIsLoadingScrapedListings] = useState(false);
  const [selectedScrapedListing, setSelectedScrapedListing] = useState<ScrapedListing | null>(null);

  // CSOKi Opportunities state (filtered ATTOM properties)
  const [opportunities, setOpportunities] = useState<OpportunityRanking[]>([]);
  const [isLoadingOpportunities, setIsLoadingOpportunities] = useState(false);
  const [opportunitiesError, setOpportunitiesError] = useState<string | null>(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState<OpportunityRanking | null>(null);

  // Local map reference for internal use
  const mapRef = useRef<google.maps.Map | null>(null);

  // Track analysis center for re-analysis on radius change
  const analysisCenterRef = useRef<{ lat: number; lng: number } | null>(null);

  // Layer refs for Google Maps built-in layers
  const trafficLayerRef = useRef<google.maps.TrafficLayer | null>(null);
  const transitLayerRef = useRef<google.maps.TransitLayer | null>(null);

  // Custom tile overlay refs
  const femaFloodOverlayRef = useRef<google.maps.ImageMapType | null>(null);
  const parcelsOverlayRef = useRef<google.maps.ImageMapType | null>(null);

  // Heat map layer ref
  const heatMapLayerRef = useRef<google.maps.visualization.HeatmapLayer | null>(null);

  // Load Google Maps with Places library for autocomplete
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_API_KEY,
    libraries: GOOGLE_MAPS_LIBRARIES,
  });

  // Fetch all stores (filtering done client-side for performance)
  const { data: storeData, isLoading } = useStores({
    limit: 5000,
  });

  // Convert Sets to Arrays for reliable checking
  const visibleBrandsArray = useMemo(() => Array.from(visibleBrands), [visibleBrands]);
  const visibleStatesArray = useMemo(() => Array.from(visibleStates), [visibleStates]);
  const visiblePOICategoriesArray = useMemo(() => Array.from(visiblePOICategories), [visiblePOICategories]);

  // Filter stores by visible brands, visible states, and those with coordinates
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

  // Filter POIs by visible categories (limit to 100 to prevent map overload)
  const visiblePOIs = useMemo(() => {
    if (!analysisResult?.pois) return [];
    const filtered = analysisResult.pois.filter((poi) =>
      visiblePOICategoriesArray.includes(poi.category)
    );
    return filtered.slice(0, 100);
  }, [analysisResult?.pois, visiblePOICategoriesArray]);

  // Dynamic map options based on business labels layer
  const mapOptions = useMemo((): google.maps.MapOptions => {
    const showBusinessLabels = visibleLayers.has('business_labels');
    return {
      ...baseMapOptions,
      styles: showBusinessLabels ? showPOIStyles : hidePOIStyles,
    };
  }, [visibleLayers]);

  // Filter stores by current map viewport for "In View" stats
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

  const handleMarkerClick = useCallback(
    (store: Store) => {
      setSelectedStore(store);
      setSelectedPOI(null);
    },
    [setSelectedStore]
  );

  const handlePOIMarkerClick = useCallback(
    (poi: typeof selectedPOI) => {
      setSelectedPOI(poi);
    },
    []
  );

  const handleMapClick = useCallback(
    async (e: google.maps.MapMouseEvent) => {
      setSelectedStore(null);
      setSelectedPOI(null);

      // If parcel layer is visible and we clicked on the map (not a marker), query parcel info
      const isParcelLayerVisible = visibleLayers.has('parcels');
      const currentZoom = mapRef.current?.getZoom() || 0;

      if (isParcelLayerVisible && currentZoom >= 14 && e.latLng) {
        const lat = e.latLng.lat();
        const lng = e.latLng.lng();

        // Store click position for InfoWindow placement while loading
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
          // Clear parcel selection on error
          setSelectedParcel(null);
        } finally {
          setIsLoadingParcel(false);
        }
      } else {
        // Clear parcel selection when clicking elsewhere
        setSelectedParcel(null);
        setParcelError(null);
        setParcelClickPosition(null);
      }
    },
    [setSelectedStore, visibleLayers]
  );

  // On map load - store instance in Zustand for navigation from other components
  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
    setMapInstance(map);
    // Set initial position
    map.setCenter(INITIAL_CENTER);
    map.setZoom(INITIAL_ZOOM);
  }, [setMapInstance]);

  // Update bounds when map moves/zooms (for "In View" stats)
  const onIdle = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    const bounds = map.getBounds();
    if (bounds) {
      const ne = bounds.getNorthEast();
      const sw = bounds.getSouthWest();
      setMapBounds({
        north: ne.lat(),
        south: sw.lat(),
        east: ne.lng(),
        west: sw.lng(),
      });
    }
  }, []);

  const onUnmount = useCallback(() => {
    // Clean up layers
    if (trafficLayerRef.current) {
      trafficLayerRef.current.setMap(null);
      trafficLayerRef.current = null;
    }
    if (transitLayerRef.current) {
      transitLayerRef.current.setMap(null);
      transitLayerRef.current = null;
    }
    if (heatMapLayerRef.current) {
      heatMapLayerRef.current.setMap(null);
      heatMapLayerRef.current = null;
    }
    femaFloodOverlayRef.current = null;
    parcelsOverlayRef.current = null;

    mapRef.current = null;
    setMapInstance(null);
  }, [setMapInstance]);

  // Analyze trade area around a location
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

  // Handle analyze button click
  const handleAnalyzeArea = useCallback(() => {
    if (!selectedStore?.latitude || !selectedStore?.longitude) return;
    // Capture store info before analysis (since runAnalysis clears selectedStore)
    setAnalyzedStore(selectedStore);
    runAnalysis(selectedStore.latitude, selectedStore.longitude, analysisRadius);
  }, [selectedStore, analysisRadius, runAnalysis, setAnalyzedStore]);

  // Auto-refresh analysis when radius changes
  useEffect(() => {
    if (analysisCenterRef.current && analysisResult) {
      runAnalysis(analysisCenterRef.current.lat, analysisCenterRef.current.lng, analysisRadius);
    }
  }, [analysisRadius]); // Only trigger on radius change

  // Parse parcel geometry when a parcel is selected (map click)
  useEffect(() => {
    if (selectedParcel?.geometry) {
      const coords = parseWKTToLatLng(selectedParcel.geometry);
      setParcelBoundary(coords);
    } else {
      setParcelBoundary(null);
    }
  }, [selectedParcel]);

  // Handle mouse move for hover effect on parcels
  const handleMouseMove = useCallback(
    (e: google.maps.MapMouseEvent) => {
      const isParcelLayerVisible = visibleLayers.has('parcels');
      const currentZoom = mapRef.current?.getZoom() || 0;

      if (isParcelLayerVisible && currentZoom >= 14 && e.latLng) {
        setHoverPosition({ lat: e.latLng.lat(), lng: e.latLng.lng() });
      } else {
        setHoverPosition(null);
      }
    },
    [visibleLayers]
  );

  // Convert visibleLayers Set to array for effect dependency
  const visibleLayersArray = useMemo(() => Array.from(visibleLayers), [visibleLayers]);

  // Manage map layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Traffic Layer
    const showTraffic = visibleLayersArray.includes('traffic');
    if (showTraffic && !trafficLayerRef.current) {
      trafficLayerRef.current = new google.maps.TrafficLayer();
      trafficLayerRef.current.setMap(map);
    } else if (!showTraffic && trafficLayerRef.current) {
      trafficLayerRef.current.setMap(null);
      trafficLayerRef.current = null;
    }

    // Transit Layer
    const showTransit = visibleLayersArray.includes('transit');
    if (showTransit && !transitLayerRef.current) {
      transitLayerRef.current = new google.maps.TransitLayer();
      transitLayerRef.current.setMap(map);
    } else if (!showTransit && transitLayerRef.current) {
      transitLayerRef.current.setMap(null);
      transitLayerRef.current = null;
    }

    // Helper to calculate bounding box for a tile (for ArcGIS export endpoint)
    const getTileBbox = (coord: google.maps.Point, zoom: number) => {
      const scale = 1 << zoom;
      // Convert tile coords to lat/lng bounds
      const x1 = (coord.x / scale) * 360 - 180;
      const x2 = ((coord.x + 1) / scale) * 360 - 180;
      // Y uses Mercator projection
      const y1Mercator = Math.PI * (1 - (2 * (coord.y + 1)) / scale);
      const y2Mercator = Math.PI * (1 - (2 * coord.y) / scale);
      const y1 = (Math.atan(Math.sinh(y1Mercator)) * 180) / Math.PI;
      const y2 = (Math.atan(Math.sinh(y2Mercator)) * 180) / Math.PI;
      return { x1, y1, x2, y2 };
    };

    // FEMA Flood Zones Overlay (using ArcGIS export endpoint)
    // IMPORTANT: FEMA flood data only renders at zoom level 12+ (scale ~1:47000 or lower)
    const showFlood = visibleLayersArray.includes('fema_flood');
    if (showFlood && !femaFloodOverlayRef.current) {
      femaFloodOverlayRef.current = new google.maps.ImageMapType({
        getTileUrl: (coord, zoom) => {
          // FEMA flood zones only available at zoom 12+ per FEMA documentation
          if (zoom < 12) {
            return null;
          }
          const { x1, y1, x2, y2 } = getTileBbox(coord, zoom);
          const bbox = `${x1},${y1},${x2},${y2}`;
          // Show both layer 27 (Flood Hazard Boundaries) and 28 (Flood Hazard Zones)
          return `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/export?bbox=${bbox}&bboxSR=4326&imageSR=3857&size=256,256&format=png32&transparent=true&layers=show:27,28&dpi=96&f=image`;
        },
        tileSize: new google.maps.Size(256, 256),
        opacity: 0.7,
        name: 'FEMA Flood Zones',
      });
      map.overlayMapTypes.push(femaFloodOverlayRef.current);
    } else if (!showFlood && femaFloodOverlayRef.current) {
      const overlays = map.overlayMapTypes;
      for (let i = 0; i < overlays.getLength(); i++) {
        if (overlays.getAt(i) === femaFloodOverlayRef.current) {
          overlays.removeAt(i);
          break;
        }
      }
      femaFloodOverlayRef.current = null;
    }

    // Parcel Boundaries Overlay (Regrid via ArcGIS Living Atlas - free tile layer)
    const showParcels = visibleLayersArray.includes('parcels');
    if (showParcels && !parcelsOverlayRef.current) {
      parcelsOverlayRef.current = new google.maps.ImageMapType({
        getTileUrl: (coord, zoom) => {
          // Parcel data is most useful at zoom 14+ (street level)
          if (zoom < 14) {
            return null;
          }
          // Regrid ArcGIS tile service uses standard XYZ tile coordinates
          return `https://tiles.arcgis.com/tiles/KzeiCaQsMoeCfoCq/arcgis/rest/services/Regrid_Nationwide_Parcel_Boundaries_v1/MapServer/tile/${zoom}/${coord.y}/${coord.x}`;
        },
        tileSize: new google.maps.Size(256, 256),
        opacity: 1.0,  // Full opacity for better visibility
        name: 'Parcel Boundaries',
      });
      map.overlayMapTypes.push(parcelsOverlayRef.current);

      // Apply CSS filter to darken the parcel lines using MutationObserver
      const applyParcelFilter = () => {
        const tiles = document.querySelectorAll('img[src*="Regrid_Nationwide_Parcel_Boundaries"]');
        tiles.forEach((tile) => {
          const el = tile as HTMLElement;
          if (!el.dataset.filtered) {
            el.style.filter = 'contrast(2.0) brightness(0.85)';
            el.dataset.filtered = 'true';
          }
        });
      };

      // Initial application
      applyParcelFilter();

      // Watch for new tiles loading
      const observer = new MutationObserver(() => {
        applyParcelFilter();
      });
      observer.observe(document.body, { childList: true, subtree: true });

      // Store observer for cleanup
      (parcelsOverlayRef.current as unknown as { _observer?: MutationObserver })._observer = observer;
    } else if (!showParcels && parcelsOverlayRef.current) {
      // Clean up observer
      const overlay = parcelsOverlayRef.current as unknown as { _observer?: MutationObserver };
      if (overlay._observer) {
        overlay._observer.disconnect();
      }
      const overlays = map.overlayMapTypes;
      for (let i = 0; i < overlays.getLength(); i++) {
        if (overlays.getAt(i) === parcelsOverlayRef.current) {
          overlays.removeAt(i);
          break;
        }
      }
      parcelsOverlayRef.current = null;
    }
  }, [visibleLayersArray]);

  // Manage property search when layer is toggled
  useEffect(() => {
    const showProperties = visibleLayersArray.includes('properties_for_sale');

    if (showProperties && mapBounds) {
      // Trigger property search when layer is enabled and we have bounds
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
      // Clear properties when layer is disabled
      setProperties([]);
      setSelectedProperty(null);
      setPropertyError(null);
    }
  }, [visibleLayersArray.includes('properties_for_sale'), mapBounds]);

  // Manage team properties when layer is enabled
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

  // Manage scraped listings (Active Listings from Crexi/LoopNet) when toggle is enabled
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
      // Clear scraped listings when toggle is disabled
      setScrapedListings([]);
      setSelectedScrapedListing(null);
    }
  }, [visiblePropertySources, mapBounds]);

  // Manage CSOKi Opportunities when layer is toggled
  useEffect(() => {
    const showOpportunities = visibleLayersArray.includes('csoki_opportunities');

    if (showOpportunities && mapBounds) {
      const fetchOpportunities = async () => {
        setIsLoadingOpportunities(true);
        setOpportunitiesError(null);

        try {
          const result = await opportunitiesApi.search({
            min_lat: mapBounds.south,
            max_lat: mapBounds.north,
            min_lng: mapBounds.west,
            max_lng: mapBounds.east,
            min_parcel_acres: 0.8,
            max_parcel_acres: 2.0,
            min_building_sqft: 2500,
            max_building_sqft: 6000,
            include_retail: true,
            include_office: true,
            include_land: true,
            require_opportunity_signal: true,
            min_opportunity_score: 0,
            limit: 100,
          });

          setOpportunities(result.opportunities || []);
        } catch (error: any) {
          console.error('[Opportunities] Error fetching:', error);
          setOpportunitiesError(error.response?.data?.detail || 'Failed to load opportunities');
          setOpportunities([]);
        } finally {
          setIsLoadingOpportunities(false);
        }
      };

      fetchOpportunities();
    } else if (!showOpportunities) {
      // Clear opportunities when layer is disabled
      setOpportunities([]);
      setSelectedOpportunity(null);
      setOpportunitiesError(null);
    }
  }, [visibleLayersArray.includes('csoki_opportunities'), mapBounds]);

  // Manage heat map layer (separate effect since it depends on visibleStores)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const showHeatMap = visibleLayersArray.includes('competition_heat');

    if (showHeatMap && visibleStores.length > 0) {
      // Create heat map data points
      const heatMapData = visibleStores
        .filter((store) => store.latitude && store.longitude)
        .map((store) => new google.maps.LatLng(store.latitude!, store.longitude!));

      if (heatMapLayerRef.current) {
        // Update existing heat map data
        heatMapLayerRef.current.setData(heatMapData);
      } else {
        // Create new heat map layer
        heatMapLayerRef.current = new google.maps.visualization.HeatmapLayer({
          data: heatMapData,
          map: map,
          radius: 30,
          opacity: 0.6,
          gradient: [
            'rgba(0, 255, 0, 0)',
            'rgba(0, 255, 0, 0.5)',
            'rgba(255, 255, 0, 0.7)',
            'rgba(255, 165, 0, 0.8)',
            'rgba(255, 0, 0, 1)',
          ],
        });
      }
    } else if (!showHeatMap && heatMapLayerRef.current) {
      // Remove heat map layer
      heatMapLayerRef.current.setMap(null);
      heatMapLayerRef.current = null;
    }
  }, [visibleLayersArray, visibleStores]);

  // Create marker icon for each brand using logo images
  const createMarkerIcon = (brand: string, isSelected: boolean): google.maps.Icon => {
    const logoUrl = BRAND_LOGOS[brand as BrandKey];
    const size = isSelected ? 32 : 22;

    return {
      url: logoUrl,
      scaledSize: new google.maps.Size(size, size),
      anchor: new google.maps.Point(size / 2, size / 2),
    };
  };

  // Create POI marker icon
  const createPOIMarkerIcon = (category: POICategory, isSelected: boolean): google.maps.Symbol => {
    const color = POI_CATEGORY_COLORS[category] || '#666';
    const scale = isSelected ? 8 : 5;

    return {
      path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
      fillColor: color,
      fillOpacity: 0.9,
      strokeColor: isSelected ? '#ffffff' : color,
      strokeWeight: isSelected ? 2 : 1,
      scale: scale,
    };
  };

  // Create property marker icon (opportunity vs active listing)
  const createPropertyMarkerIcon = (property: PropertyListing, isSelected: boolean): google.maps.Symbol => {
    const isOpportunity = property.listing_type === 'opportunity';
    const typeColor = PROPERTY_TYPE_COLORS[property.property_type] || '#22C55E';
    const scale = isSelected ? 10 : 7;

    // Opportunity markers use a different shape (diamond) vs active listings (circle)
    if (isOpportunity) {
      return {
        path: 'M 0,-1 L 1,0 L 0,1 L -1,0 Z', // Diamond shape
        fillColor: '#8B5CF6', // Purple for opportunities
        fillOpacity: 0.9,
        strokeColor: isSelected ? '#ffffff' : '#6D28D9',
        strokeWeight: isSelected ? 3 : 2,
        scale: scale * 1.2,
      };
    }

    return {
      path: google.maps.SymbolPath.CIRCLE,
      fillColor: typeColor,
      fillOpacity: 0.9,
      strokeColor: isSelected ? '#ffffff' : typeColor,
      strokeWeight: isSelected ? 3 : 2,
      scale: scale,
    };
  };

  // Handle property marker click
  const handlePropertyMarkerClick = useCallback((property: PropertyListing) => {
    setSelectedProperty(property);
    setSelectedTeamProperty(null);
    setSelectedStore(null);
    setSelectedPOI(null);
    setSelectedScrapedListing(null);
  }, [setSelectedStore]);

  // Create team property marker icon (orange pin style)
  const createTeamPropertyMarkerIcon = (isSelected: boolean): google.maps.Symbol => {
    const scale = isSelected ? 10 : 7;

    return {
      path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
      fillColor: TEAM_PROPERTY_COLOR,
      fillOpacity: 0.9,
      strokeColor: isSelected ? '#ffffff' : '#EA580C',
      strokeWeight: isSelected ? 3 : 2,
      scale: scale,
    };
  };

  // Handle team property marker click
  const handleTeamPropertyMarkerClick = useCallback((property: TeamProperty) => {
    setSelectedTeamProperty(property);
    setSelectedProperty(null);
    setSelectedStore(null);
    setSelectedPOI(null);
    setSelectedScrapedListing(null);
  }, [setSelectedStore]);

  // Create scraped listing marker icon (blue circle with $ sign)
  const createScrapedListingMarkerIcon = (isSelected: boolean): google.maps.Icon => {
    const size = isSelected ? 36 : 28;
    const color = isSelected ? '#1D4ED8' : '#3B82F6';
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}">
        <circle cx="12" cy="12" r="10" fill="${color}" stroke="white" stroke-width="2"/>
        <text x="12" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="bold">$</text>
      </svg>
    `;
    return {
      url: `data:image/svg+xml,${encodeURIComponent(svg)}`,
      scaledSize: new google.maps.Size(size, size),
      anchor: new google.maps.Point(size / 2, size / 2),
    };
  };

  // Create opportunity marker icon (purple diamond with rank number)
  const createOpportunityMarkerIcon = (opportunity: OpportunityRanking, isSelected: boolean): google.maps.Icon => {
    const size = isSelected ? 40 : 32;
    const color = isSelected ? '#7C3AED' : '#9333EA';
    const rank = opportunity.rank <= 99 ? opportunity.rank : '!';
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}">
        <path d="M12 2 L22 12 L12 22 L2 12 Z" fill="${color}" stroke="white" stroke-width="2"/>
        <text x="12" y="15" text-anchor="middle" fill="white" font-size="10" font-weight="bold">${rank}</text>
      </svg>
    `;
    return {
      url: `data:image/svg+xml,${encodeURIComponent(svg)}`,
      scaledSize: new google.maps.Size(size, size),
      anchor: new google.maps.Point(size / 2, size / 2),
    };
  };

  // Handle scraped listing marker click
  const handleScrapedListingMarkerClick = useCallback((listing: ScrapedListing) => {
    setSelectedScrapedListing(listing);
    setSelectedProperty(null);
    setSelectedTeamProperty(null);
    setSelectedStore(null);
    setSelectedPOI(null);
    setSelectedOpportunity(null);
  }, [setSelectedStore]);

  // Handle opportunity marker click
  const handleOpportunityMarkerClick = useCallback((opportunity: OpportunityRanking) => {
    setSelectedOpportunity(opportunity);
    setSelectedProperty(null);
    setSelectedTeamProperty(null);
    setSelectedStore(null);
    setSelectedPOI(null);
    setSelectedScrapedListing(null);
  }, [setSelectedStore]);

  // Handle right-click to flag a property
  const handleMapRightClick = useCallback((e: google.maps.MapMouseEvent) => {
    if (e.latLng) {
      setTeamPropertyFormCoords({
        lat: e.latLng.lat(),
        lng: e.latLng.lng(),
      });
      setShowTeamPropertyForm(true);
    }
  }, []);

  // Handle team property form success
  const handleTeamPropertySuccess = useCallback(() => {
    // Reload team properties
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

  if (loadError) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100">
        <div className="text-red-600">Error loading Google Maps</div>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100">
        <div className="text-gray-600">Loading map...</div>
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

      {/* Quick Stats Bar - shows store counts by brand */}
      <QuickStatsBar stores={storesInView} />

      {/* FEMA Flood Zone Legend */}
      <FEMALegend isVisible={visibleLayersArray.includes('fema_flood')} />

      {/* Heat Map Legend */}
      <HeatMapLegend isVisible={visibleLayersArray.includes('competition_heat')} />

      {/* Parcel Boundaries Legend */}
      <ParcelLegend isVisible={visibleLayersArray.includes('parcels')} />

      {/* Zoning Colors Legend */}
      <ZoningLegend isVisible={visibleLayersArray.includes('zoning')} />

      {/* Property Legend - shows when property layer is enabled */}
      <PropertyLegend
        isVisible={visibleLayersArray.includes('properties_for_sale')}
        propertyCount={properties.length}
        isLoading={isLoadingProperties}
        error={propertyError}
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

      {/* Hover indicator for parcel layer */}
      {hoverPosition && visibleLayersArray.includes('parcels') && !selectedParcel && !isLoadingParcel && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 bg-amber-700 text-white px-3 py-1.5 rounded-lg shadow-md text-xs">
          Click to view parcel info
        </div>
      )}

      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        onLoad={onLoad}
        onUnmount={onUnmount}
        onIdle={onIdle}
        onClick={handleMapClick}
        onRightClick={handleMapRightClick}
        onMouseMove={handleMouseMove}
        options={mapOptions}
      >
        {/* Analysis radius circle - uses analysisRadius state for immediate reactivity */}
        {analysisResult && (
          <CircleF
            center={{
              lat: analysisResult.center_latitude,
              lng: analysisResult.center_longitude,
            }}
            radius={analysisRadius * 1609.34}
            options={{
              fillColor: '#E31837',
              fillOpacity: 0.08,
              strokeColor: '#E31837',
              strokeOpacity: 0.5,
              strokeWeight: 2,
            }}
          />
        )}

        {/* Parcel boundary highlight polygon - color-coded by zoning when enabled */}
        {parcelBoundary && parcelBoundary.length > 0 && (() => {
          // Determine colors based on zoning layer visibility
          const isZoningEnabled = visibleLayersArray.includes('zoning');
          const zoningCategory = isZoningEnabled && selectedParcel
            ? getZoningCategory(selectedParcel.zoning, selectedParcel.land_use)
            : null;
          const zoningStyle = zoningCategory ? ZONING_COLORS[zoningCategory] : null;

          // Use zoning colors if enabled, otherwise default yellow/gold
          const strokeColor = zoningStyle?.color || '#D97706';
          const fillColor = zoningStyle?.fill || '#FEF3C7';
          const glowColor = zoningStyle?.color || '#FBBF24';

          return (
            <>
              {/* Outer glow effect */}
              <PolygonF
                paths={parcelBoundary}
                options={{
                  fillColor: 'transparent',
                  fillOpacity: 0,
                  strokeColor: glowColor,
                  strokeOpacity: 0.5,
                  strokeWeight: 8,
                  zIndex: 49,
                }}
              />
              {/* Main boundary */}
              <PolygonF
                paths={parcelBoundary}
                options={{
                  fillColor: fillColor,
                  fillOpacity: 0.4,
                  strokeColor: strokeColor,
                  strokeOpacity: 1,
                  strokeWeight: 4,
                  zIndex: 50,
                }}
              />
            </>
          );
        })()}

        {/* Parcel click location marker - shows exactly where user clicked */}
        {parcelClickPosition && (selectedParcel || isLoadingParcel) && (
          <>
            {/* Outer pulse ring */}
            <CircleF
              center={parcelClickPosition}
              radius={25}
              options={{
                fillColor: '#D97706',
                fillOpacity: 0.2,
                strokeColor: '#D97706',
                strokeOpacity: 0.6,
                strokeWeight: 2,
                zIndex: 51,
                clickable: false,
              }}
            />
            {/* Inner solid marker */}
            <CircleF
              center={parcelClickPosition}
              radius={8}
              options={{
                fillColor: '#D97706',
                fillOpacity: 1,
                strokeColor: '#FFFFFF',
                strokeOpacity: 1,
                strokeWeight: 3,
                zIndex: 52,
                clickable: false,
              }}
            />
          </>
        )}

        {/* Hover indicator circle when parcel layer is active */}
        {hoverPosition && visibleLayersArray.includes('parcels') && !selectedParcel && !isLoadingParcel && (
          <CircleF
            center={hoverPosition}
            radius={15}
            options={{
              fillColor: '#A16207',
              fillOpacity: 0.5,
              strokeColor: '#A16207',
              strokeOpacity: 1,
              strokeWeight: 2,
              zIndex: 100,
              clickable: false,
            }}
          />
        )}

        {/* Property markers (ATTOM opportunities) - only show if 'attom' source is visible */}
        {visiblePropertySources.has('attom') && properties.map((property) => (
          <MarkerF
            key={property.id}
            position={{ lat: property.latitude, lng: property.longitude }}
            icon={createPropertyMarkerIcon(property, selectedProperty?.id === property.id)}
            onClick={() => handlePropertyMarkerClick(property)}
            zIndex={selectedProperty?.id === property.id ? 1500 : 200}
            title={`${property.address} - ${property.price_display || 'Price N/A'}`}
          />
        ))}

        {/* Highlight circle around selected property marker */}
        {selectedProperty && (
          <CircleF
            center={{ lat: selectedProperty.latitude, lng: selectedProperty.longitude }}
            radius={50} // meters
            options={{
              fillColor: '#8B5CF6',
              fillOpacity: 0.15,
              strokeColor: '#8B5CF6',
              strokeWeight: 3,
              strokeOpacity: 0.8,
              zIndex: 1400,
              clickable: false,
            }}
          />
        )}

        {/* Team property markers (user-contributed) - only show if 'team' source is visible */}
        {visiblePropertySources.has('team') && teamProperties.map((property) => (
          <MarkerF
            key={`team-${property.id}`}
            position={{ lat: property.latitude, lng: property.longitude }}
            icon={createTeamPropertyMarkerIcon(selectedTeamProperty?.id === property.id)}
            onClick={() => handleTeamPropertyMarkerClick(property)}
            zIndex={selectedTeamProperty?.id === property.id ? 1600 : 250}
            title={`${property.address} - Team Flagged`}
          />
        ))}

        {/* Scraped listing markers (Active Listings from Crexi/LoopNet) - only show if 'scraped' source is visible */}
        {visiblePropertySources.has('scraped') && scrapedListings
          .filter((listing) => listing.latitude != null && listing.longitude != null)
          .map((listing) => (
            <MarkerF
              key={`scraped-${listing.id}`}
              position={{ lat: listing.latitude!, lng: listing.longitude! }}
              icon={createScrapedListingMarkerIcon(selectedScrapedListing?.id === listing.id)}
              onClick={() => handleScrapedListingMarkerClick(listing)}
              zIndex={selectedScrapedListing?.id === listing.id ? 1700 : 300}
              title={`${listing.title || listing.address} - ${listing.price_display || 'Price N/A'}`}
            />
          ))}

        {/* CSOKi Opportunity markers (filtered ATTOM properties) - shown when csoki_opportunities layer is active */}
        {visibleLayersArray.includes('csoki_opportunities') && opportunities.map((opportunity) => (
          <MarkerF
            key={`opportunity-${opportunity.property.id}`}
            position={{ lat: opportunity.property.latitude, lng: opportunity.property.longitude }}
            icon={createOpportunityMarkerIcon(opportunity, selectedOpportunity?.property.id === opportunity.property.id)}
            onClick={() => handleOpportunityMarkerClick(opportunity)}
            zIndex={selectedOpportunity?.property.id === opportunity.property.id ? 1800 : 400}
            title={`Rank #${opportunity.rank}: ${opportunity.property.address} - ${opportunity.signal_count} signals`}
          />
        ))}

        {/* Highlight circle around selected opportunity */}
        {selectedOpportunity && (
          <CircleF
            center={{ lat: selectedOpportunity.property.latitude, lng: selectedOpportunity.property.longitude }}
            radius={50} // meters
            options={{
              fillColor: '#9333EA',
              fillOpacity: 0.15,
              strokeColor: '#9333EA',
              strokeWeight: 3,
              strokeOpacity: 0.8,
              zIndex: 1750,
              clickable: false,
            }}
          />
        )}

        {/* POI markers */}
        {visiblePOIs.map((poi) => (
          <MarkerF
            key={poi.place_id}
            position={{ lat: poi.latitude, lng: poi.longitude }}
            icon={createPOIMarkerIcon(poi.category, selectedPOI?.place_id === poi.place_id)}
            onClick={() =>
              handlePOIMarkerClick({
                place_id: poi.place_id,
                name: poi.name,
                category: poi.category,
                latitude: poi.latitude,
                longitude: poi.longitude,
                address: poi.address,
                rating: poi.rating,
              })
            }
            zIndex={selectedPOI?.place_id === poi.place_id ? 1000 : 100}
          />
        ))}

        {/* Store markers */}
        {visibleStores.map((store) => (
          <MarkerF
            key={store.id}
            position={{ lat: store.latitude!, lng: store.longitude! }}
            icon={createMarkerIcon(store.brand, selectedStore?.id === store.id)}
            onClick={() => handleMarkerClick(store)}
            zIndex={selectedStore?.id === store.id ? 2000 : 500}
          />
        ))}

        {/* Info window for selected POI */}
        {selectedPOI && (
          <InfoWindowF
            position={{ lat: selectedPOI.latitude, lng: selectedPOI.longitude }}
            onCloseClick={() => setSelectedPOI(null)}
            options={{ disableAutoPan: true }}
          >
            <div className="min-w-[180px] p-1">
              <div
                className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white"
                style={{ backgroundColor: POI_CATEGORY_COLORS[selectedPOI.category] }}
              >
                {POI_CATEGORY_LABELS[selectedPOI.category]}
              </div>
              <div className="text-sm">
                <p className="font-medium">{selectedPOI.name}</p>
                {selectedPOI.address && (
                  <p className="text-gray-600 text-xs mt-1">{selectedPOI.address}</p>
                )}
                {selectedPOI.rating && (
                  <p className="text-gray-500 text-xs mt-1">{selectedPOI.rating} ★</p>
                )}
              </div>
            </div>
          </InfoWindowF>
        )}

        {/* Info window for selected store */}
        {selectedStore && selectedStore.latitude && selectedStore.longitude && (
          <InfoWindowF
            position={{ lat: selectedStore.latitude, lng: selectedStore.longitude }}
            onCloseClick={() => setSelectedStore(null)}
            options={{ disableAutoPan: true }}
          >
            <div className="min-w-[200px] p-1">
              <div
                className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white"
                style={{
                  backgroundColor:
                    BRAND_COLORS[selectedStore.brand as BrandKey] || '#666',
                }}
              >
                {BRAND_LABELS[selectedStore.brand as BrandKey] || selectedStore.brand}
              </div>
              <div className="text-sm">
                {selectedStore.street && (
                  <p className="font-medium">{selectedStore.street}</p>
                )}
                <p>
                  {selectedStore.city}, {selectedStore.state} {selectedStore.postal_code}
                </p>
              </div>
              {/* Analyze Area button */}
              <button
                onClick={handleAnalyzeArea}
                disabled={isAnalyzing}
                className="mt-3 w-full bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
              >
                {isAnalyzing ? 'Analyzing...' : 'Analyze Trade Area'}
              </button>
            </div>
          </InfoWindowF>
        )}

        {/* Info window for selected team property */}
        {selectedTeamProperty && (
          <InfoWindowF
            position={{ lat: selectedTeamProperty.latitude, lng: selectedTeamProperty.longitude }}
            onCloseClick={() => setSelectedTeamProperty(null)}
            options={{ disableAutoPan: true }}
          >
            <div className="min-w-[220px] p-1">
              <div
                className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white flex items-center gap-1"
                style={{ backgroundColor: TEAM_PROPERTY_COLOR }}
              >
                <span>Team Flagged</span>
                {selectedTeamProperty.source_type && (
                  <span className="opacity-75">
                    • {TEAM_PROPERTY_SOURCE_LABELS[selectedTeamProperty.source_type]}
                  </span>
                )}
              </div>
              <div className="text-sm">
                <p className="font-medium">{selectedTeamProperty.address}</p>
                <p className="text-gray-600">
                  {selectedTeamProperty.city}, {selectedTeamProperty.state} {selectedTeamProperty.postal_code || ''}
                </p>
                {selectedTeamProperty.price && (
                  <p className="text-green-700 font-medium mt-1">
                    ${selectedTeamProperty.price.toLocaleString()}
                  </p>
                )}
                {selectedTeamProperty.sqft && (
                  <p className="text-gray-500 text-xs">
                    {selectedTeamProperty.sqft.toLocaleString()} sqft
                  </p>
                )}
                {selectedTeamProperty.notes && (
                  <p className="text-gray-600 text-xs mt-2 italic border-t pt-2">
                    "{selectedTeamProperty.notes}"
                  </p>
                )}
                {selectedTeamProperty.contributor_name && (
                  <p className="text-gray-400 text-xs mt-1">
                    — {selectedTeamProperty.contributor_name}
                  </p>
                )}
              </div>
              {selectedTeamProperty.listing_url && (
                <a
                  href={selectedTeamProperty.listing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 block w-full text-center bg-orange-600 hover:bg-orange-700 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
                >
                  View Listing
                </a>
              )}
            </div>
          </InfoWindowF>
        )}

        {/* Info window for selected scraped listing (Active Listings) */}
        {selectedScrapedListing && selectedScrapedListing.latitude && selectedScrapedListing.longitude && (
          <InfoWindowF
            position={{ lat: selectedScrapedListing.latitude, lng: selectedScrapedListing.longitude }}
            onCloseClick={() => setSelectedScrapedListing(null)}
            options={{ disableAutoPan: true }}
          >
            <div className="min-w-[220px] p-1">
              <div className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white flex items-center gap-1 bg-blue-600">
                <span>Active Listing</span>
                <span className="opacity-75 capitalize">• {selectedScrapedListing.source}</span>
              </div>
              <div className="text-sm">
                {selectedScrapedListing.title && (
                  <p className="font-medium text-gray-900 mb-1">{selectedScrapedListing.title}</p>
                )}
                <p className="text-gray-700">{selectedScrapedListing.address || 'Address N/A'}</p>
                <p className="text-gray-600">
                  {selectedScrapedListing.city}, {selectedScrapedListing.state} {selectedScrapedListing.postal_code || ''}
                </p>
                {selectedScrapedListing.price_display && (
                  <p className="text-green-700 font-bold mt-1 text-base">
                    {selectedScrapedListing.price_display}
                  </p>
                )}
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  {selectedScrapedListing.sqft && (
                    <span>{selectedScrapedListing.sqft.toLocaleString()} SF</span>
                  )}
                  {selectedScrapedListing.lot_size_acres && (
                    <span>{selectedScrapedListing.lot_size_acres.toFixed(2)} acres</span>
                  )}
                  {selectedScrapedListing.property_type && (
                    <span className="capitalize">{selectedScrapedListing.property_type}</span>
                  )}
                </div>
                {selectedScrapedListing.broker_name && (
                  <p className="text-gray-400 text-xs mt-2 border-t pt-2">
                    {selectedScrapedListing.broker_name}
                    {selectedScrapedListing.broker_company && ` • ${selectedScrapedListing.broker_company}`}
                  </p>
                )}
              </div>
              {selectedScrapedListing.listing_url && (
                <a
                  href={selectedScrapedListing.listing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 block w-full text-center bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
                >
                  View on {selectedScrapedListing.source === 'crexi' ? 'Crexi' : 'LoopNet'}
                </a>
              )}
            </div>
          </InfoWindowF>
        )}

      </GoogleMap>

      {/* Draggable Parcel Info Panel (for map click queries) */}
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

      {/* Property Info Card (for property marker clicks) - Now self-positioning and draggable */}
      {selectedProperty && (
        <PropertyInfoCard
          property={selectedProperty}
          onClose={() => setSelectedProperty(null)}
        />
      )}

      {/* Opportunity Info Card (for CSOKi opportunity marker clicks) */}
      {selectedOpportunity && (
        <PropertyInfoCard
          property={{
            ...selectedOpportunity.property,
            // Enhance property with opportunity ranking context
            opportunity_signals: [
              // Add rank as first signal
              {
                signal_type: 'opportunity_rank',
                description: `Rank #${selectedOpportunity.rank} of ${opportunities.length} opportunities`,
                strength: 'high' as const,
              },
              // Add priority signals
              ...selectedOpportunity.priority_signals.map((signal) => ({
                signal_type: 'priority',
                description: signal,
                strength: 'high' as const,
              })),
              // Add original property signals
              ...selectedOpportunity.property.opportunity_signals,
            ],
          }}
          onClose={() => setSelectedOpportunity(null)}
        />
      )}

      {/* Flag Property FAB - visible when properties layer is enabled */}
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
