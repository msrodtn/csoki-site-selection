/**
 * MeasurementLayer — renders measurement geometry on the map.
 *
 * Uses GeoJSON Source + Layers for lines, polygon fills, and vertex circles.
 * Segment distance labels are rendered as Marker components at midpoints.
 */

import { useMemo } from 'react';
import { Source, Layer, Marker } from '@vis.gl/react-mapbox';
import type { LineLayerSpecification, FillLayerSpecification, CircleLayerSpecification } from 'mapbox-gl';
import { useMapStore } from '../../../store/useMapStore';
import {
  buildMeasurementGeoJSON,
  segmentDistance,
  segmentMidpoint,
  formatDistance,
} from '../../../utils/measurement';

// Amber color scheme — visually distinct from DrawControl's blue
const AMBER = '#F59E0B';

const MEASUREMENT_LINE_STYLE: Omit<LineLayerSpecification, 'source'> = {
  id: 'measurement-line',
  type: 'line',
  filter: ['==', ['get', 'featureType'], 'line'],
  layout: {
    'line-cap': 'round',
    'line-join': 'round',
  },
  paint: {
    'line-color': AMBER,
    'line-width': 3,
    'line-dasharray': [3, 2],
  },
};

const MEASUREMENT_FILL_STYLE: Omit<FillLayerSpecification, 'source'> = {
  id: 'measurement-fill',
  type: 'fill',
  filter: ['==', ['get', 'featureType'], 'polygon'],
  paint: {
    'fill-color': AMBER,
    'fill-opacity': 0.15,
  },
};

const MEASUREMENT_VERTEX_STYLE: Omit<CircleLayerSpecification, 'source'> = {
  id: 'measurement-vertex',
  type: 'circle',
  filter: ['==', ['get', 'featureType'], 'vertex'],
  paint: {
    'circle-radius': 5,
    'circle-color': '#ffffff',
    'circle-stroke-color': AMBER,
    'circle-stroke-width': 2,
  },
};

export function MeasurementLayer() {
  const measurePoints = useMapStore((s) => s.measurePoints);
  const measureType = useMapStore((s) => s.measureType);
  const measureUnit = useMapStore((s) => s.measureUnit);
  const isMeasurementComplete = useMapStore((s) => s.isMeasurementComplete);
  const isMeasureMode = useMapStore((s) => s.isMeasureMode);

  const geojson = useMemo(
    () => buildMeasurementGeoJSON(measurePoints, measureType, isMeasurementComplete),
    [measurePoints, measureType, isMeasurementComplete]
  );

  const segmentLabels = useMemo(() => {
    if (measurePoints.length < 2) return [];

    const labels: Array<{ position: [number, number]; text: string }> = [];
    const pts =
      measureType === 'polygon' && isMeasurementComplete && measurePoints.length >= 3
        ? [...measurePoints, measurePoints[0]]
        : measurePoints;

    for (let i = 0; i < pts.length - 1; i++) {
      const dist = segmentDistance(pts[i], pts[i + 1], measureUnit);
      const mid = segmentMidpoint(pts[i], pts[i + 1]);
      labels.push({ position: mid, text: formatDistance(dist, measureUnit) });
    }
    return labels;
  }, [measurePoints, measureUnit, measureType, isMeasurementComplete]);

  // Nothing to render
  if (!isMeasureMode && measurePoints.length === 0) return null;

  return (
    <>
      <Source id="measurement" type="geojson" data={geojson}>
        <Layer {...MEASUREMENT_FILL_STYLE} />
        <Layer {...MEASUREMENT_LINE_STYLE} />
        <Layer {...MEASUREMENT_VERTEX_STYLE} />
      </Source>

      {segmentLabels.map((label, i) => (
        <Marker
          key={`measure-label-${i}`}
          longitude={label.position[0]}
          latitude={label.position[1]}
          anchor="center"
          style={{ zIndex: 3000, pointerEvents: 'none' }}
        >
          <div className="bg-gray-900/80 text-white text-xs font-mono px-1.5 py-0.5 rounded shadow-sm whitespace-nowrap">
            {label.text}
          </div>
        </Marker>
      ))}
    </>
  );
}
