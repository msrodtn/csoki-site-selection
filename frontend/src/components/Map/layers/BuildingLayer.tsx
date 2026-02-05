/**
 * Building Layer Component
 *
 * Renders interactive building footprints using Mapbox's built-in composite tileset.
 * Features hover/select states via feature state and reverse geocoding on click.
 */

import { useCallback, useEffect, useRef } from 'react';
import type { MapRef } from '@vis.gl/react-mapbox';
import type { MapMouseEvent } from 'mapbox-gl';
import * as turf from '@turf/turf';
import {
  BUILDING_SOURCE_ID,
  BUILDING_SOURCE_LAYER,
  BUILDING_LAYER_ID,
  BUILDING_OUTLINE_LAYER_ID,
  buildingFillLayerSpec,
  buildingOutlineLayerSpec,
  BUILDING_FEATURE_STATE_HOVER,
  BUILDING_FEATURE_STATE_SELECTED,
} from '../../../utils/building-layer-styles';

export interface BuildingInfo {
  id: number;
  center: [number, number];
  address?: string;
  height?: number;
  type?: string;
  geometry?: GeoJSON.Geometry;
}

export interface BuildingLayerProps {
  /** Reference to the Mapbox map instance */
  map: MapRef | null;
  /** Whether the building layer is visible */
  visible?: boolean;
  /** Callback when a building is clicked */
  onBuildingClick?: (building: BuildingInfo) => void;
  /** Callback when a building is hovered */
  onBuildingHover?: (building: BuildingInfo | null) => void;
}

/**
 * Get the centroid of a building feature
 */
function getBuildingCenter(feature: GeoJSON.Feature): [number, number] | null {
  if (!feature.geometry) return null;

  try {
    const centroid = turf.centroid(feature);
    return centroid.geometry.coordinates as [number, number];
  } catch {
    return null;
  }
}

/**
 * Convert a map feature to BuildingInfo
 */
function featureToBuildingInfo(feature: GeoJSON.Feature): BuildingInfo | null {
  if (feature.id === undefined) return null;

  const center = getBuildingCenter(feature);
  if (!center) return null;

  return {
    id: feature.id as number,
    center,
    height: feature.properties?.height,
    type: feature.properties?.type,
    geometry: feature.geometry,
  };
}

/**
 * BuildingLayer renders interactive building footprints
 */
export function BuildingLayer({
  map,
  visible = true,
  onBuildingClick,
  onBuildingHover,
}: BuildingLayerProps) {
  // Track hovered and selected building IDs
  const hoveredBuildingIdRef = useRef<number | null>(null);
  const selectedBuildingIdRef = useRef<number | null>(null);
  const layersAddedRef = useRef(false);

  /**
   * Set feature state for a building
   */
  const setFeatureState = useCallback(
    (
      featureId: number | null,
      state: { [key: string]: boolean }
    ) => {
      if (!map || featureId === null) return;

      const mapInstance = map.getMap();
      if (!mapInstance.getSource(BUILDING_SOURCE_ID)) return;

      try {
        mapInstance.setFeatureState(
          {
            source: BUILDING_SOURCE_ID,
            sourceLayer: BUILDING_SOURCE_LAYER,
            id: featureId,
          },
          state
        );
      } catch (e) {
        // Feature may not exist yet
      }
    },
    [map]
  );

  /**
   * Handle mouse move on buildings
   */
  const handleMouseMove = useCallback(
    (e: MapMouseEvent) => {
      if (!map || !visible) return;

      const mapInstance = map.getMap();
      const features = e.features;
      const newHoveredFeature = features?.find((f) => f.id !== undefined);

      // Skip if same building
      if (hoveredBuildingIdRef.current === newHoveredFeature?.id) {
        return;
      }

      // Clear previous hover state
      if (hoveredBuildingIdRef.current !== null) {
        setFeatureState(hoveredBuildingIdRef.current, {
          [BUILDING_FEATURE_STATE_HOVER]: false,
        });
      }

      // Set new hover state (but not if it's selected)
      if (
        newHoveredFeature?.id !== undefined &&
        newHoveredFeature.id !== selectedBuildingIdRef.current
      ) {
        setFeatureState(newHoveredFeature.id as number, {
          [BUILDING_FEATURE_STATE_HOVER]: true,
        });
      }

      hoveredBuildingIdRef.current = (newHoveredFeature?.id as number) ?? null;

      // Update cursor
      const container = mapInstance.getCanvasContainer();
      if (newHoveredFeature) {
        container.style.cursor = 'pointer';
      }

      // Notify parent
      if (onBuildingHover) {
        if (newHoveredFeature) {
          const buildingInfo = featureToBuildingInfo(newHoveredFeature);
          onBuildingHover(buildingInfo);
        } else {
          onBuildingHover(null);
        }
      }
    },
    [map, visible, onBuildingHover, setFeatureState]
  );

  /**
   * Handle mouse leave from buildings
   */
  const handleMouseLeave = useCallback(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    // Clear hover state
    if (hoveredBuildingIdRef.current !== null) {
      setFeatureState(hoveredBuildingIdRef.current, {
        [BUILDING_FEATURE_STATE_HOVER]: false,
      });
    }

    hoveredBuildingIdRef.current = null;

    // Reset cursor
    const container = mapInstance.getCanvasContainer();
    container.style.cursor = '';

    // Notify parent
    if (onBuildingHover) {
      onBuildingHover(null);
    }
  }, [map, onBuildingHover, setFeatureState]);

  /**
   * Handle click on building
   */
  const handleClick = useCallback(
    (e: MapMouseEvent) => {
      if (!onBuildingClick || !visible) return;

      const clickedFeature = e.features?.find((f) => f.id !== undefined);
      if (!clickedFeature) return;

      // Clear previous selection
      if (selectedBuildingIdRef.current !== null) {
        setFeatureState(selectedBuildingIdRef.current, {
          [BUILDING_FEATURE_STATE_SELECTED]: false,
        });
      }

      // Set new selection
      const newId = clickedFeature.id as number;
      selectedBuildingIdRef.current = newId;
      setFeatureState(newId, {
        [BUILDING_FEATURE_STATE_SELECTED]: true,
        [BUILDING_FEATURE_STATE_HOVER]: false,
      });

      const buildingInfo = featureToBuildingInfo(clickedFeature);
      if (buildingInfo) {
        onBuildingClick(buildingInfo);
        e.originalEvent.stopPropagation();
      }
    },
    [visible, onBuildingClick, setFeatureState]
  );

  /**
   * Add building layers to map
   */
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    const addLayers = () => {
      if (layersAddedRef.current) return;
      if (!mapInstance.isStyleLoaded()) return;

      // Add fill layer
      if (!mapInstance.getLayer(BUILDING_LAYER_ID)) {
        mapInstance.addLayer({
          ...buildingFillLayerSpec,
          source: BUILDING_SOURCE_ID,
        } as mapboxgl.FillLayerSpecification);
      }

      // Add outline layer
      if (!mapInstance.getLayer(BUILDING_OUTLINE_LAYER_ID)) {
        mapInstance.addLayer({
          ...buildingOutlineLayerSpec,
          source: BUILDING_SOURCE_ID,
        } as mapboxgl.FillLayerSpecification);
      }

      layersAddedRef.current = true;
    };

    // Try immediately, then on style load
    if (mapInstance.isStyleLoaded()) {
      addLayers();
    }

    mapInstance.on('style.load', addLayers);

    return () => {
      mapInstance.off('style.load', addLayers);

      // Remove layers on cleanup
      if (mapInstance.getLayer(BUILDING_OUTLINE_LAYER_ID)) {
        mapInstance.removeLayer(BUILDING_OUTLINE_LAYER_ID);
      }
      if (mapInstance.getLayer(BUILDING_LAYER_ID)) {
        mapInstance.removeLayer(BUILDING_LAYER_ID);
      }

      layersAddedRef.current = false;
    };
  }, [map]);

  /**
   * Update layer visibility
   */
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();
    const visibility = visible ? 'visible' : 'none';

    const updateVisibility = () => {
      if (mapInstance.getLayer(BUILDING_LAYER_ID)) {
        mapInstance.setLayoutProperty(BUILDING_LAYER_ID, 'visibility', visibility);
      }
      if (mapInstance.getLayer(BUILDING_OUTLINE_LAYER_ID)) {
        mapInstance.setLayoutProperty(BUILDING_OUTLINE_LAYER_ID, 'visibility', visibility);
      }
    };

    // Try immediately and after a short delay (for async layer creation)
    updateVisibility();
    const timeout = setTimeout(updateVisibility, 100);

    return () => clearTimeout(timeout);
  }, [map, visible]);

  /**
   * Set up mouse event listeners
   */
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    mapInstance.on('mousemove', BUILDING_LAYER_ID, handleMouseMove);
    mapInstance.on('mouseleave', BUILDING_LAYER_ID, handleMouseLeave);
    mapInstance.on('click', BUILDING_LAYER_ID, handleClick);

    return () => {
      mapInstance.off('mousemove', BUILDING_LAYER_ID, handleMouseMove);
      mapInstance.off('mouseleave', BUILDING_LAYER_ID, handleMouseLeave);
      mapInstance.off('click', BUILDING_LAYER_ID, handleClick);
    };
  }, [map, handleMouseMove, handleMouseLeave, handleClick]);

  // Render nothing - layers are added imperatively
  return null;
}

export default BuildingLayer;
