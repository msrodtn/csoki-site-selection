/**
 * Traffic Data Sources Configuration
 * 
 * Supports two modes:
 * 1. 'arcgis' - Direct fetch from state DOT ArcGIS services (current)
 * 2. 'tileset' - Mapbox vector tilesets (better performance, requires setup)
 * 
 * To switch to tilesets:
 * 1. Run: node scripts/download-traffic-data.js IA
 * 2. Run: ./scripts/upload-to-mapbox.sh IA your-username
 * 3. Change MODE to 'tileset' below
 * 4. Update TILESET_SOURCES with your tileset IDs
 */

export type TrafficSourceMode = 'arcgis' | 'tileset';

// Current mode - switch to 'tileset' after uploading to Mapbox
export const TRAFFIC_SOURCE_MODE: TrafficSourceMode = 'tileset';

// ArcGIS REST API sources (direct fetch)
export const ARCGIS_SOURCES = {
  IA: {
    name: 'Iowa',
    url: 'https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Data_view/FeatureServer/10',
    fields: 'AADT,ROUTE_NAME,STATESIGNED',
    maxRecords: 2000,
  },
  // Add more states here as we find their ArcGIS services
  // NE: { name: 'Nebraska', url: '...', fields: '...', maxRecords: 2000 },
};

// Mapbox tileset sources (vector tiles - much faster!)
// Update these after uploading tilesets to Mapbox
export const TILESET_SOURCES = {
  IA: {
    name: 'Iowa',
    url: 'mapbox://msrodtn.ia-traffic',
    sourceLayer: 'traffic',
  },
  // NE: { name: 'Nebraska', url: 'mapbox://msrodtn.ne-traffic', sourceLayer: 'traffic' },
};

// Get available states for current mode
export function getAvailableStates(): Array<{ code: string; name: string }> {
  const sources = TRAFFIC_SOURCE_MODE === 'arcgis' ? ARCGIS_SOURCES : TILESET_SOURCES;
  return Object.entries(sources).map(([code, config]) => ({
    code,
    name: config.name,
  }));
}

// Get source config for a state
export function getTrafficSource(stateCode: string) {
  if (TRAFFIC_SOURCE_MODE === 'arcgis') {
    return ARCGIS_SOURCES[stateCode as keyof typeof ARCGIS_SOURCES];
  } else {
    return TILESET_SOURCES[stateCode as keyof typeof TILESET_SOURCES];
  }
}
