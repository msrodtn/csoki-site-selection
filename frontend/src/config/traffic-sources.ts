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
  // Note: These endpoints need verification - URLs may have changed
  NE: { 
    name: 'Nebraska', 
    url: 'https://gis.ne.gov/Enterprise/rest/services/AnnualAverageDailyTraffic/FeatureServer/0',
    fields: 'ADJ_ADT_TOT_NUM,ROUTE_NO,ADT_YEAR', 
    maxRecords: 2000 
  },
  NV: { 
    name: 'Nevada', 
    url: 'https://gis.dot.nv.gov/agsphs/rest/services/TRINA_Stations/FeatureServer/0',
    fields: 'AADT_2024,ROUTE_NAME,Name,LOCATION_D', 
    maxRecords: 2000 
  },
  ID: { 
    name: 'Idaho', 
    url: 'https://gis.itd.idaho.gov/arcgisprod/rest/services/ArcGISOnline/IdahoTransportationLayersForOpenData/MapServer/50',
    fields: 'AADT,Route,Year_', 
    maxRecords: 2000 
  },
};

// Mapbox tileset sources (vector tiles - much faster!)
// Update these after uploading tilesets to Mapbox
export const TILESET_SOURCES = {
  IA: {
    name: 'Iowa',
    url: 'mapbox://msrodtn.ia-traffic',
    sourceLayer: 'traffic',
  },
  NE: {
    name: 'Nebraska', 
    url: 'mapbox://msrodtn.nebraska-traffic', 
    sourceLayer: 'traffic',
  },
  NV: {
    name: 'Nevada',
    url: 'mapbox://msrodtn.nevada-traffic',
    sourceLayer: 'traffic', 
  },
  ID: {
    name: 'Idaho',
    url: 'mapbox://msrodtn.idaho-traffic',
    sourceLayer: 'traffic',
  },
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
