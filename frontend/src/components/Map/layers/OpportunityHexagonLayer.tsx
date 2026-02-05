/**
 * Opportunity Hexagon Layer
 *
 * 3D hexbin aggregation layer for visualizing property opportunity concentration.
 * Uses deck.gl's HexagonLayer for GPU-accelerated rendering.
 *
 * Features:
 * - Aggregates properties into hexagonal bins
 * - Height represents opportunity score density
 * - Color gradient from green (low) to red (high opportunity)
 * - Configurable radius and elevation scale
 */

import { useEffect, useMemo, useCallback } from 'react';
import { HexagonLayer } from '@deck.gl/aggregation-layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { PropertyListing } from '../../../types/store';

// Opportunity score color range (green → red)
const OPPORTUNITY_COLOR_RANGE: [number, number, number][] = [
  [34, 197, 94],    // Green - low opportunity density
  [132, 204, 22],   // Lime
  [234, 179, 8],    // Yellow
  [249, 115, 22],   // Orange
  [239, 68, 68],    // Red - high opportunity density
];

// Competition density color range (blue → red)
const COMPETITION_COLOR_RANGE: [number, number, number][] = [
  [59, 130, 246],   // Blue - low competition
  [99, 102, 241],   // Indigo
  [168, 85, 247],   // Purple
  [236, 72, 153],   // Pink
  [239, 68, 68],    // Red - high competition
];

export interface OpportunityHexagonLayerProps {
  data: PropertyListing[];
  visible?: boolean;
  radius?: number;  // Hexagon radius in meters
  elevationScale?: number;
  coverage?: number;  // 0-1, how much of hex is filled
  upperPercentile?: number;  // Percentile for color scaling
  colorMode?: 'opportunity' | 'competition';
  onClick?: (info: any) => void;
  onHover?: (info: any) => void;
}

/**
 * Create an OpportunityHexagonLayer instance
 */
export function createOpportunityHexagonLayer({
  data,
  visible = true,
  radius = 500,
  elevationScale = 50,
  coverage = 0.8,
  upperPercentile = 95,
  colorMode = 'opportunity',
  onClick,
  onHover,
}: OpportunityHexagonLayerProps): HexagonLayer<PropertyListing> {
  const colorRange = colorMode === 'opportunity'
    ? OPPORTUNITY_COLOR_RANGE
    : COMPETITION_COLOR_RANGE;

  return new HexagonLayer<PropertyListing>({
    id: `opportunity-hexagons-${colorMode}`,
    data,
    visible,
    pickable: true,
    extruded: true,
    radius,
    elevationScale,
    coverage,
    upperPercentile,
    colorRange,

    // Position accessor
    getPosition: (d: PropertyListing) => [d.longitude, d.latitude],

    // Weight by opportunity score for color
    getColorWeight: (d: PropertyListing) => d.opportunity_score || 0,
    colorAggregation: 'SUM',

    // Weight by opportunity score for elevation
    getElevationWeight: (d: PropertyListing) => d.opportunity_score || 0,
    elevationAggregation: 'SUM',

    // Material for 3D effect
    material: {
      ambient: 0.64,
      diffuse: 0.6,
      shininess: 32,
      specularColor: [51, 51, 51],
    },

    // Transitions for smooth updates
    transitions: {
      elevationScale: 500,
    },

    // Event handlers
    onClick: onClick ? (info) => onClick(info) : undefined,
    onHover: onHover ? (info) => onHover(info) : undefined,
  });
}

/**
 * Create a MapboxOverlay for deck.gl layers
 */
export function createDeckOverlay(layers: any[]): MapboxOverlay {
  return new MapboxOverlay({
    layers,
    interleaved: true,
  });
}

/**
 * React hook for managing the Opportunity Hexagon Layer
 */
export function useOpportunityHexagonLayer({
  mapRef,
  data,
  visible = true,
  ...options
}: OpportunityHexagonLayerProps & { mapRef: React.RefObject<any> }) {
  // Create the layer instance
  const layer = useMemo(() => {
    if (!data || data.length === 0) return null;
    return createOpportunityHexagonLayer({ data, visible, ...options });
  }, [data, visible, options]);

  // Add overlay to map
  useEffect(() => {
    if (!mapRef.current || !layer) return;

    const map = mapRef.current.getMap();
    if (!map) return;

    const overlay = createDeckOverlay([layer]);
    map.addControl(overlay);

    return () => {
      map.removeControl(overlay);
    };
  }, [mapRef, layer]);

  return layer;
}

/**
 * Get hexagon layer statistics for display
 */
export function getHexagonStats(data: PropertyListing[]): {
  totalProperties: number;
  avgOpportunityScore: number;
  maxOpportunityScore: number;
  propertiesWithSignals: number;
} {
  if (!data || data.length === 0) {
    return {
      totalProperties: 0,
      avgOpportunityScore: 0,
      maxOpportunityScore: 0,
      propertiesWithSignals: 0,
    };
  }

  const scores = data.map((p) => p.opportunity_score || 0);
  const propertiesWithSignals = data.filter(
    (p) => p.opportunity_signals && p.opportunity_signals.length > 0
  ).length;

  return {
    totalProperties: data.length,
    avgOpportunityScore: Math.round(
      scores.reduce((sum, s) => sum + s, 0) / scores.length
    ),
    maxOpportunityScore: Math.max(...scores),
    propertiesWithSignals,
  };
}

export default createOpportunityHexagonLayer;
