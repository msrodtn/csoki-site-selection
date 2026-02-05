/**
 * Custom Geolocation Control
 *
 * Provides a locate-me button with accuracy circle visualization.
 * Shows user's current location with a pulsing dot and accuracy radius.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { MapRef } from '@vis.gl/react-mapbox';
import type { GeoJSONSource } from 'mapbox-gl';
import * as turf from '@turf/turf';

export interface GeolocateControlProps {
  /** Reference to the Mapbox map instance */
  map: MapRef | null;
  /** Position on the map */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  /** Callback when location is obtained */
  onGeolocate?: (position: GeolocationPosition) => void;
  /** Callback when geolocation fails */
  onError?: (error: GeolocationPositionError) => void;
  /** Whether to track location continuously */
  trackUserLocation?: boolean;
  /** Zoom level when flying to location */
  flyToZoom?: number;
}

// Source and layer IDs for geolocation visualization
const GEOLOCATE_SOURCE_ID = 'geolocate-source';
const GEOLOCATE_ACCURACY_LAYER_ID = 'geolocate-accuracy';
const GEOLOCATE_DOT_LAYER_ID = 'geolocate-dot';
const GEOLOCATE_DOT_PULSE_LAYER_ID = 'geolocate-dot-pulse';

/**
 * Position styles for control placement
 */
const positionStyles: Record<string, React.CSSProperties> = {
  'top-left': { top: 120, left: 10 },
  'top-right': { top: 120, right: 10 },
  'bottom-left': { bottom: 30, left: 10 },
  'bottom-right': { bottom: 30, right: 10 },
};

type GeolocateState = 'idle' | 'loading' | 'active' | 'error';

/**
 * Create GeoJSON for user location with accuracy circle
 */
function createLocationGeoJSON(
  lng: number,
  lat: number,
  accuracy: number
): GeoJSON.FeatureCollection {
  // Create accuracy circle (radius in meters)
  const accuracyCircle = turf.circle([lng, lat], accuracy / 1000, {
    units: 'kilometers',
    steps: 64,
  });

  // Create center point
  const centerPoint: GeoJSON.Feature = {
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [lng, lat],
    },
    properties: {
      type: 'center',
    },
  };

  return {
    type: 'FeatureCollection',
    features: [
      { ...accuracyCircle, properties: { type: 'accuracy' } },
      centerPoint,
    ],
  };
}

/**
 * GeolocateControl provides location tracking with accuracy visualization
 */
export function GeolocateControl({
  map,
  position = 'top-right',
  onGeolocate,
  onError,
  trackUserLocation = false,
  flyToZoom = 15,
}: GeolocateControlProps) {
  const [state, setState] = useState<GeolocateState>('idle');
  const watchIdRef = useRef<number | null>(null);
  const layersAddedRef = useRef(false);

  /**
   * Add geolocation layers to map
   */
  const addLayers = useCallback(() => {
    if (!map || layersAddedRef.current) return;

    const mapInstance = map.getMap();
    if (!mapInstance.isStyleLoaded()) return;

    // Add source
    if (!mapInstance.getSource(GEOLOCATE_SOURCE_ID)) {
      mapInstance.addSource(GEOLOCATE_SOURCE_ID, {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      });
    }

    // Add accuracy circle layer
    if (!mapInstance.getLayer(GEOLOCATE_ACCURACY_LAYER_ID)) {
      mapInstance.addLayer({
        id: GEOLOCATE_ACCURACY_LAYER_ID,
        type: 'fill',
        source: GEOLOCATE_SOURCE_ID,
        filter: ['==', ['get', 'type'], 'accuracy'],
        paint: {
          'fill-color': '#3B82F6',
          'fill-opacity': 0.15,
        },
      });
    }

    // Add pulsing outer ring
    if (!mapInstance.getLayer(GEOLOCATE_DOT_PULSE_LAYER_ID)) {
      mapInstance.addLayer({
        id: GEOLOCATE_DOT_PULSE_LAYER_ID,
        type: 'circle',
        source: GEOLOCATE_SOURCE_ID,
        filter: ['==', ['get', 'type'], 'center'],
        paint: {
          'circle-radius': 20,
          'circle-color': '#3B82F6',
          'circle-opacity': 0.3,
          'circle-stroke-width': 0,
        },
      });
    }

    // Add center dot layer
    if (!mapInstance.getLayer(GEOLOCATE_DOT_LAYER_ID)) {
      mapInstance.addLayer({
        id: GEOLOCATE_DOT_LAYER_ID,
        type: 'circle',
        source: GEOLOCATE_SOURCE_ID,
        filter: ['==', ['get', 'type'], 'center'],
        paint: {
          'circle-radius': 8,
          'circle-color': '#3B82F6',
          'circle-stroke-width': 3,
          'circle-stroke-color': '#ffffff',
        },
      });
    }

    layersAddedRef.current = true;
  }, [map]);

  /**
   * Remove geolocation layers from map
   */
  const removeLayers = useCallback(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    if (mapInstance.getLayer(GEOLOCATE_DOT_LAYER_ID)) {
      mapInstance.removeLayer(GEOLOCATE_DOT_LAYER_ID);
    }
    if (mapInstance.getLayer(GEOLOCATE_DOT_PULSE_LAYER_ID)) {
      mapInstance.removeLayer(GEOLOCATE_DOT_PULSE_LAYER_ID);
    }
    if (mapInstance.getLayer(GEOLOCATE_ACCURACY_LAYER_ID)) {
      mapInstance.removeLayer(GEOLOCATE_ACCURACY_LAYER_ID);
    }
    if (mapInstance.getSource(GEOLOCATE_SOURCE_ID)) {
      mapInstance.removeSource(GEOLOCATE_SOURCE_ID);
    }

    layersAddedRef.current = false;
  }, [map]);

  /**
   * Update location on map
   */
  const updateLocation = useCallback(
    (position: GeolocationPosition) => {
      if (!map) return;

      const { longitude, latitude, accuracy } = position.coords;
      const mapInstance = map.getMap();

      // Ensure layers exist
      addLayers();

      // Update source data
      const source = mapInstance.getSource(GEOLOCATE_SOURCE_ID) as GeoJSONSource;
      if (source) {
        const geojson = createLocationGeoJSON(longitude, latitude, accuracy);
        source.setData(geojson);
      }

      // Fly to location on first fix
      if (state === 'loading') {
        mapInstance.flyTo({
          center: [longitude, latitude],
          zoom: flyToZoom,
          duration: 1500,
        });
      }

      setState('active');
      onGeolocate?.(position);
    },
    [map, state, flyToZoom, onGeolocate, addLayers]
  );

  /**
   * Handle geolocation error
   */
  const handleError = useCallback(
    (error: GeolocationPositionError) => {
      setState('error');
      onError?.(error);

      // Show user-friendly error message
      let message = 'Unable to get your location';
      switch (error.code) {
        case error.PERMISSION_DENIED:
          message = 'Location permission denied. Please enable location access.';
          break;
        case error.POSITION_UNAVAILABLE:
          message = 'Location information unavailable.';
          break;
        case error.TIMEOUT:
          message = 'Location request timed out.';
          break;
      }
      console.warn('Geolocation error:', message);
    },
    [onError]
  );

  /**
   * Start location tracking
   */
  const startTracking = useCallback(() => {
    if (!navigator.geolocation) {
      handleError({
        code: 2,
        message: 'Geolocation not supported',
        PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2,
        TIMEOUT: 3,
      } as GeolocationPositionError);
      return;
    }

    setState('loading');

    const options: PositionOptions = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    };

    if (trackUserLocation) {
      watchIdRef.current = navigator.geolocation.watchPosition(
        updateLocation,
        handleError,
        options
      );
    } else {
      navigator.geolocation.getCurrentPosition(
        updateLocation,
        handleError,
        options
      );
    }
  }, [trackUserLocation, updateLocation, handleError]);

  /**
   * Stop location tracking
   */
  const stopTracking = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }

    removeLayers();
    setState('idle');
  }, [removeLayers]);

  /**
   * Handle button click
   */
  const handleClick = useCallback(() => {
    if (state === 'active') {
      stopTracking();
    } else if (state !== 'loading') {
      startTracking();
    }
  }, [state, startTracking, stopTracking]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
      removeLayers();
    };
  }, [removeLayers]);

  /**
   * Handle style changes
   */
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    const handleStyleLoad = () => {
      layersAddedRef.current = false;
      if (state === 'active') {
        addLayers();
      }
    };

    mapInstance.on('style.load', handleStyleLoad);

    return () => {
      mapInstance.off('style.load', handleStyleLoad);
    };
  }, [map, state, addLayers]);

  // Button styling based on state
  const getButtonStyles = () => {
    const base =
      'w-8 h-8 rounded-md shadow-md border flex items-center justify-center transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1';

    switch (state) {
      case 'loading':
        return `${base} bg-blue-50 border-blue-200 text-blue-600 animate-pulse`;
      case 'active':
        return `${base} bg-blue-500 border-blue-600 text-white`;
      case 'error':
        return `${base} bg-red-50 border-red-200 text-red-600`;
      default:
        return `${base} bg-white border-gray-200 text-gray-700 hover:bg-gray-50 active:bg-gray-100`;
    }
  };

  return (
    <div className="absolute z-10" style={positionStyles[position]}>
      <button
        onClick={handleClick}
        className={getButtonStyles()}
        title={state === 'active' ? 'Stop tracking' : 'Find my location'}
        aria-label={state === 'active' ? 'Stop tracking' : 'Find my location'}
        disabled={state === 'loading'}
      >
        {state === 'loading' ? (
          // Loading spinner
          <svg
            className="animate-spin"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="12" cy="12" r="10" opacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" />
          </svg>
        ) : (
          // Location icon
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill={state === 'active' ? 'currentColor' : 'none'}
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v4" />
            <path d="M12 18v4" />
            <path d="M2 12h4" />
            <path d="M18 12h4" />
          </svg>
        )}
      </button>
    </div>
  );
}

export default GeolocateControl;
