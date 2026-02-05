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
 * Throws errors with user-friendly messages for UI display
 */
export async function fetchIsochrone(
  options: IsochroneOptions,
  accessToken: string
): Promise<GeoJSON.Feature<GeoJSON.Polygon> | null> {
  const { coordinates, minutes, mode } = options;
  const [lng, lat] = coordinates;

  // Validate access token
  if (!accessToken) {
    throw new Error('Map service not configured. Please contact support.');
  }

  // Validate coordinates
  if (lng < -180 || lng > 180 || lat < -90 || lat > 90) {
    throw new Error('Invalid location. Please select a point on the map.');
  }

  // Mapbox Isochrone API endpoint
  const url = `https://api.mapbox.com/isochrone/v1/mapbox/${mode}/${lng},${lat}`;

  const params = new URLSearchParams({
    contours_minutes: minutes.toString(),
    polygons: 'true',
    access_token: accessToken,
  });

  try {
    const response = await fetch(`${url}?${params}`);

    if (response.status === 401) {
      throw new Error('Map service authentication failed. Please refresh the page.');
    }

    if (response.status === 422) {
      throw new Error('Unable to calculate travel area for this location. Try a different spot.');
    }

    if (!response.ok) {
      throw new Error(`Travel area service error (${response.status}). Please try again.`);
    }

    const data = await response.json();

    // Mapbox returns a FeatureCollection with one feature
    if (data.features && data.features.length > 0) {
      return data.features[0] as GeoJSON.Feature<GeoJSON.Polygon>;
    }

    // No features returned - location might be unreachable (e.g., in ocean)
    return null;
  } catch (error) {
    // Re-throw our custom errors
    if (error instanceof Error && error.message.includes('Map service') ||
        error instanceof Error && error.message.includes('Unable to calculate') ||
        error instanceof Error && error.message.includes('Invalid location') ||
        error instanceof Error && error.message.includes('Travel area service')) {
      throw error;
    }
    // Network or other errors
    console.error('Failed to fetch isochrone:', error);
    throw new Error('Failed to calculate travel area. Check your connection and try again.');
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
export function getIsochroneOpacity(): number {
  return 0.2; // Semi-transparent
}
