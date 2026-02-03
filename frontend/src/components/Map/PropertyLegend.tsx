import { DollarSign, TrendingUp } from 'lucide-react';
import { PROPERTY_TYPE_COLORS, PROPERTY_TYPE_LABELS, type PropertyType } from '../../types/store';

interface PropertyLegendProps {
  isVisible: boolean;
  propertyCount?: number;
  isLoading?: boolean;
  error?: string | null;
}

export function PropertyLegend({ isVisible, propertyCount = 0, isLoading = false, error = null }: PropertyLegendProps) {
  if (!isVisible) return null;

  const propertyTypes: PropertyType[] = ['retail', 'land', 'office', 'industrial', 'mixed_use'];

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-white rounded-lg shadow-lg p-3 min-w-[200px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <DollarSign className="w-4 h-4 text-green-600" />
        <span className="font-semibold text-sm text-gray-800">Properties For Sale</span>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Searching...
        </div>
      ) : error ? (
        <div className="text-xs text-red-500">
          {error}
        </div>
      ) : (
        <>
          {/* Marker type legend */}
          <div className="space-y-2 mb-3">
            <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Marker Types</div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 flex items-center justify-center">
                <div className="w-3 h-3 bg-purple-500 rotate-45" />
              </div>
              <span className="text-xs text-gray-600">Opportunity (likely to sell)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 flex items-center justify-center">
                <div className="w-3 h-3 bg-green-500 rounded-full" />
              </div>
              <span className="text-xs text-gray-600">Active Listing</span>
            </div>
          </div>

          {/* Property type colors */}
          <div className="space-y-1.5 pt-2 border-t border-gray-100">
            <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">Property Types</div>
            {propertyTypes.map((type) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: PROPERTY_TYPE_COLORS[type] }}
                />
                <span className="text-xs text-gray-600">{PROPERTY_TYPE_LABELS[type]}</span>
              </div>
            ))}
          </div>

          {/* Stats */}
          <div className="mt-2 pt-2 border-t border-gray-200">
            <div className="text-xs text-gray-500">
              Found: <span className="font-medium text-gray-700">{propertyCount}</span> properties
            </div>
            <div className="text-[10px] text-gray-400 mt-1">
              Source: ATTOM Property Data
            </div>
          </div>

          <div className="mt-2 pt-2 border-t border-gray-200 text-[10px] text-gray-400">
            <div className="flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              Click marker for details
            </div>
          </div>
        </>
      )}
    </div>
  );
}
