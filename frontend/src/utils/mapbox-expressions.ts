/**
 * Mapbox GL JS Data-Driven Styling Expressions
 *
 * Reusable expression builders for dynamic visualization based on data properties.
 * These expressions use Mapbox's expression syntax for interpolation, conditional logic,
 * and property-based styling.
 *
 * @see https://docs.mapbox.com/help/glossary/data-driven-styling/
 */

import type { ExpressionSpecification } from 'mapbox-gl';
import { BRAND_COLORS, PROPERTY_TYPE_COLORS, type BrandKey, type PropertyType } from '../types/store';

// ============================================================================
// Opportunity Score Expressions
// ============================================================================

/**
 * Color gradient for opportunity scores (0-100)
 * Green (low opportunity) → Yellow (medium) → Red (high opportunity)
 */
export const opportunityScoreColor: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'opportunity_score'], 0],
  0, '#22C55E',   // Green - low opportunity
  25, '#84CC16',  // Lime
  50, '#EAB308',  // Yellow - medium opportunity
  75, '#F97316',  // Orange
  100, '#EF4444', // Red - high opportunity
];

/**
 * Opacity based on opportunity score - higher scores more visible
 */
export const opportunityScoreOpacity: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'opportunity_score'], 0],
  0, 0.4,
  50, 0.7,
  100, 1.0,
];

/**
 * Circle radius based on opportunity score - higher scores larger
 */
export const opportunityScoreRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'opportunity_score'], 0],
  0, 6,
  50, 10,
  100, 16,
];

/**
 * Heatmap weight based on opportunity score
 * Used to make high-opportunity areas "hotter" in heatmap visualization
 */
export const opportunityHeatmapWeight: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'opportunity_score'], 50],
  0, 0.5,
  50, 1,
  100, 2,
];

// ============================================================================
// Brand Color Expressions
// ============================================================================

/**
 * Match expression for brand colors
 * Returns the appropriate color for each brand key
 */
export const brandColorMatch: ExpressionSpecification = [
  'match',
  ['get', 'brand'],
  'csoki', BRAND_COLORS.csoki,
  'russell_cellular', BRAND_COLORS.russell_cellular,
  'verizon_corporate', BRAND_COLORS.verizon_corporate,
  'victra', BRAND_COLORS.victra,
  'tmobile', BRAND_COLORS.tmobile,
  'uscellular', BRAND_COLORS.uscellular,
  'wireless_zone', BRAND_COLORS.wireless_zone,
  'tcc', BRAND_COLORS.tcc,
  '#666666', // default fallback
];

/**
 * Brand colors as RGB arrays for deck.gl layers
 */
export const BRAND_COLORS_RGB: Record<BrandKey, [number, number, number]> = {
  csoki: [227, 24, 55],
  russell_cellular: [255, 107, 0],
  verizon_corporate: [205, 4, 11],
  victra: [0, 0, 0],
  tmobile: [226, 0, 116],
  uscellular: [0, 163, 224],
  wireless_zone: [124, 58, 237],
  tcc: [5, 150, 105],
};

// ============================================================================
// Property Type Expressions
// ============================================================================

/**
 * Match expression for property type colors
 */
export const propertyTypeColor: ExpressionSpecification = [
  'match',
  ['get', 'property_type'],
  'retail', PROPERTY_TYPE_COLORS.retail,
  'land', PROPERTY_TYPE_COLORS.land,
  'office', PROPERTY_TYPE_COLORS.office,
  'industrial', PROPERTY_TYPE_COLORS.industrial,
  'mixed_use', PROPERTY_TYPE_COLORS.mixed_use,
  '#6B7280', // default gray
];

/**
 * Property type colors as RGB arrays for deck.gl layers
 */
export const PROPERTY_TYPE_COLORS_RGB: Record<PropertyType, [number, number, number]> = {
  retail: [34, 197, 94],
  land: [161, 98, 7],
  office: [59, 130, 246],
  industrial: [107, 114, 128],
  mixed_use: [139, 92, 246],
  unknown: [156, 163, 175],
};

// ============================================================================
// Zoom-Based Expressions
// ============================================================================

/**
 * Marker size that increases with zoom level
 * Useful for keeping markers visible at all zoom levels
 */
export const zoomBasedMarkerSize: ExpressionSpecification = [
  'interpolate',
  ['exponential', 1.5],
  ['zoom'],
  6, 8,    // Zoomed out - small markers
  10, 12,
  14, 18,
  18, 24,  // Zoomed in - larger markers
];

/**
 * Icon size for symbol layers (normalized 0-1 scale)
 */
export const zoomBasedIconSize: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  6, 0.5,
  10, 0.75,
  14, 1.0,
  18, 1.25,
];

/**
 * Text size that scales with zoom
 */
export const zoomBasedTextSize: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  8, 10,
  12, 12,
  16, 14,
];

/**
 * Heatmap intensity that increases with zoom
 */
export const zoomBasedHeatmapIntensity: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  0, 1,
  15, 3,
];

/**
 * Heatmap radius that increases with zoom
 */
export const zoomBasedHeatmapRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  0, 2,
  15, 30,
];

/**
 * Heatmap opacity that decreases at higher zoom levels
 * (to reveal individual markers underneath)
 */
export const zoomBasedHeatmapOpacity: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  7, 0.8,
  15, 0.3,
];

// ============================================================================
// Competition Density Heatmap
// ============================================================================

/**
 * Competition density heatmap color ramp
 * Green (sparse) → Yellow → Orange → Red (dense)
 */
export const competitionDensityHeatmapColor: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0, 'rgba(0, 255, 0, 0)',
  0.2, 'rgba(0, 255, 0, 0.5)',
  0.4, 'rgba(255, 255, 0, 0.7)',
  0.6, 'rgba(255, 165, 0, 0.8)',
  0.8, 'rgba(255, 0, 0, 0.9)',
  1, 'rgba(255, 0, 0, 1)',
];

/**
 * Opportunity-weighted heatmap color ramp
 * Shows opportunity concentration rather than just point density
 */
export const opportunityHeatmapColor: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0, 'rgba(33, 150, 243, 0)',       // Transparent
  0.2, 'rgba(76, 175, 80, 0.5)',    // Green - low opportunity density
  0.4, 'rgba(139, 195, 74, 0.6)',   // Light green
  0.6, 'rgba(255, 235, 59, 0.7)',   // Yellow - medium
  0.8, 'rgba(255, 152, 0, 0.85)',   // Orange - high
  1, 'rgba(244, 67, 54, 1)',        // Red - critical opportunity zone
];

// ============================================================================
// Activity Node Heatmap
// ============================================================================

/**
 * Activity node heatmap color ramp
 * Green (low activity) -> Yellow (medium) -> Red (high/hot)
 */
export const activityNodeHeatmapColor: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0, 'rgba(0, 128, 0, 0)',
  0.15, 'rgba(0, 200, 0, 0.4)',
  0.3, 'rgba(128, 255, 0, 0.55)',
  0.5, 'rgba(255, 255, 0, 0.7)',
  0.7, 'rgba(255, 165, 0, 0.85)',
  0.85, 'rgba(255, 69, 0, 0.92)',
  1.0, 'rgba(255, 0, 0, 1.0)',
];

/**
 * Build heatmap paint for activity nodes.
 * Uses the `weight` property from each feature for intensity contribution,
 * so higher-traffic POIs (big box = 3.0) contribute more than small shops (0.8).
 */
export function buildActivityNodeHeatmapPaint(): Record<string, ExpressionSpecification> {
  return {
    'heatmap-weight': [
      'interpolate',
      ['linear'],
      ['coalesce', ['get', 'weight'], 1.0],
      0.5, 0.3,
      1.0, 0.6,
      2.0, 1.0,
      3.0, 1.5,
    ],
    'heatmap-intensity': [
      'interpolate',
      ['linear'],
      ['zoom'],
      0, 0.5,
      8, 1.0,
      12, 2.0,
      15, 3.0,
    ],
    'heatmap-color': activityNodeHeatmapColor,
    'heatmap-radius': [
      'interpolate',
      ['linear'],
      ['zoom'],
      0, 2,
      8, 10,
      12, 25,
      15, 40,
      18, 60,
    ],
    'heatmap-opacity': [
      'interpolate',
      ['linear'],
      ['zoom'],
      7, 0.85,
      12, 0.6,
      16, 0.25,
    ],
  };
}

// ============================================================================
// Lot Size / Building Size Expressions
// ============================================================================

/**
 * Circle radius based on lot size (acres)
 * Larger lots = larger circles
 */
export const lotSizeRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'lot_size_acres'], 0],
  0, 6,
  0.5, 8,
  1, 10,
  2, 14,
  5, 18,
];

/**
 * Circle radius based on building square footage
 */
export const buildingSqftRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'sqft'], 0],
  0, 6,
  2500, 8,
  5000, 10,
  10000, 14,
  25000, 18,
];

// ============================================================================
// Data Freshness / Confidence Expressions
// ============================================================================

/**
 * Opacity based on data age (days since last update)
 * Fresher data = more opaque
 */
export function dataFreshnessOpacity(daysField: string): ExpressionSpecification {
  return [
    'interpolate',
    ['linear'],
    ['coalesce', ['get', daysField], 0],
    0, 1.0,    // Just updated - full opacity
    30, 0.8,   // Month old
    90, 0.6,   // Quarter old
    180, 0.4,  // Half year old
    365, 0.2,  // Year old - faded
  ];
}

// ============================================================================
// Layer Configuration Builders
// ============================================================================

/**
 * Build a complete heatmap paint configuration with data-driven weights
 * @param weighted - If true, uses opportunity_score for weight. If false, equal weight for all points.
 */
export function buildHeatmapPaint(weighted: boolean = false): Record<string, ExpressionSpecification> {
  return {
    'heatmap-weight': weighted ? opportunityHeatmapWeight : ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
    'heatmap-intensity': zoomBasedHeatmapIntensity,
    'heatmap-color': weighted ? opportunityHeatmapColor : competitionDensityHeatmapColor,
    'heatmap-radius': zoomBasedHeatmapRadius,
    'heatmap-opacity': zoomBasedHeatmapOpacity,
  };
}

/**
 * Build circle paint configuration for property markers
 * @param useOpportunityScore - Color by opportunity score vs property type
 */
export function buildPropertyCirclePaint(useOpportunityScore: boolean = true): Record<string, ExpressionSpecification | string | number> {
  return {
    'circle-color': useOpportunityScore ? opportunityScoreColor : propertyTypeColor,
    'circle-radius': useOpportunityScore ? opportunityScoreRadius : 8,
    'circle-opacity': useOpportunityScore ? opportunityScoreOpacity : 0.8,
    'circle-stroke-width': 2,
    'circle-stroke-color': '#ffffff',
  };
}

/**
 * Build symbol layout configuration for store markers
 */
export function buildStoreSymbolLayout(): Record<string, ExpressionSpecification | string | boolean> {
  return {
    'icon-image': ['get', 'brand'],
    'icon-size': zoomBasedIconSize,
    'icon-allow-overlap': true,
  };
}

// ============================================================================
// Travel Time Expressions
// ============================================================================

/**
 * Color gradient based on travel time in minutes
 * Green (instant) → Yellow (10 min) → Red (20+ min)
 */
export const travelTimeColor: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'travel_time_minutes'], 30],
  0, '#22C55E',   // Green - instant
  5, '#84CC16',   // Lime - 5 min
  10, '#EAB308',  // Yellow - 10 min
  15, '#F97316',  // Orange - 15 min
  20, '#EF4444',  // Red - 20+ min
];

/**
 * Opacity based on travel time - fade distant locations
 */
export const travelTimeOpacity: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'travel_time_minutes'], 30],
  0, 1.0,
  10, 0.8,
  20, 0.5,
  30, 0.3,
];

/**
 * Circle radius based on travel time - closer = larger
 */
export const travelTimeRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'travel_time_minutes'], 30],
  0, 14,  // Close - large
  10, 10,
  20, 6,
  30, 4,  // Far - small
];

/**
 * Get travel time color as RGB array for deck.gl
 */
export function getTravelTimeColorRGB(minutes: number | null): [number, number, number, number] {
  if (minutes === null) return [107, 114, 128, 200]; // Gray
  if (minutes < 5) return [34, 197, 94, 220];   // Green
  if (minutes < 10) return [132, 204, 22, 220]; // Lime
  if (minutes < 15) return [234, 179, 8, 220];  // Yellow
  if (minutes < 20) return [249, 115, 22, 220]; // Orange
  return [239, 68, 68, 220]; // Red
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Create a step expression for categorical color assignment
 * @param property - The feature property to read
 * @param stops - Array of [threshold, color] pairs
 * @param defaultColor - Color to use below first threshold
 */
export function createStepColor(
  property: string,
  stops: [number, string][],
  defaultColor: string
): ExpressionSpecification {
  const expression: (string | number | string[])[] = ['step', ['get', property], defaultColor];
  for (const [threshold, color] of stops) {
    expression.push(threshold, color);
  }
  return expression as ExpressionSpecification;
}

/**
 * Create an interpolation expression for continuous color gradients
 * @param property - The feature property to read
 * @param stops - Array of [value, color] pairs
 */
export function createInterpolateColor(
  property: string,
  stops: [number, string][]
): ExpressionSpecification {
  const expression: any[] = [
    'interpolate',
    ['linear'],
    ['coalesce', ['get', property], 0],
  ];
  for (const [value, color] of stops) {
    expression.push(value, color);
  }
  return expression as ExpressionSpecification;
}

/**
 * Wrap a property getter with coalesce for null safety
 */
export function safeGet(property: string, fallback: number | string = 0): ExpressionSpecification {
  return ['coalesce', ['get', property], fallback];
}
