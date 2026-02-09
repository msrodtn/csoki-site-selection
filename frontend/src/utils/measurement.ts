/**
 * Map Measurement Utilities
 *
 * Distance and area calculations using turf.js,
 * unit conversions, formatting, and GeoJSON builders.
 */

import * as turf from '@turf/turf';

export type DistanceUnit = 'feet' | 'miles' | 'km' | 'meters';
export type AreaUnit = 'sqft' | 'acres' | 'sqmiles';

// Conversion factors from square meters
const SQ_METERS_TO_SQ_FEET = 10.7639;
const SQ_METERS_TO_ACRES = 0.000247105;
const SQ_METERS_TO_SQ_MILES = 3.861e-7;

/** Map our DistanceUnit to turf's unit system */
function turfUnit(unit: DistanceUnit): 'feet' | 'miles' | 'kilometers' | 'meters' {
  switch (unit) {
    case 'feet': return 'feet';
    case 'miles': return 'miles';
    case 'km': return 'kilometers';
    case 'meters': return 'meters';
  }
}

/** Calculate distance between two [lng, lat] points */
export function segmentDistance(
  p1: [number, number],
  p2: [number, number],
  unit: DistanceUnit
): number {
  return turf.distance(turf.point(p1), turf.point(p2), { units: turfUnit(unit) });
}

/** Calculate total line distance across all points */
export function totalLineDistance(
  points: [number, number][],
  unit: DistanceUnit
): number {
  if (points.length < 2) return 0;
  const line = turf.lineString(points);
  return turf.length(line, { units: turfUnit(unit) });
}

/** Calculate polygon area from points (auto-closes the ring) */
export function polygonArea(
  points: [number, number][],
  unit: AreaUnit
): number {
  if (points.length < 3) return 0;
  const ring = [...points, points[0]];
  const polygon = turf.polygon([ring]);
  const areaM2 = turf.area(polygon); // always returns sq meters
  switch (unit) {
    case 'sqft': return areaM2 * SQ_METERS_TO_SQ_FEET;
    case 'acres': return areaM2 * SQ_METERS_TO_ACRES;
    case 'sqmiles': return areaM2 * SQ_METERS_TO_SQ_MILES;
  }
}

/** Calculate polygon perimeter */
export function polygonPerimeter(
  points: [number, number][],
  unit: DistanceUnit
): number {
  if (points.length < 3) return 0;
  const ring = [...points, points[0]];
  return totalLineDistance(ring, unit);
}

/** Get midpoint of a segment (for label placement) */
export function segmentMidpoint(
  p1: [number, number],
  p2: [number, number]
): [number, number] {
  const mid = turf.midpoint(turf.point(p1), turf.point(p2));
  return mid.geometry.coordinates as [number, number];
}

/** Format distance with appropriate precision */
export function formatDistance(value: number, unit: DistanceUnit): string {
  const labels: Record<DistanceUnit, string> = {
    feet: 'ft',
    miles: 'mi',
    km: 'km',
    meters: 'm',
  };
  if (unit === 'feet' || unit === 'meters') {
    return `${value < 100 ? value.toFixed(1) : Math.round(value).toLocaleString()} ${labels[unit]}`;
  }
  return `${value < 1 ? value.toFixed(3) : value.toFixed(2)} ${labels[unit]}`;
}

/** Format area with appropriate precision */
export function formatArea(value: number, unit: AreaUnit): string {
  const labels: Record<AreaUnit, string> = {
    sqft: 'sq ft',
    acres: 'ac',
    sqmiles: 'sq mi',
  };
  if (unit === 'sqft') {
    return `${Math.round(value).toLocaleString()} ${labels[unit]}`;
  }
  return `${value < 1 ? value.toFixed(3) : value.toFixed(2)} ${labels[unit]}`;
}

/** Build GeoJSON FeatureCollection for rendering measurement geometry */
export function buildMeasurementGeoJSON(
  points: [number, number][],
  type: 'line' | 'polygon',
  isComplete: boolean
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  if (points.length >= 2) {
    // Closed polygon fill
    if (type === 'polygon' && isComplete && points.length >= 3) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[...points, points[0]]],
        },
        properties: { featureType: 'polygon' },
      });
    }

    // Line connecting all points (always show, even for polygon while drawing)
    const linePoints =
      type === 'polygon' && isComplete && points.length >= 3
        ? [...points, points[0]]
        : points;
    features.push({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: linePoints,
      },
      properties: { featureType: 'line' },
    });
  }

  // Vertex circles at each clicked point
  points.forEach((pt, i) => {
    features.push({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: pt,
      },
      properties: { featureType: 'vertex', index: i },
    });
  });

  return { type: 'FeatureCollection', features };
}
