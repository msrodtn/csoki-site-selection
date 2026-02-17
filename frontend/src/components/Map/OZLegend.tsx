import { Info } from 'lucide-react';

interface OZLegendProps {
  isVisible: boolean;
}

export function OZLegend({ isVisible }: OZLegendProps) {
  if (!isVisible) return null;

  return (
    <div className="absolute bottom-4 left-4 z-10 bg-white rounded-lg shadow-lg p-3 max-w-[220px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <Info className="w-4 h-4 text-indigo-600" />
        <h3 className="text-sm font-semibold text-gray-800">Opportunity Zones</h3>
      </div>

      <div className="space-y-1.5 text-xs">
        {/* OZ 1.0 Designated */}
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border"
            style={{ backgroundColor: '#6366F133', borderColor: '#4F46E5' }}
          />
          <div>
            <span className="font-medium text-gray-700">Designated (1.0)</span>
            <p className="text-gray-500">Active through 2028</p>
          </div>
        </div>

        {/* OZ 2.0 Eligible */}
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded border-2 border-dashed"
            style={{ borderColor: '#F59E0B', backgroundColor: 'transparent' }}
          />
          <div>
            <span className="font-medium text-gray-700">Eligible (2.0 Preview)</span>
            <p className="text-gray-500">Not yet designated</p>
          </div>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-200">
        OZ 2.0 nominations: July 2026
      </p>
    </div>
  );
}
