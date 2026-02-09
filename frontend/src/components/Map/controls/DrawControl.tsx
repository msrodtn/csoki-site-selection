import { useEffect, useRef, useCallback } from 'react';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { Pencil, Trash2 } from 'lucide-react';
import type { MapRef } from '@vis.gl/react-mapbox';

export interface DrawControlProps {
  map: MapRef | null;
  isDrawMode: boolean;
  onDrawModeChange: (active: boolean) => void;
  onPolygonCreated: (feature: GeoJSON.Feature) => void;
  onPolygonCleared: () => void;
  hasPolygon: boolean;
}

const DRAW_STYLES = [
  // Polygon fill
  {
    id: 'gl-draw-polygon-fill',
    type: 'fill',
    filter: ['all', ['==', '$type', 'Polygon'], ['!=', 'mode', 'static']],
    paint: {
      'fill-color': '#3B82F6',
      'fill-outline-color': '#3B82F6',
      'fill-opacity': 0.1,
    },
  },
  // Polygon outline
  {
    id: 'gl-draw-polygon-stroke-active',
    type: 'line',
    filter: ['all', ['==', '$type', 'Polygon'], ['!=', 'mode', 'static']],
    layout: {
      'line-cap': 'round',
      'line-join': 'round',
    },
    paint: {
      'line-color': '#3B82F6',
      'line-dasharray': [2, 2],
      'line-width': 2.5,
    },
  },
  // Vertex points
  {
    id: 'gl-draw-polygon-and-line-vertex-active',
    type: 'circle',
    filter: ['all', ['==', 'meta', 'vertex'], ['==', '$type', 'Point'], ['!=', 'mode', 'static']],
    paint: {
      'circle-radius': 5,
      'circle-color': '#fff',
      'circle-stroke-color': '#3B82F6',
      'circle-stroke-width': 2,
    },
  },
  // Midpoints
  {
    id: 'gl-draw-polygon-midpoint',
    type: 'circle',
    filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'midpoint']],
    paint: {
      'circle-radius': 3,
      'circle-color': '#3B82F6',
    },
  },
  // Line (active, while drawing)
  {
    id: 'gl-draw-line',
    type: 'line',
    filter: ['all', ['==', '$type', 'LineString'], ['!=', 'mode', 'static']],
    layout: {
      'line-cap': 'round',
      'line-join': 'round',
    },
    paint: {
      'line-color': '#3B82F6',
      'line-dasharray': [2, 2],
      'line-width': 2.5,
    },
  },
];

export function DrawControl({
  map,
  isDrawMode,
  onDrawModeChange,
  onPolygonCreated,
  onPolygonCleared,
  hasPolygon,
}: DrawControlProps) {
  const drawRef = useRef<MapboxDraw | null>(null);

  // Initialize MapboxDraw on the raw map instance
  useEffect(() => {
    if (!map) return;
    const mapInstance = map.getMap();

    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {},
      defaultMode: 'simple_select',
      styles: DRAW_STYLES as unknown[],
    });

    drawRef.current = draw;
    mapInstance.addControl(draw as unknown as mapboxgl.IControl);

    const handleCreate = (e: { features: GeoJSON.Feature[] }) => {
      if (e.features.length > 0) {
        onPolygonCreated(e.features[0]);
        onDrawModeChange(false);
      }
    };

    mapInstance.on('draw.create', handleCreate);

    return () => {
      mapInstance.off('draw.create', handleCreate);
      try {
        mapInstance.removeControl(draw as unknown as mapboxgl.IControl);
      } catch {
        // Control may already be removed if map was destroyed
      }
      drawRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  const handleActivateDraw = useCallback(() => {
    if (!drawRef.current) return;
    // Clear any existing drawings first
    drawRef.current.deleteAll();
    drawRef.current.changeMode('draw_polygon');
    onDrawModeChange(true);
  }, [onDrawModeChange]);

  const handleClearDrawing = useCallback(() => {
    if (!drawRef.current) return;
    drawRef.current.deleteAll();
    onPolygonCleared();
    onDrawModeChange(false);
  }, [onPolygonCleared, onDrawModeChange]);

  return (
    <div className="absolute z-10" style={{ top: 160, right: 10 }}>
      <div className="flex flex-col gap-0.5">
        <button
          onClick={handleActivateDraw}
          className={`w-8 h-8 rounded-t-md shadow-md border border-gray-200
                     flex items-center justify-center
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                     transition-colors duration-150
                     ${isDrawMode
                       ? 'bg-blue-600 text-white hover:bg-blue-700'
                       : 'bg-white text-gray-700 hover:bg-gray-50 active:bg-gray-100'
                     }`}
          title="Draw analysis area"
          aria-label="Draw analysis area"
        >
          <Pencil className="w-4 h-4" />
        </button>
        <button
          onClick={handleClearDrawing}
          disabled={!hasPolygon && !isDrawMode}
          className={`w-8 h-8 rounded-b-md shadow-md border border-gray-200
                     flex items-center justify-center
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                     transition-colors duration-150
                     ${hasPolygon || isDrawMode
                       ? 'bg-white text-red-500 hover:bg-red-50 active:bg-red-100'
                       : 'bg-white text-gray-300 cursor-not-allowed'
                     }`}
          title="Clear drawing"
          aria-label="Clear drawing"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
