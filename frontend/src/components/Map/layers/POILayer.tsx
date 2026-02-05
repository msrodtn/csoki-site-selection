/**
 * POI Layer Component
 *
 * Renders Points of Interest using native Mapbox GL layers with feature state.
 * Replaces React <Marker> components for better performance.
 *
 * Features:
 * - Category-based coloring (anchors, restaurants, retail, etc.)
 * - Zoom-responsive sizing
 * - Hover/select states via feature state (no React re-renders)
 * - Visibility filtering from Zustand store
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { MapRef } from '@vis.gl/react-mapbox';
import type { Map as MapboxMap, GeoJSONSource } from 'mapbox-gl';
import { useMapStore } from '../../../store/useMapStore';
import type { POI, POICategory } from '../../../types/store';
import {
  POI_SOURCE_ID,
  POI_LAYER_ID,
  POI_HOVER_LAYER_ID,
  POI_SELECTED_LAYER_ID,
  poiCircleLayerSpec,
  poiHoverLayerSpec,
  poiSelectedLayerSpec,
  buildPOIVisibilityFilter,
} from '../../../utils/poi-layer-styles';
import { InteractiveMapLayer, type LayerStyle } from './InteractiveMapLayer';

// GeoJSON types for POI features
interface POIFeatureProperties {
  place_id: string;
  name: string;
  category: POICategory;
  address: string | null;
  rating: number | null;
  user_ratings_total: number | null;
}

interface POIFeature extends GeoJSON.Feature<GeoJSON.Point, POIFeatureProperties> {
  id: number; // Required for feature state
}

interface POIFeatureCollection extends GeoJSON.FeatureCollection<GeoJSON.Point, POIFeatureProperties> {
  features: POIFeature[];
}

export interface POILayerProps {
  /** Reference to the Mapbox map instance */
  map: MapRef | null;
  /** Array of POIs to display */
  pois: POI[];
  /** Callback when a POI is clicked */
  onPOIClick?: (poi: POI) => void;
  /** Callback when a POI is hovered */
  onPOIHover?: (poi: POI | null) => void;
}

/**
 * Convert POI array to GeoJSON FeatureCollection
 * Assigns numeric IDs required for feature state
 */
function poisToGeoJSON(pois: POI[]): POIFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: pois.map((poi, index) => ({
      type: 'Feature',
      id: index, // Numeric ID for feature state
      geometry: {
        type: 'Point',
        coordinates: [poi.longitude, poi.latitude],
      },
      properties: {
        place_id: poi.place_id,
        name: poi.name,
        category: poi.category,
        address: poi.address,
        rating: poi.rating,
        user_ratings_total: poi.user_ratings_total,
      },
    })),
  };
}

/**
 * Convert GeoJSON feature back to POI object
 */
function featureToPOI(feature: GeoJSON.Feature): POI | null {
  if (!feature.properties) return null;

  const coords = (feature.geometry as GeoJSON.Point).coordinates;
  return {
    place_id: feature.properties.place_id,
    name: feature.properties.name,
    category: feature.properties.category as POICategory,
    types: [], // Not stored in feature
    latitude: coords[1],
    longitude: coords[0],
    address: feature.properties.address,
    rating: feature.properties.rating,
    user_ratings_total: feature.properties.user_ratings_total,
  };
}

/**
 * Create layer style object with add/remove methods
 * @param initialData - Initial GeoJSON data to populate the source
 */
function createPOILayerStyle(initialData: POIFeatureCollection): LayerStyle {
  return {
    add: (map: MapboxMap) => {
      // Add source if not exists (with initial data)
      if (!map.getSource(POI_SOURCE_ID)) {
        map.addSource(POI_SOURCE_ID, {
          type: 'geojson',
          data: initialData,
        });
      } else {
        // Source exists, update data
        const source = map.getSource(POI_SOURCE_ID) as GeoJSONSource;
        source.setData(initialData);
      }

      // Add layers in order: base, hover, selected
      if (!map.getLayer(POI_LAYER_ID)) {
        map.addLayer({
          ...poiCircleLayerSpec,
          source: POI_SOURCE_ID,
        } as mapboxgl.CircleLayerSpecification);
      }

      if (!map.getLayer(POI_HOVER_LAYER_ID)) {
        map.addLayer({
          ...poiHoverLayerSpec,
          source: POI_SOURCE_ID,
        } as mapboxgl.CircleLayerSpecification);
      }

      if (!map.getLayer(POI_SELECTED_LAYER_ID)) {
        map.addLayer({
          ...poiSelectedLayerSpec,
          source: POI_SOURCE_ID,
        } as mapboxgl.CircleLayerSpecification);
      }
    },
    remove: (map: MapboxMap) => {
      // Remove layers first
      if (map.getLayer(POI_SELECTED_LAYER_ID)) {
        map.removeLayer(POI_SELECTED_LAYER_ID);
      }
      if (map.getLayer(POI_HOVER_LAYER_ID)) {
        map.removeLayer(POI_HOVER_LAYER_ID);
      }
      if (map.getLayer(POI_LAYER_ID)) {
        map.removeLayer(POI_LAYER_ID);
      }
      // Remove source
      if (map.getSource(POI_SOURCE_ID)) {
        map.removeSource(POI_SOURCE_ID);
      }
    },
  };
}

/**
 * POILayer renders POIs using native Mapbox GL layers
 */
export function POILayer({ map, pois, onPOIClick, onPOIHover }: POILayerProps) {
  // Get visibility state from Zustand store
  const visiblePOICategories = useMapStore((s) => s.visiblePOICategories);
  const hiddenPOIs = useMapStore((s) => s.hiddenPOIs);
  const selectedPOIId = useMapStore((s) => s.selectedPOIId);

  // Create mapping from place_id to feature index for selection sync
  const placeIdToIndexRef = useRef<Map<string, number>>(new Map());

  // Convert POIs to GeoJSON and update mapping
  const geojsonData = useMemo(() => {
    const data = poisToGeoJSON(pois);
    // Update place_id to index mapping
    placeIdToIndexRef.current.clear();
    pois.forEach((poi, index) => {
      placeIdToIndexRef.current.set(poi.place_id, index);
    });
    return data;
  }, [pois]);

  // Memoize layer style - recreate when data changes to ensure proper initialization
  const layerStyle = useMemo(() => createPOILayerStyle(geojsonData), [geojsonData]);

  // Get numeric feature ID for selected POI
  const selectedFeatureId = useMemo(() => {
    if (!selectedPOIId) return null;
    return placeIdToIndexRef.current.get(selectedPOIId) ?? null;
  }, [selectedPOIId]);

  // Build visibility filter
  const visibilityFilter = useMemo(() => {
    const categories = Array.from(visiblePOICategories);
    const hiddenIds = Array.from(hiddenPOIs);
    return buildPOIVisibilityFilter(categories as POICategory[], hiddenIds);
  }, [visiblePOICategories, hiddenPOIs]);

  // Update source data when POIs change (with retry for async source creation)
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    const maxAttempts = 20;

    const trySetData = () => {
      timeout = undefined;
      const source = mapInstance.getSource(POI_SOURCE_ID) as GeoJSONSource | undefined;

      if (source) {
        source.setData(geojsonData);
      } else if (attempts < maxAttempts) {
        attempts++;
        timeout = setTimeout(trySetData, 100);
      }
    };

    trySetData();

    return () => {
      if (timeout) clearTimeout(timeout);
    };
  }, [map, geojsonData]);

  // Update filter when visibility changes (with retry for async layer creation)
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    const maxAttempts = 20;

    const trySetFilter = () => {
      timeout = undefined;
      const layerExists = mapInstance.getLayer(POI_LAYER_ID);

      if (layerExists) {
        // Apply filter to all POI layers
        [POI_LAYER_ID, POI_HOVER_LAYER_ID, POI_SELECTED_LAYER_ID].forEach((layerId) => {
          if (mapInstance.getLayer(layerId)) {
            mapInstance.setFilter(layerId, visibilityFilter);
          }
        });
      } else if (attempts < maxAttempts) {
        attempts++;
        timeout = setTimeout(trySetFilter, 100);
      }
    };

    trySetFilter();

    return () => {
      if (timeout) clearTimeout(timeout);
    };
  }, [map, visibilityFilter]);

  // Handle feature click - convert back to POI and notify
  const handleFeatureClick = useCallback(
    (feature: GeoJSON.Feature) => {
      if (!onPOIClick) return;

      const poi = featureToPOI(feature);
      if (poi) {
        onPOIClick(poi);
      }
    },
    [onPOIClick]
  );

  // Handle feature hover - convert back to POI and notify
  const handleFeatureHover = useCallback(
    (feature: GeoJSON.Feature | null) => {
      if (!onPOIHover) return;

      if (feature) {
        const poi = featureToPOI(feature);
        onPOIHover(poi);
      } else {
        onPOIHover(null);
      }
    },
    [onPOIHover]
  );

  return (
    <InteractiveMapLayer
      map={map}
      sourceId={POI_SOURCE_ID}
      layerId={POI_LAYER_ID}
      layerStyle={layerStyle}
      selectedFeatureId={selectedFeatureId}
      onFeatureClick={handleFeatureClick}
      onFeatureHover={handleFeatureHover}
    />
  );
}

export default POILayer;
