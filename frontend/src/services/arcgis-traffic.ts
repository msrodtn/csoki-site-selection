/**
 * ArcGIS Traffic Data Service
 * 
 * Fetches AADT (Average Annual Daily Traffic) data from state DOT services.
 * Currently supports Iowa, can be expanded to other states.
 */

export interface TrafficSegment {
  type: 'Feature';
  geometry: {
    type: 'LineString';
    coordinates: number[][];
  };
  properties: {
    AADT: number;
    AADT_YEAR: number;
    ROUTEID: string;
    STATESIGNED?: string;
    COUNTYSIGNED?: string;
    TRUCK_AADT?: number;
  };
}

export interface TrafficDataResponse {
  type: 'FeatureCollection';
  features: TrafficSegment[];
}

/**
 * Fetch traffic data from Iowa DOT ArcGIS service
 */
export async function fetchIowaTrafficData(
  bounds: { north: number; south: number; east: number; west: number }
): Promise<TrafficDataResponse> {
  // Convert bounds to ArcGIS format (Web Mercator)
  const xmin = bounds.west;
  const ymin = bounds.south;
  const xmax = bounds.east;
  const ymax = bounds.north;

  const url = 'https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Data_view/FeatureServer/10/query';

  const params = new URLSearchParams({
    where: '1=1',
    geometry: `${xmin},${ymin},${xmax},${ymax}`,
    geometryType: 'esriGeometryEnvelope',
    spatialRel: 'esriSpatialRelIntersects',
    outFields: 'AADT,AADT_YEAR,ROUTEID,STATESIGNED,COUNTYSIGNED,TRUCK_AADT',
    returnGeometry: 'true',
    f: 'geojson',
    inSR: '4326',
    outSR: '4326',
  });

  try {
    const response = await fetch(`${url}?${params}`);
    
    if (!response.ok) {
      throw new Error(`ArcGIS request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return data as TrafficDataResponse;
  } catch (error) {
    console.error('Failed to fetch Iowa traffic data:', error);
    throw error;
  }
}

/**
 * Get color for traffic volume (matches Iowa DOT color scheme)
 */
export function getTrafficColor(aadt: number): string {
  if (aadt < 1000) return '#00C5FF';      // Blue
  if (aadt < 2000) return '#55FF00';      // Green
  if (aadt < 5000) return '#FFAA00';      // Orange
  return '#FF0000';                        // Red
}

/**
 * Get Mapbox expression for traffic color
 */
export function getTrafficColorExpression(): any[] {
  return [
    'step',
    ['get', 'AADT'],
    '#00C5FF',  // < 1000
    1000,
    '#55FF00',  // 1000-1999
    2000,
    '#FFAA00',  // 2000-4999
    5000,
    '#FF0000',  // 5000+
  ];
}

/**
 * Format AADT number for display
 */
export function formatAADT(aadt: number): string {
  if (!aadt) return 'N/A';
  return aadt.toLocaleString() + ' vehicles/day';
}
