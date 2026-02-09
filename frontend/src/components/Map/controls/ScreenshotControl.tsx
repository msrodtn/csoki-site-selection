import { useCallback } from 'react';
import { Camera } from 'lucide-react';
import type { MapRef } from '@vis.gl/react-mapbox';

export interface ScreenshotControlProps {
  map: MapRef | null;
}

export function ScreenshotControl({ map }: ScreenshotControlProps) {
  const handleScreenshot = useCallback(() => {
    if (!map) return;
    const mapInstance = map.getMap();

    try {
      const canvas = mapInstance.getCanvas();
      const dataUrl = canvas.toDataURL('image/png');

      const link = document.createElement('a');
      link.download = `csoki-map-${new Date().toISOString().split('T')[0]}.png`;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('Map screenshot failed:', err);
    }
  }, [map]);

  return (
    <div className="absolute z-10" style={{ top: 120, right: 10 }}>
      <button
        onClick={handleScreenshot}
        className="w-8 h-8 bg-white rounded-md shadow-md border border-gray-200
                   flex items-center justify-center text-gray-700
                   hover:bg-gray-50 active:bg-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                   transition-colors duration-150"
        title="Screenshot map"
        aria-label="Screenshot map"
      >
        <Camera className="w-4 h-4" />
      </button>
    </div>
  );
}
