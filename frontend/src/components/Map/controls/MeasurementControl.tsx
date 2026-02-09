/**
 * MeasurementControl — map toolbar for distance and area measurement.
 *
 * Two modes:
 * - Line: click points to measure distance
 * - Polygon: click points to measure area + perimeter
 *
 * Amber-themed (#F59E0B) to distinguish from DrawControl's blue.
 */

import { useCallback, useEffect, useMemo } from 'react';
import { Ruler, Pentagon, X } from 'lucide-react';
import { useMapStore } from '../../../store/useMapStore';
import {
  totalLineDistance,
  polygonArea,
  polygonPerimeter,
  formatDistance,
  formatArea,
  type DistanceUnit,
  type AreaUnit,
} from '../../../utils/measurement';

const DISTANCE_UNITS: { value: DistanceUnit; label: string }[] = [
  { value: 'feet', label: 'ft' },
  { value: 'miles', label: 'mi' },
  { value: 'km', label: 'km' },
  { value: 'meters', label: 'm' },
];

const AREA_UNITS: { value: AreaUnit; label: string }[] = [
  { value: 'sqft', label: 'sq ft' },
  { value: 'acres', label: 'ac' },
  { value: 'sqmiles', label: 'sq mi' },
];

export function MeasurementControl() {
  const isMeasureMode = useMapStore((s) => s.isMeasureMode);
  const setIsMeasureMode = useMapStore((s) => s.setIsMeasureMode);
  const measureType = useMapStore((s) => s.measureType);
  const setMeasureType = useMapStore((s) => s.setMeasureType);
  const measureUnit = useMapStore((s) => s.measureUnit);
  const setMeasureUnit = useMapStore((s) => s.setMeasureUnit);
  const measureAreaUnit = useMapStore((s) => s.measureAreaUnit);
  const setMeasureAreaUnit = useMapStore((s) => s.setMeasureAreaUnit);
  const measurePoints = useMapStore((s) => s.measurePoints);
  const clearMeasurement = useMapStore((s) => s.clearMeasurement);
  const isMeasurementComplete = useMapStore((s) => s.isMeasurementComplete);

  const handleLineMode = useCallback(() => {
    if (isMeasureMode && measureType === 'line') {
      setIsMeasureMode(false);
    } else {
      setMeasureType('line');
      setIsMeasureMode(true);
    }
  }, [isMeasureMode, measureType, setIsMeasureMode, setMeasureType]);

  const handlePolygonMode = useCallback(() => {
    if (isMeasureMode && measureType === 'polygon') {
      setIsMeasureMode(false);
    } else {
      setMeasureType('polygon');
      setIsMeasureMode(true);
    }
  }, [isMeasureMode, measureType, setIsMeasureMode, setMeasureType]);

  const handleClear = useCallback(() => {
    clearMeasurement();
    setIsMeasureMode(false);
  }, [clearMeasurement, setIsMeasureMode]);

  // ESC to cancel
  useEffect(() => {
    if (!isMeasureMode) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClear();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isMeasureMode, handleClear]);

  // Computed results
  const results = useMemo(() => {
    if (measurePoints.length < 2) return null;

    if (measureType === 'line') {
      return {
        type: 'line' as const,
        total: formatDistance(totalLineDistance(measurePoints, measureUnit), measureUnit),
        segments: measurePoints.length - 1,
      };
    }

    if (measurePoints.length >= 3) {
      return {
        type: 'polygon' as const,
        area: formatArea(polygonArea(measurePoints, measureAreaUnit), measureAreaUnit),
        perimeter: formatDistance(polygonPerimeter(measurePoints, measureUnit), measureUnit),
        vertices: measurePoints.length,
      };
    }

    return null;
  }, [measurePoints, measureType, measureUnit, measureAreaUnit]);

  const isLineActive = isMeasureMode && measureType === 'line';
  const isPolygonActive = isMeasureMode && measureType === 'polygon';
  const hasData = measurePoints.length > 0;

  return (
    <div className="absolute z-10" style={{ top: 230, right: 10 }}>
      {/* Button group */}
      <div className="flex flex-col gap-0.5">
        {/* Line measure */}
        <button
          onClick={handleLineMode}
          className={`w-8 h-8 rounded-t-md shadow-md border border-gray-200
                     flex items-center justify-center
                     focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1
                     transition-colors duration-150
                     ${isLineActive
                       ? 'bg-amber-500 text-white hover:bg-amber-600'
                       : 'bg-white text-gray-700 hover:bg-gray-50 active:bg-gray-100'
                     }`}
          title="Measure distance"
          aria-label="Measure distance"
        >
          <Ruler className="w-4 h-4" />
        </button>

        {/* Polygon area */}
        <button
          onClick={handlePolygonMode}
          className={`w-8 h-8 shadow-md border border-gray-200
                     flex items-center justify-center
                     focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1
                     transition-colors duration-150
                     ${isPolygonActive
                       ? 'bg-amber-500 text-white hover:bg-amber-600'
                       : 'bg-white text-gray-700 hover:bg-gray-50 active:bg-gray-100'
                     }`}
          title="Measure area"
          aria-label="Measure area"
        >
          <Pentagon className="w-4 h-4" />
        </button>

        {/* Clear */}
        <button
          onClick={handleClear}
          disabled={!hasData && !isMeasureMode}
          className={`w-8 h-8 rounded-b-md shadow-md border border-gray-200
                     flex items-center justify-center
                     focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1
                     transition-colors duration-150
                     ${hasData || isMeasureMode
                       ? 'bg-white text-red-500 hover:bg-red-50 active:bg-red-100'
                       : 'bg-white text-gray-300 cursor-not-allowed'
                     }`}
          title="Clear measurement"
          aria-label="Clear measurement"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Results panel — floats to the left of the buttons */}
      {results && (
        <div className="absolute top-0 right-10 mr-2 bg-white rounded-lg shadow-lg border border-gray-200 p-3 w-52">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            {results.type === 'line' ? 'Distance' : 'Area'}
          </div>

          {results.type === 'line' && (
            <>
              <div className="text-lg font-bold text-gray-900 mb-1">
                {results.total}
              </div>
              <div className="text-xs text-gray-400">
                {results.segments} segment{results.segments !== 1 ? 's' : ''}
              </div>
            </>
          )}

          {results.type === 'polygon' && (
            <>
              <div className="text-lg font-bold text-gray-900 mb-1">
                {results.area}
              </div>
              <div className="text-sm text-gray-600">
                Perimeter: {results.perimeter}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {results.vertices} vertices
              </div>
            </>
          )}

          {/* Unit selectors */}
          <div className="flex gap-1 mt-2 pt-2 border-t border-gray-100">
            {DISTANCE_UNITS.map((u) => (
              <button
                key={u.value}
                onClick={() => setMeasureUnit(u.value)}
                className={`px-1.5 py-0.5 text-xs rounded transition-colors
                  ${measureUnit === u.value
                    ? 'bg-amber-100 text-amber-800 font-medium'
                    : 'text-gray-500 hover:bg-gray-100'
                  }`}
              >
                {u.label}
              </button>
            ))}
          </div>

          {results.type === 'polygon' && (
            <div className="flex gap-1 mt-1">
              {AREA_UNITS.map((u) => (
                <button
                  key={u.value}
                  onClick={() => setMeasureAreaUnit(u.value)}
                  className={`px-1.5 py-0.5 text-xs rounded transition-colors
                    ${measureAreaUnit === u.value
                      ? 'bg-amber-100 text-amber-800 font-medium'
                      : 'text-gray-500 hover:bg-gray-100'
                    }`}
                >
                  {u.label}
                </button>
              ))}
            </div>
          )}

          {/* Instructions when still drawing */}
          {!isMeasurementComplete && isMeasureMode && (
            <div className="text-xs text-amber-600 mt-2 pt-1 border-t border-gray-100">
              {measureType === 'line'
                ? 'Double-click to finish'
                : 'Double-click to close polygon'}
              <span className="text-gray-400 block">ESC to cancel</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
