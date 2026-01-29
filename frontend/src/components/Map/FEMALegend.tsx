import { Info } from 'lucide-react';

interface FEMALegendProps {
  isVisible: boolean;
}

export function FEMALegend({ isVisible }: FEMALegendProps) {
  if (!isVisible) return null;

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-white rounded-lg shadow-lg p-3 max-w-[200px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <Info className="w-4 h-4 text-blue-600" />
        <h3 className="text-sm font-semibold text-gray-800">FEMA Flood Zones</h3>
      </div>

      <div className="space-y-1.5 text-xs">
        {/* High Risk - Special Flood Hazard Areas */}
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border border-gray-300"
            style={{ backgroundColor: '#6699FF' }}
          />
          <div>
            <span className="font-medium text-gray-700">Zone A, AE</span>
            <p className="text-gray-500">High risk (1% annual)</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border border-gray-300"
            style={{ backgroundColor: '#7D4FC9' }}
          />
          <div>
            <span className="font-medium text-gray-700">Zone V, VE</span>
            <p className="text-gray-500">Coastal high hazard</p>
          </div>
        </div>

        {/* Moderate Risk */}
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border border-gray-300"
            style={{ backgroundColor: '#FFA500' }}
          />
          <div>
            <span className="font-medium text-gray-700">Zone X (shaded)</span>
            <p className="text-gray-500">Moderate (0.2% annual)</p>
          </div>
        </div>

        {/* Minimal/Undetermined */}
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border border-gray-300 bg-white"
          />
          <div>
            <span className="font-medium text-gray-700">Zone X, D</span>
            <p className="text-gray-500">Minimal/Undetermined</p>
          </div>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-200">
        Zoom to 12+ for flood data
      </p>
    </div>
  );
}
