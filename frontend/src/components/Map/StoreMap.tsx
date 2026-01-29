import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, CircleF } from '@react-google-maps/api';
import { useMapStore } from '../../store/useMapStore';
import { useStores } from '../../hooks/useStores';
import { analysisApi } from '../../services/api';
import {
  BRAND_COLORS,
  BRAND_LABELS,
  POI_CATEGORY_COLORS,
  POI_CATEGORY_LABELS,
  type BrandKey,
  type POICategory,
} from '../../types/store';
import type { Store } from '../../types/store';

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

// Initial map position (Iowa/Nebraska region)
const INITIAL_CENTER = { lat: 41.5, lng: -96.0 };
const INITIAL_ZOOM = 6;

const mapContainerStyle = {
  width: '100%',
  height: '100%',
};

const mapOptions: google.maps.MapOptions = {
  disableDefaultUI: false,
  zoomControl: true,
  mapTypeControl: true,
  scaleControl: true,
  streetViewControl: false,
  rotateControl: false,
  fullscreenControl: true,
  clickableIcons: false,
  gestureHandling: 'greedy',
  styles: [
    {
      featureType: 'poi',
      elementType: 'labels',
      stylers: [{ visibility: 'off' }],
    },
  ],
};

// Libraries to load with Google Maps (must be constant to avoid re-renders)
const GOOGLE_MAPS_LIBRARIES: ('places')[] = ['places'];

export function StoreMap() {
  const {
    selectedStore,
    setSelectedStore,
    visibleBrands,
    visibleStates,
    analysisResult,
    setAnalysisResult,
    isAnalyzing,
    setIsAnalyzing,
    setAnalysisError,
    visiblePOICategories,
    setShowAnalysisPanel,
    analysisRadius,
    setMapInstance,
    visibleLayers,
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

  // Local map reference for internal use
  const mapRef = useRef<google.maps.Map | null>(null);

  // Track analysis center for re-analysis on radius change
  const analysisCenterRef = useRef<{ lat: number; lng: number } | null>(null);

  // Layer refs for Google Maps built-in layers
  const trafficLayerRef = useRef<google.maps.TrafficLayer | null>(null);
  const transitLayerRef = useRef<google.maps.TransitLayer | null>(null);

  // Custom tile overlay refs
  const femaFloodOverlayRef = useRef<google.maps.ImageMapType | null>(null);
  const censusTractsOverlayRef = useRef<google.maps.ImageMapType | null>(null);

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

  const handleMapClick = useCallback(() => {
    setSelectedStore(null);
    setSelectedPOI(null);
  }, [setSelectedStore]);

  // On map load - store instance in Zustand for navigation from other components
  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
    setMapInstance(map);
    // Set initial position
    map.setCenter(INITIAL_CENTER);
    map.setZoom(INITIAL_ZOOM);
  }, [setMapInstance]);

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
    femaFloodOverlayRef.current = null;
    censusTractsOverlayRef.current = null;

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
    runAnalysis(selectedStore.latitude, selectedStore.longitude, analysisRadius);
  }, [selectedStore, analysisRadius, runAnalysis]);

  // Auto-refresh analysis when radius changes
  useEffect(() => {
    if (analysisCenterRef.current && analysisResult) {
      runAnalysis(analysisCenterRef.current.lat, analysisCenterRef.current.lng, analysisRadius);
    }
  }, [analysisRadius]); // Only trigger on radius change

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
    const showFlood = visibleLayersArray.includes('fema_flood');
    if (showFlood && !femaFloodOverlayRef.current) {
      femaFloodOverlayRef.current = new google.maps.ImageMapType({
        getTileUrl: (coord, zoom) => {
          const { x1, y1, x2, y2 } = getTileBbox(coord, zoom);
          const bbox = `${x1},${y1},${x2},${y2}`;
          return `https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/export?bbox=${bbox}&bboxSR=4326&imageSR=3857&size=256,256&format=png32&transparent=true&f=image`;
        },
        tileSize: new google.maps.Size(256, 256),
        opacity: 0.6,
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

    // Census Tracts Overlay (using ArcGIS export endpoint)
    const showCensus = visibleLayersArray.includes('census_tracts');
    if (showCensus && !censusTractsOverlayRef.current) {
      censusTractsOverlayRef.current = new google.maps.ImageMapType({
        getTileUrl: (coord, zoom) => {
          const { x1, y1, x2, y2 } = getTileBbox(coord, zoom);
          const bbox = `${x1},${y1},${x2},${y2}`;
          // Census Tracts layer (layer 8 in TIGERweb)
          return `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/export?bbox=${bbox}&bboxSR=4326&imageSR=3857&size=256,256&format=png32&transparent=true&layers=show:8&f=image`;
        },
        tileSize: new google.maps.Size(256, 256),
        opacity: 0.5,
        name: 'Census Tracts',
      });
      map.overlayMapTypes.push(censusTractsOverlayRef.current);
    } else if (!showCensus && censusTractsOverlayRef.current) {
      const overlays = map.overlayMapTypes;
      for (let i = 0; i < overlays.getLength(); i++) {
        if (overlays.getAt(i) === censusTractsOverlayRef.current) {
          overlays.removeAt(i);
          break;
        }
      }
      censusTractsOverlayRef.current = null;
    }
  }, [visibleLayersArray]);

  // Create SVG marker icon for each brand (larger than POIs to stand out)
  const createMarkerIcon = (brand: string, isSelected: boolean): google.maps.Symbol => {
    const color = BRAND_COLORS[brand as BrandKey] || '#666';
    const scale = isSelected ? 14 : 10;

    return {
      path: google.maps.SymbolPath.CIRCLE,
      fillColor: color,
      fillOpacity: 1,
      strokeColor: '#ffffff',
      strokeWeight: isSelected ? 3 : 2,
      scale: scale,
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

      {/* Store count */}
      <div className="absolute top-4 right-4 z-10 bg-white px-3 py-1 rounded-lg shadow-md text-sm">
        {visibleStores.length.toLocaleString()} stores visible
        {visiblePOIs.length > 0 && (
          <span className="ml-2 text-gray-500">| {visiblePOIs.length} POIs</span>
        )}
      </div>

      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        onLoad={onLoad}
        onUnmount={onUnmount}
        onClick={handleMapClick}
        options={mapOptions}
      >
        {/* Analysis radius circle */}
        {analysisResult && (
          <CircleF
            center={{
              lat: analysisResult.center_latitude,
              lng: analysisResult.center_longitude,
            }}
            radius={analysisResult.radius_meters}
            options={{
              fillColor: '#E31837',
              fillOpacity: 0.08,
              strokeColor: '#E31837',
              strokeOpacity: 0.5,
              strokeWeight: 2,
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
      </GoogleMap>
    </div>
  );
}
