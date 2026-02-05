/**
 * Custom Navigation Control
 *
 * Provides zoom in/out and compass reset buttons with custom styling.
 * Replaces the default Mapbox NavigationControl for better theme integration.
 */

import { useCallback } from 'react';
import type { MapRef } from '@vis.gl/react-mapbox';

export interface NavigationControlProps {
  /** Reference to the Mapbox map instance */
  map: MapRef | null;
  /** Position on the map */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  /** Show compass button */
  showCompass?: boolean;
  /** Zoom animation duration in ms */
  zoomDuration?: number;
}

/**
 * Position styles for control placement
 */
const positionStyles: Record<string, React.CSSProperties> = {
  'top-left': { top: 10, left: 10 },
  'top-right': { top: 10, right: 10 },
  'bottom-left': { bottom: 30, left: 10 },
  'bottom-right': { bottom: 30, right: 10 },
};

/**
 * NavigationControl provides custom zoom buttons
 */
export function NavigationControl({
  map,
  position = 'top-right',
  showCompass = true,
  zoomDuration = 300,
}: NavigationControlProps) {
  /**
   * Handle zoom in
   */
  const handleZoomIn = useCallback(() => {
    if (!map) return;
    const mapInstance = map.getMap();
    mapInstance.zoomIn({ duration: zoomDuration });
  }, [map, zoomDuration]);

  /**
   * Handle zoom out
   */
  const handleZoomOut = useCallback(() => {
    if (!map) return;
    const mapInstance = map.getMap();
    mapInstance.zoomOut({ duration: zoomDuration });
  }, [map, zoomDuration]);

  /**
   * Handle compass reset (north up)
   */
  const handleResetNorth = useCallback(() => {
    if (!map) return;
    const mapInstance = map.getMap();
    mapInstance.resetNorth({ duration: zoomDuration });
  }, [map, zoomDuration]);

  return (
    <div
      className="absolute z-10 flex flex-col gap-0.5"
      style={positionStyles[position]}
    >
      {/* Zoom In Button */}
      <button
        onClick={handleZoomIn}
        className="w-8 h-8 bg-white rounded-t-md shadow-md border border-gray-200
                   flex items-center justify-center text-gray-700
                   hover:bg-gray-50 active:bg-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                   transition-colors duration-150"
        title="Zoom in"
        aria-label="Zoom in"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>

      {/* Zoom Out Button */}
      <button
        onClick={handleZoomOut}
        className={`w-8 h-8 bg-white shadow-md border border-gray-200
                   flex items-center justify-center text-gray-700
                   hover:bg-gray-50 active:bg-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                   transition-colors duration-150
                   ${showCompass ? '' : 'rounded-b-md'}`}
        title="Zoom out"
        aria-label="Zoom out"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>

      {/* Compass Button */}
      {showCompass && (
        <button
          onClick={handleResetNorth}
          className="w-8 h-8 bg-white rounded-b-md shadow-md border border-gray-200
                     flex items-center justify-center text-gray-700
                     hover:bg-gray-50 active:bg-gray-100
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                     transition-colors duration-150"
          title="Reset north"
          aria-label="Reset north"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {/* Compass icon */}
            <circle cx="12" cy="12" r="10" />
            <polygon
              points="12,2 15,12 12,22 9,12"
              fill="currentColor"
              opacity="0.3"
            />
            <polygon points="12,2 15,12 12,10 9,12" fill="#EF4444" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default NavigationControl;
