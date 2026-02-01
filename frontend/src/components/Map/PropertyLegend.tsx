import { DollarSign, ExternalLink } from 'lucide-react';
import { PROPERTY_TYPE_COLORS, PROPERTY_TYPE_LABELS, type PropertyType } from '../../types/store';
import { useMapStore } from '../../store/useMapStore';

interface PropertyLegendProps {
  isVisible: boolean;
}

export function PropertyLegend({ isVisible }: PropertyLegendProps) {
  const { propertySearchResult, isPropertySearching, propertySearchError } = useMapStore();

  if (!isVisible) return null;

  const propertyTypes: PropertyType[] = ['retail', 'land', 'office', 'industrial', 'mixed_use'];

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-white rounded-lg shadow-lg p-3 min-w-[180px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <DollarSign className="w-4 h-4 text-green-600" />
        <span className="font-semibold text-sm text-gray-800">Properties For Sale</span>
      </div>

      {isPropertySearching ? (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Searching...
        </div>
      ) : propertySearchError ? (
        <div className="text-xs text-red-500">
          {propertySearchError}
        </div>
      ) : (
        <>
          <div className="space-y-1.5">
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

          {propertySearchResult && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              <div className="text-xs text-gray-500">
                Found: <span className="font-medium text-gray-700">{propertySearchResult.total_found}</span> listings
              </div>
              <div className="text-[10px] text-gray-400 mt-1">
                Sources: {propertySearchResult.sources_searched.join(', ')}
              </div>
            </div>
          )}

          <div className="mt-2 pt-2 border-t border-gray-200 text-[10px] text-gray-400">
            <div className="flex items-center gap-1">
              <ExternalLink className="w-3 h-3" />
              Click marker to view listing
            </div>
          </div>
        </>
      )}
    </div>
  );
}
