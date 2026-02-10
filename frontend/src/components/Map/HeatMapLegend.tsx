import { Flame, ShoppingBag, Film, UtensilsCrossed } from 'lucide-react';

interface HeatMapLegendProps {
  isVisible: boolean;
}

export function HeatMapLegend({ isVisible }: HeatMapLegendProps) {
  if (!isVisible) return null;

  return (
    <div className="absolute bottom-4 left-4 z-10 bg-white rounded-lg shadow-lg p-3 max-w-[200px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <Flame className="w-4 h-4 text-orange-500" />
        <h3 className="text-sm font-semibold text-gray-800">Activity Nodes</h3>
      </div>

      <div className="space-y-1.5 text-xs">
        <div className="flex items-center gap-2">
          <div
            className="w-16 h-3 rounded"
            style={{
              background: 'linear-gradient(to right, rgba(0, 200, 0, 0.4), rgba(255, 255, 0, 0.7), rgba(255, 165, 0, 0.85), rgba(255, 0, 0, 1))',
            }}
          />
        </div>
        <div className="flex justify-between text-gray-500">
          <span>Low</span>
          <span>High</span>
        </div>
      </div>

      <div className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-200 space-y-0.5">
        <div className="flex items-center gap-1">
          <ShoppingBag className="w-3 h-3" /> Shopping (big box, malls)
        </div>
        <div className="flex items-center gap-1">
          <Film className="w-3 h-3" /> Entertainment / Attractions
        </div>
        <div className="flex items-center gap-1">
          <UtensilsCrossed className="w-3 h-3" /> Dining (QSR, restaurants)
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mt-1">Category overlap = hotter zones</p>
    </div>
  );
}
