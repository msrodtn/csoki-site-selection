/**
 * deck.gl Layer Components
 *
 * Custom WebGL layers for advanced 3D visualizations.
 * Uses deck.gl's MapboxLayer for integration with Mapbox GL JS.
 */

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
