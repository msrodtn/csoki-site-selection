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
  type BrandKey,
  type POICategory,
} from '../../types/store';
import type { Store, ParcelInfo } from '../../types/store';
import { FEMALegend } from './FEMALegend';
import { HeatMapLegend } from './HeatMapLegend';
import { ParcelLegend } from './ParcelLegend';
import { QuickStatsBar } from './QuickStatsBar';

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
  streetViewControl: true,
  rotateControl: true,
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
const GOOGLE_MAPS_LIBRARIES: ('places' | 'visualization')[] = ['places', 'visualization'];

// Parse WKT geometry to Google Maps LatLng array
function parseWKTToLatLng(wkt: string): google.maps.LatLngLiteral[] | null {
  if (!wkt) return null;

  try {
    // Handle MULTIPOLYGON and POLYGON formats
    // Example: MULTIPOLYGON(((-93.123 41.456, -93.124 41.457, ...)))
    // or POLYGON((-93.123 41.456, -93.124 41.457, ...))

    // Extract coordinates from WKT
    const coordMatch = wkt.match(/\(\(+([^)]+)\)+\)/);
    if (!coordMatch) return null;

    const coordString = coordMatch[1];
    const coords = coordString.split(',').map(pair => {
      const [lng, lat] = pair.trim().split(/\s+/).map(Number);
      return { lat, lng };
    });

    // Filter out invalid coordinates
    return coords.filter(c => !isNaN(c.lat) && !isNaN(c.lng));
  } catch {
    console.error('Failed to parse WKT geometry:', wkt);
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

  // Parcel info state
  const [selectedParcel, setSelectedParcel] = useState<ParcelInfo | null>(null);
  const [isLoadingParcel, setIsLoadingParcel] = useState(false);
  const [parcelError, setParcelError] = useState<string | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [parcelBoundary, setParcelBoundary] = useState<google.maps.LatLngLiteral[] | null>(null);

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
    censusTractsOverlayRef.current = null;
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

  // Parse parcel geometry when a parcel is selected
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
        opacity: 0.7,
        name: 'Parcel Boundaries',
      });
      map.overlayMapTypes.push(parcelsOverlayRef.current);
    } else if (!showParcels && parcelsOverlayRef.current) {
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
      <QuickStatsBar stores={visibleStores} />

      {/* FEMA Flood Zone Legend */}
      <FEMALegend isVisible={visibleLayersArray.includes('fema_flood')} />

      {/* Heat Map Legend */}
      <HeatMapLegend isVisible={visibleLayersArray.includes('competition_heat')} />

      {/* Parcel Boundaries Legend */}
      <ParcelLegend isVisible={visibleLayersArray.includes('parcels')} />

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
        onClick={handleMapClick}
        onMouseMove={handleMouseMove}
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

        {/* Parcel boundary highlight polygon */}
        {parcelBoundary && parcelBoundary.length > 0 && (
          <PolygonF
            paths={parcelBoundary}
            options={{
              fillColor: '#A16207',
              fillOpacity: 0.3,
              strokeColor: '#A16207',
              strokeOpacity: 1,
              strokeWeight: 3,
              zIndex: 50,
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

        {/* Parcel info window */}
        {(selectedParcel || isLoadingParcel) && (
          <InfoWindowF
            position={{ lat: selectedParcel?.latitude || 0, lng: selectedParcel?.longitude || 0 }}
            onCloseClick={() => {
              setSelectedParcel(null);
              setParcelError(null);
            }}
            options={{ disableAutoPan: true, maxWidth: 320 }}
          >
            <div className="min-w-[280px] p-1">
              <div className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white bg-amber-700">
                Parcel Information
              </div>

              {isLoadingParcel ? (
                <div className="text-center py-4 text-gray-500">
                  <div className="animate-spin inline-block w-5 h-5 border-2 border-amber-600 border-t-transparent rounded-full mb-2"></div>
                  <p className="text-xs">Loading parcel data...</p>
                </div>
              ) : parcelError ? (
                <div className="text-center py-2 text-red-600 text-xs">
                  {parcelError}
                </div>
              ) : selectedParcel ? (
                <div className="text-sm space-y-2">
                  {/* Parcel ID */}
                  {selectedParcel.parcel_id && (
                    <div>
                      <span className="text-gray-500 text-xs">Parcel ID:</span>
                      <p className="font-medium">{selectedParcel.parcel_id}</p>
                    </div>
                  )}

                  {/* Address */}
                  {selectedParcel.address && (
                    <div>
                      <span className="text-gray-500 text-xs">Address:</span>
                      <p className="font-medium">{selectedParcel.address}</p>
                      {(selectedParcel.city || selectedParcel.state) && (
                        <p className="text-gray-600 text-xs">
                          {[selectedParcel.city, selectedParcel.state, selectedParcel.zip_code]
                            .filter(Boolean)
                            .join(', ')}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Owner */}
                  {selectedParcel.owner && (
                    <div>
                      <span className="text-gray-500 text-xs">Owner:</span>
                      <p className="font-medium">{selectedParcel.owner}</p>
                    </div>
                  )}

                  {/* Grid of key metrics */}
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200">
                    {selectedParcel.acreage && (
                      <div>
                        <span className="text-gray-500 text-xs">Acreage:</span>
                        <p className="font-medium">{selectedParcel.acreage.toFixed(2)} ac</p>
                      </div>
                    )}
                    {selectedParcel.zoning && (
                      <div>
                        <span className="text-gray-500 text-xs">Zoning:</span>
                        <p className="font-medium">{selectedParcel.zoning}</p>
                      </div>
                    )}
                    {selectedParcel.land_use && (
                      <div>
                        <span className="text-gray-500 text-xs">Land Use:</span>
                        <p className="font-medium">{selectedParcel.land_use}</p>
                      </div>
                    )}
                    {selectedParcel.year_built && (
                      <div>
                        <span className="text-gray-500 text-xs">Year Built:</span>
                        <p className="font-medium">{selectedParcel.year_built}</p>
                      </div>
                    )}
                    {selectedParcel.building_sqft && (
                      <div>
                        <span className="text-gray-500 text-xs">Building Sqft:</span>
                        <p className="font-medium">{selectedParcel.building_sqft.toLocaleString()}</p>
                      </div>
                    )}
                    {selectedParcel.total_value && (
                      <div>
                        <span className="text-gray-500 text-xs">Total Value:</span>
                        <p className="font-medium">${selectedParcel.total_value.toLocaleString()}</p>
                      </div>
                    )}
                  </div>

                  {/* Sale info */}
                  {(selectedParcel.sale_price || selectedParcel.sale_date) && (
                    <div className="pt-2 border-t border-gray-200">
                      <span className="text-gray-500 text-xs">Last Sale:</span>
                      <p className="font-medium">
                        {selectedParcel.sale_price && `$${selectedParcel.sale_price.toLocaleString()}`}
                        {selectedParcel.sale_price && selectedParcel.sale_date && ' on '}
                        {selectedParcel.sale_date}
                      </p>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </InfoWindowF>
        )}
      </GoogleMap>
    </div>
  );
}
