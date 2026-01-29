import { LandPlot } from 'lucide-react';

interface ParcelLegendProps {
  isVisible: boolean;
}

export function ParcelLegend({ isVisible }: ParcelLegendProps) {
  if (!isVisible) return null;

  return (
    <div className="absolute bottom-32 left-4 z-10 bg-white rounded-lg shadow-lg p-3 max-w-[200px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <LandPlot className="w-4 h-4 text-amber-700" />
        <h3 className="text-sm font-semibold text-gray-800">Parcel Boundaries</h3>
      </div>

      <div className="space-y-1.5 text-xs">
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border-2"
            style={{ borderColor: '#A16207', backgroundColor: 'transparent' }}
          />
          <div>
            <span className="font-medium text-gray-700">Property Lines</span>
            <p className="text-gray-500">Tax parcel boundaries</p>
          </div>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-200">
        Zoom to 14+ for parcel data
      </p>

      <p className="text-[10px] text-gray-400 mt-1">
        Data: Regrid via ArcGIS Living Atlas
      </p>
    </div>
  );
}
