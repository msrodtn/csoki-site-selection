import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, CircleF, PolygonF } from '@react-google-maps/api';
import { useMapStore } from '../../store/useMapStore';
import { useStores } from '../../hooks/useStores';
import { analysisApi } from '../../services/api';
import {
  BRAND_COLORS,
  BRAND_LABELS,
  BRAND_LOGOS,
  POI_CATEGORY_COLORS,
  POI_CATEGORY_LABELS,
  PROPERTY_TYPE_COLORS,
  PROPERTY_TYPE_LABELS,
  type BrandKey,
  type POICategory,
  type PropertyType,
} from '../../types/store';
import type { Store, ParcelInfo } from '../../types/store';
import { FEMALegend } from './FEMALegend';
import { HeatMapLegend } from './HeatMapLegend';
import { ParcelLegend } from './ParcelLegend';
import { ZoningLegend, ZONING_COLORS, getZoningCategory } from './ZoningLegend';
import { PropertyLegend } from './PropertyLegend';
import { QuickStatsBar } from './QuickStatsBar';
import { DraggableParcelInfo } from './DraggableParcelInfo';

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
    // Property search
    propertySearchResult,
    setPropertySearchResult,
    isPropertySearching,
    setIsPropertySearching,
    setPropertySearchError,
    visiblePropertyTypes,
    // Selected property
    selectedProperty,
    setSelectedProperty,
    // Property parcel
    propertyParcel,
    setPropertyParcel,
    isLoadingPropertyParcel,
    setIsLoadingPropertyParcel,
    propertyParcelError,
    setPropertyParcelError,
    showPropertyParcelPanel,
    setShowPropertyParcelPanel,
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

  // Property parcel boundary state (for selected property listings)
  const [propertyParcelBoundary, setPropertyParcelBoundary] = useState<google.maps.LatLngLiteral[] | null>(null);

  // Map bounds for filtering "In View" stats
  const [mapBounds, setMapBounds] = useState<{
    north: number;
    south: number;
    east: number;
    west: number;
  } | null>(null);

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

  // Filter property listings by visible property types
  const visiblePropertyTypesArray = useMemo(() => Array.from(visiblePropertyTypes), [visiblePropertyTypes]);
  const visibleProperties = useMemo(() => {
    if (!propertySearchResult?.listings) return [];
    return propertySearchResult.listings.filter(
      (listing) =>
        listing.latitude &&
        listing.longitude &&
        visiblePropertyTypesArray.includes(listing.property_type)
    );
  }, [propertySearchResult?.listings, visiblePropertyTypesArray]);

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

  // Auto-fetch parcel when property is selected (with debounce)
  useEffect(() => {
    if (!selectedProperty?.latitude || !selectedProperty?.longitude) {
      setPropertyParcel(null);
      setPropertyParcelBoundary(null);
      setPropertyParcelError(null);
      return;
    }

    // Clear previous parcel data immediately
    setPropertyParcel(null);
    setPropertyParcelBoundary(null);
    setPropertyParcelError(null);

    // Debounce to avoid rapid API calls if user clicks multiple properties quickly
    const timeoutId = setTimeout(async () => {
      setIsLoadingPropertyParcel(true);

      try {
        const parcelInfo = await analysisApi.getParcelInfo({
          latitude: selectedProperty.latitude!,
          longitude: selectedProperty.longitude!,
        });
        setPropertyParcel(parcelInfo);

        // Parse geometry for boundary polygon
        if (parcelInfo.geometry) {
          const coords = parseWKTToLatLng(parcelInfo.geometry);
          setPropertyParcelBoundary(coords);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Parcel data unavailable';
        setPropertyParcelError(message);
      } finally {
        setIsLoadingPropertyParcel(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [selectedProperty, setPropertyParcel, setIsLoadingPropertyParcel, setPropertyParcelError]);

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

  // Property search when layer is enabled
  useEffect(() => {
    const showProperties = visibleLayersArray.includes('properties_for_sale');
    const map = mapRef.current;

    if (showProperties && map && !propertySearchResult && !isPropertySearching) {
      // Get current map center for the search
      const center = map.getCenter();
      if (!center) return;

      const lat = center.lat();
      const lng = center.lng();

      // Trigger property search
      setIsPropertySearching(true);
      setPropertySearchError(null);

      analysisApi
        .searchProperties({
          latitude: lat,
          longitude: lng,
          radius_miles: 10, // Search within 10 miles of map center
        })
        .then((result) => {
          setPropertySearchResult(result);
        })
        .catch((error) => {
          const message = error instanceof Error ? error.message : 'Failed to search properties';
          setPropertySearchError(message);
          console.error('Property search error:', error);
        })
        .finally(() => {
          setIsPropertySearching(false);
        });
    } else if (!showProperties && propertySearchResult) {
      // Clear results when layer is disabled
      setPropertySearchResult(null);
      setSelectedProperty(null);
    }
  }, [visibleLayersArray, propertySearchResult, isPropertySearching, setPropertySearchResult, setIsPropertySearching, setPropertySearchError]);

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

  // Create Property marker icon (dollar sign shape)
  const createPropertyMarkerIcon = (propertyType: PropertyType, isSelected: boolean): google.maps.Symbol => {
    const color = PROPERTY_TYPE_COLORS[propertyType] || '#22C55E';
    const scale = isSelected ? 10 : 7;

    return {
      path: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z',
      fillColor: color,
      fillOpacity: 1,
      strokeColor: isSelected ? '#ffffff' : '#000000',
      strokeWeight: isSelected ? 2 : 0.5,
      scale: scale / 12,
      anchor: new google.maps.Point(12, 12),
    };
  };

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

      {/* Property search loading indicator */}
      {isPropertySearching && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-green-600 text-white px-4 py-2 rounded-lg shadow-md flex items-center gap-2">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Searching for properties...
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

      {/* Properties For Sale Legend */}
      <PropertyLegend isVisible={visibleLayersArray.includes('properties_for_sale')} />

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

        {/* Property parcel boundary highlight - green theme to match property markers */}
        {propertyParcelBoundary && propertyParcelBoundary.length > 0 && (() => {
          // Determine colors based on zoning layer visibility
          const isZoningEnabled = visibleLayersArray.includes('zoning');
          const zoningCategory = isZoningEnabled && propertyParcel
            ? getZoningCategory(propertyParcel.zoning, propertyParcel.land_use)
            : null;
          const zoningStyle = zoningCategory ? ZONING_COLORS[zoningCategory] : null;

          // Use zoning colors if enabled, otherwise green theme (matching property markers)
          const strokeColor = zoningStyle?.color || '#16A34A';  // green-600
          const fillColor = zoningStyle?.fill || '#DCFCE7';     // green-100
          const glowColor = zoningStyle?.color || '#22C55E';    // green-500

          return (
            <>
              {/* Outer glow effect */}
              <PolygonF
                paths={propertyParcelBoundary}
                options={{
                  fillColor: 'transparent',
                  fillOpacity: 0,
                  strokeColor: glowColor,
                  strokeOpacity: 0.5,
                  strokeWeight: 8,
                  zIndex: 47,
                }}
              />
              {/* Main boundary */}
              <PolygonF
                paths={propertyParcelBoundary}
                options={{
                  fillColor: fillColor,
                  fillOpacity: 0.4,
                  strokeColor: strokeColor,
                  strokeOpacity: 1,
                  strokeWeight: 4,
                  zIndex: 48,
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

        {/* Property listing markers */}
        {visibleProperties.map((property) => (
          <MarkerF
            key={property.id}
            position={{ lat: property.latitude!, lng: property.longitude! }}
            icon={createPropertyMarkerIcon(property.property_type, selectedProperty?.id === property.id)}
            onClick={() => {
              setSelectedProperty(property);
              setSelectedStore(null);
              setSelectedPOI(null);
            }}
            zIndex={selectedProperty?.id === property.id ? 1500 : 300}
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

        {/* Info window for selected property listing */}
        {selectedProperty && selectedProperty.latitude && selectedProperty.longitude && (
          <InfoWindowF
            position={{ lat: selectedProperty.latitude, lng: selectedProperty.longitude }}
            onCloseClick={() => {
              setSelectedProperty(null);
              setPropertyParcel(null);
              setPropertyParcelBoundary(null);
              setPropertyParcelError(null);
              setShowPropertyParcelPanel(false);
            }}
            options={{ disableAutoPan: true }}
          >
            <div className="min-w-[240px] max-w-[280px] p-1">
              <div
                className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white flex items-center justify-between"
                style={{
                  backgroundColor: PROPERTY_TYPE_COLORS[selectedProperty.property_type] || '#22C55E',
                }}
              >
                <span>{PROPERTY_TYPE_LABELS[selectedProperty.property_type]}</span>
                <span className="opacity-75 text-[10px] uppercase">{selectedProperty.source}</span>
              </div>
              <div className="text-sm">
                <p className="font-medium">{selectedProperty.address}</p>
                <p className="text-gray-600">
                  {selectedProperty.city}, {selectedProperty.state}
                </p>
                {selectedProperty.price && (
                  <p className="font-bold text-green-600 mt-1">{selectedProperty.price}</p>
                )}
                {selectedProperty.sqft && (
                  <p className="text-gray-500 text-xs">{selectedProperty.sqft}</p>
                )}
                {selectedProperty.description && (
                  <p className="text-gray-500 text-xs mt-1 line-clamp-2">{selectedProperty.description}</p>
                )}
              </div>

              {/* Parcel Summary Section */}
              <div className="mt-2 pt-2 border-t border-gray-200">
                {isLoadingPropertyParcel ? (
                  <div className="flex items-center gap-2 text-gray-500 text-xs">
                    <div className="animate-spin w-3 h-3 border border-green-600 border-t-transparent rounded-full" />
                    Loading parcel...
                  </div>
                ) : propertyParcelError ? (
                  <p className="text-xs text-gray-400">{propertyParcelError}</p>
                ) : propertyParcel ? (
                  <div className="text-xs space-y-1">
                    <p className="font-medium text-gray-700">Parcel Info</p>
                    <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-gray-600">
                      {propertyParcel.acreage != null && (
                        <span>{propertyParcel.acreage.toFixed(2)} acres</span>
                      )}
                      {propertyParcel.zoning && (
                        <span>Zoning: {propertyParcel.zoning}</span>
                      )}
                      {propertyParcel.building_sqft != null && (
                        <span>{propertyParcel.building_sqft.toLocaleString()} SF</span>
                      )}
                      {propertyParcel.year_built != null && (
                        <span>Built: {propertyParcel.year_built}</span>
                      )}
                    </div>
                    {propertyParcel.total_value != null && (
                      <p className="text-green-700 font-medium">
                        Assessed: ${propertyParcel.total_value.toLocaleString()}
                      </p>
                    )}
                    <button
                      onClick={() => setShowPropertyParcelPanel(true)}
                      className="text-green-600 hover:text-green-700 text-[10px] font-medium mt-1"
                    >
                      View full parcel details →
                    </button>
                  </div>
                ) : null}
              </div>

              {selectedProperty.url && (
                <a
                  href={selectedProperty.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 block w-full text-center bg-green-600 hover:bg-green-700 text-white text-xs font-medium py-2 px-3 rounded transition-colors"
                >
                  View Listing
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

      {/* Draggable Property Parcel Info Panel (for selected property listings) */}
      {showPropertyParcelPanel && propertyParcel && (
        <DraggableParcelInfo
          parcel={propertyParcel}
          isLoading={false}
          error={null}
          variant="property"
          onClose={() => setShowPropertyParcelPanel(false)}
        />
      )}
    </div>
  );
}
