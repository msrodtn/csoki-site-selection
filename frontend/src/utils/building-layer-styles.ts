/**
 * Building Layer Style Definitions
 *
 * Native Mapbox GL layer styles for interactive building footprints.
 * Uses Mapbox's built-in composite tileset with the 'building' source-layer.
 */

import type {
  FillLayerSpecification,
  FillExtrusionLayerSpecification,
  ExpressionSpecification,
} from 'mapbox-gl';

// Source and layer IDs
export const BUILDING_SOURCE_ID = 'composite';
export const BUILDING_SOURCE_LAYER = 'building';
export const BUILDING_LAYER_ID = 'buildings-interactive';
export const BUILDING_OUTLINE_LAYER_ID = 'buildings-outline';

// Feature state keys
export const BUILDING_FEATURE_STATE_HOVER = 'hover';
export const BUILDING_FEATURE_STATE_SELECTED = 'selected';

/**
 * Fill color expression with feature state support
 * Blue tones for hover/select, gray default
 */
export const buildingFillColorExpression: ExpressionSpecification = [
  'case',
  ['boolean', ['feature-state', 'selected'], false], '#3B82F6', // Blue-500
  ['boolean', ['feature-state', 'hover'], false], '#60A5FA',    // Blue-400
  '#E5E7EB', // Gray-200 default
];

/**
 * Fill opacity expression with feature state support
 */
export const buildingFillOpacityExpression: ExpressionSpecification = [
  'case',
  ['boolean', ['feature-state', 'selected'], false], 0.7,
  ['boolean', ['feature-state', 'hover'], false], 0.5,
  0.3,
];

/**
 * Outline color expression
 */
export const buildingOutlineColorExpression: ExpressionSpecification = [
  'case',
  ['boolean', ['feature-state', 'selected'], false], '#1D4ED8', // Blue-700
  ['boolean', ['feature-state', 'hover'], false], '#3B82F6',    // Blue-500
  '#9CA3AF', // Gray-400
];

/**
 * Interactive building fill layer specification
 * Renders building footprints with hover/select states
 */
export const buildingFillLayerSpec: Omit<FillLayerSpecification, 'source'> = {
  id: BUILDING_LAYER_ID,
  type: 'fill',
  'source-layer': BUILDING_SOURCE_LAYER,
  minzoom: 15,
  paint: {
    'fill-color': buildingFillColorExpression,
    'fill-opacity': buildingFillOpacityExpression,
  },
};

/**
 * Building outline layer specification
 * Adds visible outline to buildings
 */
export const buildingOutlineLayerSpec: Omit<FillLayerSpecification, 'source'> = {
  id: BUILDING_OUTLINE_LAYER_ID,
  type: 'fill',
  'source-layer': BUILDING_SOURCE_LAYER,
  minzoom: 15,
  paint: {
    'fill-outline-color': buildingOutlineColorExpression,
    'fill-color': 'transparent',
    'fill-opacity': 1,
  },
};

/**
 * 3D building extrusion layer specification
 * Optional layer for 3D building visualization
 */
export const buildingExtrusionLayerSpec: Omit<FillExtrusionLayerSpecification, 'source'> = {
  id: 'buildings-extrusion',
  type: 'fill-extrusion',
  'source-layer': BUILDING_SOURCE_LAYER,
  minzoom: 15,
  paint: {
    'fill-extrusion-color': [
      'case',
      ['boolean', ['feature-state', 'selected'], false], '#3B82F6',
      ['boolean', ['feature-state', 'hover'], false], '#60A5FA',
      '#D1D5DB',
    ],
    'fill-extrusion-height': [
      'interpolate',
      ['linear'],
      ['zoom'],
      15, 0,
      15.5, ['get', 'height'],
    ],
    'fill-extrusion-base': [
      'interpolate',
      ['linear'],
      ['zoom'],
      15, 0,
      15.5, ['get', 'min_height'],
    ],
    'fill-extrusion-opacity': 0.6,
  },
};

/**
 * Get all building layer IDs for event handling
 */
export function getBuildingLayerIds(): string[] {
  return [BUILDING_LAYER_ID, BUILDING_OUTLINE_LAYER_ID];
}
