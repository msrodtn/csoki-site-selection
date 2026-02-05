/**
 * Interactive Map Layer Component
 *
 * A reusable abstraction for managing interactive Mapbox GL layers with feature state.
 * Handles layer lifecycle, mouse events, and hover/select state management.
 *
 * Inspired by professional Mapbox layer patterns - uses feature state instead of
 * React state for hover/select, avoiding unnecessary re-renders.
 */

import { useCallback, useEffect, useRef } from 'react';
import type { MapRef } from '@vis.gl/react-mapbox';
import type { Map as MapboxMap, MapMouseEvent } from 'mapbox-gl';

export const FEATURE_STATE_HOVER = 'hover';
export const FEATURE_STATE_SELECTED = 'selected';
export const FEATURE_STATE_HIDDEN = 'hidden';

export interface LayerStyle {
  add: (map: MapboxMap) => void;
  remove: (map: MapboxMap) => void;
}

export interface InteractiveMapLayerProps {
  /** Reference to the Mapbox map instance */
  map: MapRef | null;
  /** Source ID for the layer */
  sourceId: string;
  /** Primary layer ID for event handling */
  layerId: string;
  /** Layer style configuration with add/remove methods */
  layerStyle: LayerStyle;
  /** Currently selected feature ID (or null) */
  selectedFeatureId: string | number | null;
  /** Callback when a feature is clicked */
  onFeatureClick?: (feature: GeoJSON.Feature) => void;
  /** Callback when a feature is hovered */
  onFeatureHover?: (feature: GeoJSON.Feature | null) => void;
}

/**
 * InteractiveMapLayer manages the lifecycle and interactions for a Mapbox layer
 * with feature state support for hover and selection.
 */
export function InteractiveMapLayer({
  map,
  sourceId,
  layerId,
  layerStyle,
  selectedFeatureId,
  onFeatureClick,
  onFeatureHover,
}: InteractiveMapLayerProps) {
  // Track hovered feature ID to clear state on leave
  const hoveredFeatureIdRef = useRef<string | number | null>(null);
  // Track selected feature ID for cleanup
  const selectedFeatureIdRef = useRef<string | number | null>(null);

  /**
   * Set feature state for hover
   */
  const setFeatureHoveredState = useCallback(
    (featureId: string | number | null, state: boolean) => {
      if (!map || featureId === null) return;

      const mapInstance = map.getMap();
      if (!mapInstance.getSource(sourceId)) return;

      mapInstance.setFeatureState(
        { source: sourceId, id: featureId },
        { [FEATURE_STATE_HOVER]: state }
      );
    },
    [map, sourceId]
  );

  /**
   * Set feature state for selection
   */
  const setFeatureSelectedState = useCallback(
    (featureId: string | number | null, state: boolean) => {
      if (!map || featureId === null) return;

      const mapInstance = map.getMap();
      if (!mapInstance.getSource(sourceId)) return;

      mapInstance.setFeatureState(
        { source: sourceId, id: featureId },
        {
          [FEATURE_STATE_SELECTED]: state,
          // Clear hover when selecting (prevents visual conflict)
          [FEATURE_STATE_HOVER]: false,
        }
      );
    },
    [map, sourceId]
  );

  /**
   * Handle mouse move/enter on layer
   */
  const handleFeatureHover = useCallback(
    (e: MapMouseEvent) => {
      if (!map) return;

      const mapInstance = map.getMap();
      const newHoveredFeature = e.features?.[0];

      // Skip if same feature
      if (hoveredFeatureIdRef.current === newHoveredFeature?.id) {
        return;
      }

      // Clear previous hover state
      if (hoveredFeatureIdRef.current !== null) {
        setFeatureHoveredState(hoveredFeatureIdRef.current, false);
      }

      // Set new hover state (but not if it's the selected feature)
      if (
        newHoveredFeature?.id !== undefined &&
        newHoveredFeature.id !== selectedFeatureIdRef.current
      ) {
        setFeatureHoveredState(newHoveredFeature.id, true);
      }

      hoveredFeatureIdRef.current = newHoveredFeature?.id ?? null;

      // Update cursor
      const container = mapInstance.getCanvasContainer();
      if (newHoveredFeature) {
        container.style.cursor = 'pointer';
      }

      // Notify parent
      if (onFeatureHover) {
        onFeatureHover(newHoveredFeature || null);
      }
    },
    [map, onFeatureHover, setFeatureHoveredState]
  );

  /**
   * Handle mouse leave from layer
   */
  const handleFeatureLeave = useCallback(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    // Clear hover state
    if (hoveredFeatureIdRef.current !== null) {
      setFeatureHoveredState(hoveredFeatureIdRef.current, false);
    }

    hoveredFeatureIdRef.current = null;

    // Reset cursor
    const container = mapInstance.getCanvasContainer();
    container.style.cursor = '';

    // Notify parent
    if (onFeatureHover) {
      onFeatureHover(null);
    }
  }, [map, onFeatureHover, setFeatureHoveredState]);

  /**
   * Handle click on layer
   */
  const handleFeatureClick = useCallback(
    (e: MapMouseEvent) => {
      if (!onFeatureClick) return;

      // Filter features with valid IDs (tile boundaries may have undefined IDs)
      const clickedFeature = e.features?.find((f) => f.id !== undefined);

      if (clickedFeature) {
        onFeatureClick(clickedFeature);
        // Prevent event from propagating to other layers
        e.originalEvent.stopPropagation();
      }
    },
    [onFeatureClick]
  );

  /**
   * Sync selected feature state when prop changes
   */
  useEffect(() => {
    if (!map) return;

    // Clear previous selection
    if (selectedFeatureIdRef.current !== null) {
      setFeatureSelectedState(selectedFeatureIdRef.current, false);
    }

    selectedFeatureIdRef.current = selectedFeatureId;

    // Set new selection (with retry for async source loading)
    if (selectedFeatureId !== null) {
      let timeout: ReturnType<typeof setTimeout> | undefined;

      const trySelectFeature = () => {
        timeout = undefined;
        const mapInstance = map.getMap();

        if (mapInstance.loaded() && mapInstance.getSource(sourceId)) {
          setFeatureSelectedState(selectedFeatureId, true);
        } else {
          timeout = setTimeout(trySelectFeature, 50);
        }
      };

      trySelectFeature();

      return () => {
        if (timeout) clearTimeout(timeout);
        setFeatureSelectedState(selectedFeatureId, false);
      };
    }
  }, [map, sourceId, selectedFeatureId, setFeatureSelectedState]);

  /**
   * Set up mouse event listeners
   */
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();

    mapInstance.on('mousemove', layerId, handleFeatureHover);
    mapInstance.on('mouseleave', layerId, handleFeatureLeave);
    mapInstance.on('click', layerId, handleFeatureClick);

    return () => {
      mapInstance.off('mousemove', layerId, handleFeatureHover);
      mapInstance.off('mouseleave', layerId, handleFeatureLeave);
      mapInstance.off('click', layerId, handleFeatureClick);
    };
  }, [map, layerId, handleFeatureClick, handleFeatureHover, handleFeatureLeave]);

  /**
   * Initialize and cleanup layer style
   */
  useEffect(() => {
    if (!map) return;

    const mapInstance = map.getMap();
    let timeout: ReturnType<typeof setTimeout> | undefined;

    const initializeLayer = () => {
      layerStyle.add(mapInstance);
      // Restore selection state after layer is added
      if (selectedFeatureIdRef.current !== null) {
        setFeatureSelectedState(selectedFeatureIdRef.current, true);
      }
    };

    const tryInitializeLayer = () => {
      timeout = undefined;
      if (mapInstance.loaded()) {
        initializeLayer();
      } else {
        timeout = setTimeout(tryInitializeLayer, 50);
      }
    };

    tryInitializeLayer();

    return () => {
      if (timeout) clearTimeout(timeout);
      layerStyle.remove(mapInstance);
    };
  }, [map, layerStyle, setFeatureSelectedState]);

  // This component renders nothing - layers are added imperatively to the map
  return null;
}

export default InteractiveMapLayer;
