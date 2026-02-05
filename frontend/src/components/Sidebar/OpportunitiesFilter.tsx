/**
 * OpportunitiesFilter - Filter controls for CSOKi Opportunities layer
 *
 * Allows users to customize the property search criteria:
 * - Parcel size range (default: 0.8-2 acres)
 * - Building size range (default: 2500-6000 sqft)
 * - Property type toggles (Land, Retail, Office)
 */

import { Diamond, SlidersHorizontal } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';

interface OpportunitiesFilterProps {
  isVisible: boolean;
}

export function OpportunitiesFilter({ isVisible }: OpportunitiesFilterProps) {
  const { opportunityFilters, setOpportunityFilters } = useMapStore();

  if (!isVisible) return null;

  const handleMinAcresChange = (value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 0) {
      setOpportunityFilters({ minParcelAcres: num });
    }
  };

  const handleMaxAcresChange = (value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 0) {
      setOpportunityFilters({ maxParcelAcres: num });
    }
  };

  const handleMinSqftChange = (value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && num >= 0) {
      setOpportunityFilters({ minBuildingSqft: num });
    }
  };

  const handleMaxSqftChange = (value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && num >= 0) {
      setOpportunityFilters({ maxBuildingSqft: num });
    }
  };

  return (
    <div className="p-4 border-b border-gray-200 bg-purple-50">
      <div className="flex items-center gap-2 mb-3">
        <Diamond className="w-5 h-5 text-purple-600" />
        <h3 className="font-semibold text-purple-900">Opportunity Filters</h3>
        <SlidersHorizontal className="w-4 h-4 text-purple-400 ml-auto" />
      </div>

      {/* Parcel Size Range */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-gray-600 mb-1.5">
          Parcel Size (acres)
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            step="0.1"
            min="0"
            value={opportunityFilters.minParcelAcres}
            onChange={(e) => handleMinAcresChange(e.target.value)}
            className="w-20 px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
          />
          <span className="text-gray-400 text-sm">to</span>
          <input
            type="number"
            step="0.1"
            min="0"
            value={opportunityFilters.maxParcelAcres}
            onChange={(e) => handleMaxAcresChange(e.target.value)}
            className="w-20 px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
          />
          <span className="text-gray-500 text-xs">ac</span>
        </div>
      </div>

      {/* Building Size Range */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-gray-600 mb-1.5">
          Building Size (sqft)
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            step="100"
            min="0"
            value={opportunityFilters.minBuildingSqft}
            onChange={(e) => handleMinSqftChange(e.target.value)}
            className="w-24 px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
          />
          <span className="text-gray-400 text-sm">to</span>
          <input
            type="number"
            step="100"
            min="0"
            value={opportunityFilters.maxBuildingSqft}
            onChange={(e) => handleMaxSqftChange(e.target.value)}
            className="w-24 px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
          />
          <span className="text-gray-500 text-xs">sf</span>
        </div>
      </div>

      {/* Property Type Toggles */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-2">
          Property Types
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() =>
              setOpportunityFilters({ includeLand: !opportunityFilters.includeLand })
            }
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
              opportunityFilters.includeLand
                ? 'bg-purple-600 text-white'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            Land
          </button>
          <button
            onClick={() =>
              setOpportunityFilters({ includeRetail: !opportunityFilters.includeRetail })
            }
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
              opportunityFilters.includeRetail
                ? 'bg-purple-600 text-white'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            Retail
          </button>
          <button
            onClick={() =>
              setOpportunityFilters({ includeOffice: !opportunityFilters.includeOffice })
            }
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
              opportunityFilters.includeOffice
                ? 'bg-purple-600 text-white'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            Office
          </button>
        </div>
      </div>

      {/* Reset to Defaults */}
      <button
        onClick={() =>
          setOpportunityFilters({
            minParcelAcres: 0.8,
            maxParcelAcres: 2.0,
            minBuildingSqft: 2500,
            maxBuildingSqft: 6000,
            includeLand: true,
            includeRetail: true,
            includeOffice: true,
          })
        }
        className="mt-3 text-xs text-purple-600 hover:text-purple-800 hover:underline"
      >
        Reset to defaults
      </button>
    </div>
  );
}

export default OpportunitiesFilter;
