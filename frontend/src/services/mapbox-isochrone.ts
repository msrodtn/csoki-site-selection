/**
 * Mapbox Isochrone API Service
 * 
 * Fetches travel time polygons (isochrones) from Mapbox API.
 * Shows areas reachable within X minutes by driving/walking/cycling.
 */

import type { TravelMode } from '../components/Map/IsochroneControl';

export interface IsochroneOptions {
  coordinates: [number, number]; // [lng, lat]
  minutes: number;
  mode: TravelMode;
}

export interface IsochronePolygon {
  type: 'Feature';
  geometry: {
    type: 'Polygon';
    coordinates: number[][][];
  };
  properties: {
    contour: number; // Minutes
    color: string;
    opacity: number;
  };
}

/**
 * Fetch isochrone polygon from Mapbox API
 */
export async function fetchIsochrone(
  options: IsochroneOptions,
  accessToken: string
): Promise<GeoJSON.Feature<GeoJSON.Polygon> | null> {
  const { coordinates, minutes, mode } = options;
  const [lng, lat] = coordinates;

  // Mapbox Isochrone API endpoint
  const url = `https://api.mapbox.com/isochrone/v1/mapbox/${mode}/${lng},${lat}`;

  const params = new URLSearchParams({
    contours_minutes: minutes.toString(),
    polygons: 'true',
    access_token: accessToken,
  });

  try {
    const response = await fetch(`${url}?${params}`);

    if (!response.ok) {
      throw new Error(`Isochrone API error: ${response.statusText}`);
    }

    const data = await response.json();

    // Mapbox returns a FeatureCollection with one feature
    if (data.features && data.features.length > 0) {
      return data.features[0] as GeoJSON.Feature<GeoJSON.Polygon>;
    }

    return null;
  } catch (error) {
    console.error('Failed to fetch isochrone:', error);
    return null;
  }
}

/**
 * Get color for isochrone based on travel mode
 */
export function getIsochroneColor(mode: TravelMode): string {
  switch (mode) {
    case 'driving':
      return '#3B82F6'; // Blue
    case 'walking':
      return '#10B981'; // Green
    case 'cycling':
      return '#F59E0B'; // Orange
  }
}

/**
 * Get opacity for isochrone polygon
 */
export function getIsochroneOpacity(mode: TravelMode): number {
  return 0.2; // Semi-transparent
}
