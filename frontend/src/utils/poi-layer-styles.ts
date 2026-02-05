/**
 * POI Layer Style Definitions
 *
 * Native Mapbox GL layer styles for POI rendering with feature state support.
 * Replaces React marker components with performant WebGL-based layers.
 */

import type {
  CircleLayerSpecification,
  ExpressionSpecification,
  FilterSpecification,
} from 'mapbox-gl';
import { POI_CATEGORY_COLORS, type POICategory } from '../types/store';

// Source and layer IDs
export const POI_SOURCE_ID = 'poi-source';
export const POI_LAYER_ID = 'poi-layer';
export const POI_HOVER_LAYER_ID = 'poi-hover-layer';
export const POI_SELECTED_LAYER_ID = 'poi-selected-layer';

/**
 * Category color match expression
 * Maps POI category to its corresponding color
 */
export const poiCategoryColorExpression: ExpressionSpecification = [
  'match',
  ['get', 'category'],
  'anchors', POI_CATEGORY_COLORS.anchors,
  'quick_service', POI_CATEGORY_COLORS.quick_service,
  'restaurants', POI_CATEGORY_COLORS.restaurants,
  'retail', POI_CATEGORY_COLORS.retail,
  'entertainment', POI_CATEGORY_COLORS.entertainment,
  'services', POI_CATEGORY_COLORS.services,
  '#666666', // fallback color
];

/**
 * Zoom-responsive circle radius
 * Sizes POIs appropriately at different zoom levels
 */
export const poiCircleRadiusExpression: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  10, 5,   // zoom 10: 5px radius
  14, 8,   // zoom 14: 8px radius
  18, 12,  // zoom 18: 12px radius
];

/**
 * Hover state circle radius (larger)
 */
export const poiHoverCircleRadiusExpression: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  10, 7,
  14, 10,
  18, 14,
];

/**
 * Selected state circle radius (largest)
 */
export const poiSelectedCircleRadiusExpression: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  10, 8,
  14, 12,
  18, 16,
];

/**
 * Base POI circle layer specification
 * Renders all visible POIs with category-based coloring
 */
export const poiCircleLayerSpec: Omit<CircleLayerSpecification, 'source'> = {
  id: POI_LAYER_ID,
  type: 'circle',
  paint: {
    'circle-color': poiCategoryColorExpression,
    'circle-radius': poiCircleRadiusExpression,
    'circle-opacity': [
      'case',
      ['boolean', ['feature-state', 'hidden'], false], 0,
      ['boolean', ['feature-state', 'hover'], false], 0, // hide when hover layer shows
      ['boolean', ['feature-state', 'selected'], false], 0, // hide when selected layer shows
      0.85,
    ],
    'circle-stroke-width': 1.5,
    'circle-stroke-color': '#ffffff',
    'circle-stroke-opacity': [
      'case',
      ['boolean', ['feature-state', 'hidden'], false], 0,
      ['boolean', ['feature-state', 'hover'], false], 0,
      ['boolean', ['feature-state', 'selected'], false], 0,
      1,
    ],
  },
};

/**
 * Hover POI circle layer specification
 * Shows only when feature has hover state
 */
export const poiHoverLayerSpec: Omit<CircleLayerSpecification, 'source'> = {
  id: POI_HOVER_LAYER_ID,
  type: 'circle',
  paint: {
    'circle-color': poiCategoryColorExpression,
    'circle-radius': poiHoverCircleRadiusExpression,
    'circle-opacity': [
      'case',
      ['boolean', ['feature-state', 'hidden'], false], 0,
      ['boolean', ['feature-state', 'selected'], false], 0, // selected takes priority
      ['boolean', ['feature-state', 'hover'], false], 1,
      0,
    ],
    'circle-stroke-width': 2,
    'circle-stroke-color': '#ffffff',
    'circle-stroke-opacity': [
      'case',
      ['boolean', ['feature-state', 'hover'], false], 1,
      0,
    ],
  },
};

/**
 * Selected POI circle layer specification
 * Shows only when feature has selected state
 */
export const poiSelectedLayerSpec: Omit<CircleLayerSpecification, 'source'> = {
  id: POI_SELECTED_LAYER_ID,
  type: 'circle',
  paint: {
    'circle-color': poiCategoryColorExpression,
    'circle-radius': poiSelectedCircleRadiusExpression,
    'circle-opacity': [
      'case',
      ['boolean', ['feature-state', 'hidden'], false], 0,
      ['boolean', ['feature-state', 'selected'], false], 1,
      0,
    ],
    'circle-stroke-width': 3,
    'circle-stroke-color': '#000000',
    'circle-stroke-opacity': [
      'case',
      ['boolean', ['feature-state', 'selected'], false], 1,
      0,
    ],
  },
};

/**
 * Build visibility filter expression
 * Combines category visibility and individual POI hidden state
 *
 * @param visibleCategories - Array of visible POI categories
 * @param hiddenPOIIds - Array of place_ids to hide
 */
export function buildPOIVisibilityFilter(
  visibleCategories: POICategory[],
  hiddenPOIIds: string[]
): FilterSpecification {
  const categoryFilter: ExpressionSpecification = [
    'in',
    ['get', 'category'],
    ['literal', visibleCategories],
  ];

  // If no hidden POIs, just filter by category
  if (hiddenPOIIds.length === 0) {
    return categoryFilter;
  }

  const notHiddenFilter: ExpressionSpecification = [
    '!',
    ['in', ['get', 'place_id'], ['literal', hiddenPOIIds]],
  ];

  return ['all', categoryFilter, notHiddenFilter];
}

/**
 * Get all POI layer IDs for event handling
 */
export function getPOILayerIds(): string[] {
  return [POI_LAYER_ID, POI_HOVER_LAYER_ID, POI_SELECTED_LAYER_ID];
}
