import { useMemo } from 'react';
import { BRAND_COLORS, BRAND_LABELS, type BrandKey } from '../../types/store';
import type { Store } from '../../types/store';

interface QuickStatsBarProps {
  stores: Store[];
}

// Order brands by typical importance
const BRAND_ORDER: BrandKey[] = [
  'csoki',
  'russell_cellular',
  'verizon_corporate',
  'victra',
  'tmobile',
  'uscellular',
];

export function QuickStatsBar({ stores }: QuickStatsBarProps) {
  // Count stores by brand
  const brandCounts = useMemo(() => {
    const counts: Record<string, number> = {};

    for (const store of stores) {
      const brand = store.brand as BrandKey;
      counts[brand] = (counts[brand] || 0) + 1;
    }

    return counts;
  }, [stores]);

  // Get ordered brands with counts
  const brandStats = useMemo(() => {
    return BRAND_ORDER
      .filter(brand => brandCounts[brand] > 0)
      .map(brand => ({
        brand,
        count: brandCounts[brand] || 0,
        color: BRAND_COLORS[brand],
        label: BRAND_LABELS[brand],
      }));
  }, [brandCounts]);

  if (stores.length === 0) {
    return null;
  }

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg px-4 py-2 flex items-center gap-4">
      <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
        In View:
      </span>

      <div className="flex items-center gap-3">
        {brandStats.map(({ brand, count, color, label }) => (
          <div
            key={brand}
            className="flex items-center gap-1.5"
            title={label}
          >
            <div
              className="w-3 h-3 rounded-full border border-white shadow-sm"
              style={{ backgroundColor: color }}
            />
            <span className="text-sm font-medium text-gray-700">{count}</span>
          </div>
        ))}
      </div>

      <div className="border-l border-gray-300 pl-3 ml-1">
        <span className="text-sm font-semibold text-gray-800">
          {stores.length.toLocaleString()} total
        </span>
      </div>
    </div>
  );
}
