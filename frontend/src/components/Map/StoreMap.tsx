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
  clickableIcons: false, // Prevent clicking Google's default POIs
  gestureHandling: 'greedy', // Allow all gestures without requiring ctrl
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
    viewport,
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
  } = useMapStore();

  const [map, setMap] = useState<google.maps.Map | null>(null);
  const [selectedPOI, setSelectedPOI] = useState<{
    place_id: string;
    name: string;
    category: POICategory;
    latitude: number;
    longitude: number;
    address: string | null;
    rating: number | null;
  } | null>(null);

  // Track the last viewport update to avoid unnecessary panning
  const lastViewportRef = useRef({ latitude: viewport.latitude, longitude: viewport.longitude, zoom: viewport.zoom });

  // Track analysis center for re-analysis on radius change
  const analysisCenterRef = useRef<{ lat: number; lng: number } | null>(null);

  // Lock map position during/after analysis
  const mapPositionLockRef = useRef<{ center: google.maps.LatLngLiteral; zoom: number } | null>(null);

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
    // Limit markers to prevent performance issues
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
      // Don't clear selected store - keep the analysis context
    },
    []
  );

  const handleMapClick = useCallback(() => {
    setSelectedStore(null);
    setSelectedPOI(null);
  }, [setSelectedStore]);

  const onLoad = useCallback((map: google.maps.Map) => {
    setMap(map);
    // Set initial position from viewport state
    map.setCenter({ lat: viewport.latitude, lng: viewport.longitude });
    map.setZoom(viewport.zoom);
  }, [viewport.latitude, viewport.longitude, viewport.zoom]);

  const onUnmount = useCallback(() => {
    setMap(null);
  }, []);

  // Update map center only when viewport is explicitly changed (search/state filter)
  // Don't pan during active analysis
  useEffect(() => {
    if (!map) return;
    if (isAnalyzing) return; // Don't move map during analysis

    const last = lastViewportRef.current;
    const hasChanged =
      last.latitude !== viewport.latitude ||
      last.longitude !== viewport.longitude ||
      last.zoom !== viewport.zoom;

    if (hasChanged) {
      map.panTo({ lat: viewport.latitude, lng: viewport.longitude });
      map.setZoom(viewport.zoom);
      lastViewportRef.current = { latitude: viewport.latitude, longitude: viewport.longitude, zoom: viewport.zoom };
      // Clear analysis when navigating away
      if (analysisResult) {
        analysisCenterRef.current = null;
        mapPositionLockRef.current = null;
      }
    }
  }, [map, viewport.latitude, viewport.longitude, viewport.zoom, isAnalyzing, analysisResult]);

  // Analyze trade area around a location
  const runAnalysis = useCallback(async (lat: number, lng: number, radius: number) => {
    // Lock current map position before analysis
    if (map) {
      const center = map.getCenter();
      const zoom = map.getZoom();
      if (center && zoom !== undefined) {
        mapPositionLockRef.current = {
          center: { lat: center.lat(), lng: center.lng() },
          zoom: zoom,
        };
      }
    }

    // Close the InfoWindow to prevent UI jitter
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

      // Restore map position after analysis
      if (map && mapPositionLockRef.current) {
        map.setCenter(mapPositionLockRef.current.center);
        map.setZoom(mapPositionLockRef.current.zoom);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to analyze area';
      setAnalysisError(message);
    } finally {
      setIsAnalyzing(false);
    }
  }, [map, setSelectedStore, setAnalysisResult, setIsAnalyzing, setAnalysisError, setShowAnalysisPanel]);

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
  }, [analysisRadius]); // Only trigger on radius change, not on runAnalysis change

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
        center={{ lat: 41.5, lng: -96.0 }}
        zoom={6}
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
            animation={undefined}
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
            animation={undefined}
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
