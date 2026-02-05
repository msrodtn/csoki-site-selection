/**
 * Competitor Arc Layer
 *
 * Visualizes connections between a potential site and nearby competitors.
 * Uses deck.gl's ArcLayer for curved arcs.
 *
 * Features:
 * - Arcs from site to each competitor
 * - Color-coded by travel time (green=close, yellow=medium, red=far)
 * - Auto-appears when competitor analysis data is available
 */

import { useMemo } from 'react';
import { ArcLayer } from '@deck.gl/layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { Store, CompetitorWithTravelTime } from '../../../types/store';

// Default source color (green for the potential site)
const SOURCE_COLOR: [number, number, number] = [46, 204, 113];

export interface CompetitorArcLayerProps {
  siteLocation: [number, number];  // [lng, lat]
  competitors: (Store | CompetitorWithTravelTime)[];
  visible?: boolean;
  arcWidth?: number;
  tilt?: number;  // Arc curvature (0 = straight line)
  greatCircle?: boolean;  // Use great circle arcs
  animated?: boolean;
  highlightedCompetitorId?: number | null;
  onClick?: (info: any) => void;
  onHover?: (info: any) => void;
}

/**
 * Get RGB color for a brand
 */
/**
 * Create a CompetitorArcLayer instance
 */
export function createCompetitorArcLayer({
  siteLocation,
  competitors,
  visible = true,
  arcWidth = 2,
  tilt = 30,
  greatCircle = true,
  animated = false,
  highlightedCompetitorId = null,
  onClick,
  onHover,
}: CompetitorArcLayerProps): ArcLayer<Store | CompetitorWithTravelTime> {
  // Filter out competitors without coordinates
  const validCompetitors = competitors.filter(
    (c) => c.latitude != null && c.longitude != null
  );

  return new ArcLayer<Store | CompetitorWithTravelTime>({
    id: 'competitor-arcs',
    data: validCompetitors,
    visible,
    pickable: true,

    // All arcs start from the site location
    getSourcePosition: () => siteLocation,

    // Each arc ends at the competitor location
    getTargetPosition: (d) => [d.longitude!, d.latitude!],

    // Source color is always green (site)
    getSourceColor: () => [...SOURCE_COLOR, 200] as [number, number, number, number],

    // Target color based on travel time (green=close, yellow=medium, red=far)
    getTargetColor: (d) => {
      const isHighlighted = highlightedCompetitorId === d.id;
      const alpha = isHighlighted ? 255 : 220;

      // Color by travel time for clear visual feedback
      if ('travel_time_minutes' in d && d.travel_time_minutes != null) {
        const minutes = d.travel_time_minutes;
        if (minutes < 5) return [34, 197, 94, alpha];     // Green - very close
        if (minutes < 15) return [234, 179, 8, alpha];    // Yellow - medium
        return [239, 68, 68, alpha];                       // Red - far
      }

      // Gray fallback when no travel time data
      return [107, 114, 128, isHighlighted ? 255 : 180];
    },

    // Arc width (wider for highlighted)
    getWidth: (d) => {
      const isHighlighted = highlightedCompetitorId === d.id;
      return isHighlighted ? arcWidth * 2 : arcWidth;
    },

    // Fixed low arc height for cleaner flat appearance
    getHeight: 0.3,

    // Arc curvature
    getTilt: tilt,

    // Great circle for long distances
    greatCircle,

    // Event handlers
    onClick: onClick ? (info) => onClick(info) : undefined,
    onHover: onHover ? (info) => onHover(info) : undefined,

    // Animation settings
    ...(animated
      ? {
          // Add animation parameters if needed
          updateTriggers: {
            getSourceColor: [Date.now()],
            getTargetColor: [highlightedCompetitorId, Date.now()],
          },
        }
      : {}),
  });
}

/**
 * Create a MapboxOverlay with arc layers
 */
export function createArcOverlay(layers: ArcLayer<any>[]): MapboxOverlay {
  return new MapboxOverlay({
    layers,
    interleaved: true,
  });
}

/**
 * React hook for creating the competitor arc layer
 */
export function useCompetitorArcLayer({
  mapRef,
  siteLocation,
  competitors,
  visible = true,
  ...options
}: CompetitorArcLayerProps & { mapRef: React.RefObject<any> }) {
  // Create the layer instance
  const layer = useMemo(() => {
    if (!competitors || competitors.length === 0) return null;
    return createCompetitorArcLayer({ siteLocation, competitors, visible, ...options });
  }, [siteLocation, competitors, visible, options]);

  return layer;
}

/**
 * Get arc statistics for display
 */
export function getArcStats(
  _siteLocation: [number, number],
  competitors: (Store | CompetitorWithTravelTime)[]
): {
  totalCompetitors: number;
  competitorsByBrand: Record<string, number>;
  avgTravelTime: number | null;
  closestCompetitor: (Store | CompetitorWithTravelTime) | null;
} {
  if (!competitors || competitors.length === 0) {
    return {
      totalCompetitors: 0,
      competitorsByBrand: {},
      avgTravelTime: null,
      closestCompetitor: null,
    };
  }

  // Count by brand
  const competitorsByBrand = competitors.reduce<Record<string, number>>((acc, c) => {
    acc[c.brand] = (acc[c.brand] || 0) + 1;
    return acc;
  }, {});

  // Calculate average travel time if available
  const competitorsWithTime = competitors.filter(
    (c): c is CompetitorWithTravelTime =>
      'travel_time_minutes' in c && c.travel_time_minutes != null
  );

  const avgTravelTime =
    competitorsWithTime.length > 0
      ? competitorsWithTime.reduce((sum, c) => sum + (c.travel_time_minutes || 0), 0) /
        competitorsWithTime.length
      : null;

  // Find closest competitor
  const closestCompetitor =
    competitorsWithTime.length > 0
      ? competitorsWithTime.reduce((closest, c) =>
          (c.travel_time_minutes || Infinity) < (closest.travel_time_minutes || Infinity)
            ? c
            : closest
        )
      : null;

  return {
    totalCompetitors: competitors.length,
    competitorsByBrand,
    avgTravelTime,
    closestCompetitor,
  };
}

export default createCompetitorArcLayer;
