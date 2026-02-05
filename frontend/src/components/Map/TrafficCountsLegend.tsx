import { BarChart2 } from 'lucide-react';

interface TrafficCountsLegendProps {
  isVisible: boolean;
}

export function TrafficCountsLegend({ isVisible }: TrafficCountsLegendProps) {
  if (!isVisible) return null;

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-white rounded-lg shadow-lg p-3 max-w-[200px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <BarChart2 className="w-4 h-4 text-purple-600" />
        <h3 className="text-sm font-semibold text-gray-800">Traffic Counts</h3>
      </div>

      <div className="space-y-1.5 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded" style={{ backgroundColor: '#3B82F6' }} />
          <span className="text-gray-600">0-999/day</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded" style={{ backgroundColor: '#10B981' }} />
          <span className="text-gray-600">1,000-1,999/day</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded" style={{ backgroundColor: '#F59E0B' }} />
          <span className="text-gray-600">2,000-4,999/day</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded" style={{ backgroundColor: '#EF4444' }} />
          <span className="text-gray-600">5,000+/day</span>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-100">
        Iowa DOT AADT Data
      </p>
    </div>
  );
}
