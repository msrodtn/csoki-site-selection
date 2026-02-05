/**
 * Competitor Arc Layer
 *
 * Visualizes connections between a potential site and nearby competitors.
 * Uses deck.gl's ArcLayer for animated, curved arcs.
 *
 * Features:
 * - Arcs from site to each competitor
 * - Color-coded by brand
 * - Arc height based on distance
 * - Animation support for highlighting
 */

import { useMemo } from 'react';
import { ArcLayer } from '@deck.gl/layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { Store, BrandKey, CompetitorWithTravelTime } from '../../../types/store';
import { BRAND_COLORS_RGB, getTravelTimeColorRGB } from '../../../utils/mapbox-expressions';

// Default source color (green for the potential site)
const SOURCE_COLOR: [number, number, number] = [46, 204, 113];

// Arc height multiplier based on distance
const ARC_HEIGHT_FACTOR = 0.5;

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
function getBrandColor(brand: string): [number, number, number] {
  return BRAND_COLORS_RGB[brand as BrandKey] || [102, 102, 102];
}

/**
 * Calculate arc height based on travel time or distance
 * Longer travel times = higher arcs (more curved)
 */
function getArcHeight(
  competitor: Store | CompetitorWithTravelTime,
  siteLocation: [number, number]
): number {
  // Use actual travel time from Matrix API if available
  if ('travel_time_minutes' in competitor && competitor.travel_time_minutes != null) {
    // Scale: 5 min = 0.25 height, 10 min = 0.5, 20 min = 1.0 (max)
    return Math.min(competitor.travel_time_minutes / 20, 1) * ARC_HEIGHT_FACTOR;
  }

  // Use distance if available
  if ('distance_miles' in competitor && competitor.distance_miles != null) {
    // Scale: 1 mile = 0.1, 5 miles = 0.5, 10+ miles = 1.0
    return Math.min(competitor.distance_miles / 10, 1) * ARC_HEIGHT_FACTOR;
  }

  // Fall back to rough lat/lng distance calculation
  if (competitor.latitude && competitor.longitude) {
    const dlat = Math.abs(competitor.latitude - siteLocation[1]);
    const dlng = Math.abs(competitor.longitude - siteLocation[0]);
    const distance = Math.sqrt(dlat * dlat + dlng * dlng);
    return Math.min(distance * 10, 1) * ARC_HEIGHT_FACTOR;
  }

  return 0.2; // Default height
}

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

    // Target color based on travel time (if available) or brand
    getTargetColor: (d) => {
      const isHighlighted = highlightedCompetitorId === d.id;

      // Use travel time color if available (green=fast, red=slow)
      if ('travel_time_minutes' in d && d.travel_time_minutes != null) {
        const color = getTravelTimeColorRGB(d.travel_time_minutes);
        if (isHighlighted) {
          return [color[0], color[1], color[2], 255] as [number, number, number, number];
        }
        return color;
      }

      // Fall back to brand color
      const alpha = isHighlighted ? 255 : 180;
      return [...getBrandColor(d.brand), alpha] as [number, number, number, number];
    },

    // Arc width (wider for highlighted)
    getWidth: (d) => {
      const isHighlighted = highlightedCompetitorId === d.id;
      return isHighlighted ? arcWidth * 2 : arcWidth;
    },

    // Arc height based on distance/travel time
    getHeight: (d) => getArcHeight(d, siteLocation) * 0.02,

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
  siteLocation: [number, number],
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
