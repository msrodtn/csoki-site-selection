import { useMapStore } from '../../store/useMapStore';
import { useStoreStats } from '../../hooks/useStores';
import { BRAND_COLORS, BRAND_LABELS, BRAND_LOGOS, type BrandKey } from '../../types/store';
import { Eye, EyeOff } from 'lucide-react';

export function BrandFilter() {
  const { visibleBrands, toggleBrand, setAllBrandsVisible } = useMapStore();
  const { data: stats, isLoading } = useStoreStats();

  const allVisible = stats ? visibleBrands.size >= stats.length : visibleBrands.size > 0;

  if (isLoading) {
    return (
      <div className="p-4">
        <div className="animate-pulse space-y-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-10 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800">Competitors</h3>
        <button
          onClick={() => setAllBrandsVisible(!allVisible)}
          className="text-xs text-blue-600 hover:text-blue-800"
        >
          {allVisible ? 'Hide All' : 'Show All'}
        </button>
      </div>

      <div className="space-y-2">
        {stats?.map((stat) => {
          const brandKey = stat.brand as BrandKey;
          const isVisible = visibleBrands.has(brandKey);
          const color = BRAND_COLORS[brandKey] || '#666';
          const label = BRAND_LABELS[brandKey] || stat.brand;
          const logo = BRAND_LOGOS[brandKey];

          return (
            <button
              key={stat.brand}
              onClick={() => toggleBrand(brandKey)}
              className={
                'w-full flex items-center justify-between p-2 rounded-lg transition-all duration-150 text-left ' +
                (isVisible
                  ? 'bg-gray-50 hover:bg-gray-100'
                  : 'bg-gray-100 opacity-50 hover:opacity-75')
              }
            >
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full border border-gray-200 bg-white flex items-center justify-center flex-shrink-0">
                  {logo ? (
                    <img
                      src={logo}
                      alt={label}
                      className="w-5 h-5 object-contain rounded-full"
                    />
                  ) : (
                    <div
                      className="w-5 h-5 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                  )}
                </div>
                <span className="text-sm font-medium truncate">{label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">
                  {stat.count.toLocaleString()}
                </span>
                {isVisible ? (
                  <Eye className="w-4 h-4 text-gray-400" />
                ) : (
                  <EyeOff className="w-4 h-4 text-gray-300" />
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="text-sm text-gray-600">
          <span className="font-medium">Total stores:</span>{' '}
          {stats?.reduce((sum, s) => sum + s.count, 0).toLocaleString()}
        </div>
      </div>
    </div>
  );
}
