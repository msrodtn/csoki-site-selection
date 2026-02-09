/**
 * Map Layer Components
 *
 * Custom layers for map visualizations.
 * Includes deck.gl WebGL layers and native Mapbox GL layers.
 */

// deck.gl 3D visualization layers
export {
  createOpportunityHexagonLayer,
  createDeckOverlay,
  useOpportunityHexagonLayer,
  getHexagonStats,
  type OpportunityHexagonLayerProps,
} from './OpportunityHexagonLayer';

export {
  createCompetitorArcLayer,
  createArcOverlay,
  useCompetitorArcLayer,
  getArcStats,
  type CompetitorArcLayerProps,
} from './CompetitorArcLayer';

// Native Mapbox GL layers with feature state support
export {
  InteractiveMapLayer,
  FEATURE_STATE_HOVER,
  FEATURE_STATE_SELECTED,
  FEATURE_STATE_HIDDEN,
  type LayerStyle,
  type InteractiveMapLayerProps,
} from './InteractiveMapLayer';

export { POILayer, type POILayerProps } from './POILayer';

export {
  BuildingLayer,
  type BuildingLayerProps,
  type BuildingInfo,
} from './BuildingLayer';

export { MeasurementLayer } from './MeasurementLayer';
