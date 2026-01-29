import { useState, useEffect, useCallback } from 'react';
import {
  X,
  Trash2,
  MapPin,
  Users,
  DollarSign,
  Loader2,
  ArrowRight,
  GripHorizontal,
} from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';
import { analysisApi } from '../../services/api';
import type { SavedLocation, DemographicsResponse, BrandKey } from '../../types/store';
import { BRAND_COLORS, BRAND_LABELS, BRAND_LOGOS } from '../../types/store';

// Format numbers with commas
const formatNumber = (num: number | null): string => {
  if (num === null) return 'N/A';
  return num.toLocaleString();
};

// Format currency
const formatCurrency = (num: number | null): string => {
  if (num === null) return 'N/A';
  return '$' + num.toLocaleString();
};

export function ComparePanel() {
  const {
    savedLocations,
    removeSavedLocation,
    clearSavedLocations,
    showComparePanel,
    setShowComparePanel,
    navigateTo,
  } = useMapStore();

  const [loadingDemographics, setLoadingDemographics] = useState<Record<string, boolean>>({});
  const [demographicsCache, setDemographicsCache] = useState<Record<string, DemographicsResponse>>({});

  // Handle closing the panel - clear cache and saved locations for fresh comparison
  const handleClose = () => {
    setShowComparePanel(false);
    setDemographicsCache({});
    clearSavedLocations();
  };

  // Load demographics for saved locations that don't have it
  const loadDemographics = useCallback(async (location: SavedLocation) => {
    if (demographicsCache[location.id] || loadingDemographics[location.id]) return;

    setLoadingDemographics((prev) => ({ ...prev, [location.id]: true }));

    try {
      const data = await analysisApi.getDemographics({
        latitude: location.latitude,
        longitude: location.longitude,
      });
      setDemographicsCache((prev) => ({ ...prev, [location.id]: data }));
    } catch (error) {
      console.error('Failed to load demographics for comparison:', error);
    } finally {
      setLoadingDemographics((prev) => ({ ...prev, [location.id]: false }));
    }
  }, [demographicsCache, loadingDemographics]);

  // Load demographics for all saved locations when panel opens
  useEffect(() => {
    if (showComparePanel) {
      savedLocations.forEach((location) => {
        if (!demographicsCache[location.id]) {
          loadDemographics(location);
        }
      });
    }
  }, [showComparePanel, savedLocations, demographicsCache, loadDemographics]);

  if (!showComparePanel) return null;

  // Get 1-mile radius demographics for comparison
  const getMetrics = (locationId: string) => {
    const demo = demographicsCache[locationId];
    if (!demo) return null;
    return demo.radii.find((r) => r.radius_miles === 1) || demo.radii[0];
  };

  return (
    <div className="absolute top-4 right-4 z-30 bg-white rounded-lg shadow-xl w-[500px] max-h-[calc(100vh-2rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-gradient-to-r from-blue-600 to-blue-700 rounded-t-lg">
        <div className="flex items-center gap-2">
          <GripHorizontal className="w-4 h-4 text-white/70" />
          <h2 className="text-lg font-semibold text-white">Compare Locations</h2>
          <span className="text-sm text-white/70">({savedLocations.length} saved)</span>
        </div>
        <button
          onClick={handleClose}
          className="text-white/80 hover:text-white transition-colors"
          title="Close and clear comparison"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {savedLocations.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <MapPin className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="font-medium">No saved locations</p>
            <p className="text-sm mt-1">
              Use "Save for Compare" in the Trade Area Analysis panel to save locations.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Comparison Grid */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-semibold text-gray-600">Location</th>
                    {savedLocations.map((loc) => {
                      const brandKey = loc.brand as BrandKey | undefined;
                      const brandColor = brandKey ? BRAND_COLORS[brandKey] : '#666';
                      const brandLabel = brandKey ? BRAND_LABELS[brandKey] : loc.name;
                      const brandLogo = brandKey ? BRAND_LOGOS[brandKey] : null;
                      const locationSubtext = loc.city && loc.state ? `${loc.city}, ${loc.state}` : null;

                      return (
                        <th key={loc.id} className="text-center py-2 px-2 min-w-[120px]">
                          <div className="flex flex-col items-center gap-1">
                            {/* Brand logo */}
                            {brandLogo ? (
                              <img
                                src={brandLogo}
                                alt={brandLabel}
                                className="w-8 h-8 object-contain flex-shrink-0 rounded"
                                title={brandLabel}
                              />
                            ) : (
                              <div
                                className="w-8 h-8 rounded-full flex-shrink-0"
                                style={{ backgroundColor: brandColor }}
                                title={brandLabel}
                              />
                            )}
                            {/* Brand name */}
                            <span className="font-semibold text-gray-800 text-xs truncate max-w-[110px]" title={brandLabel}>
                              {brandLabel}
                            </span>
                            {/* City, State subtext */}
                            {locationSubtext && (
                              <span className="text-[10px] text-gray-400 truncate max-w-[110px]" title={locationSubtext}>
                                {locationSubtext}
                              </span>
                            )}
                            <div className="flex gap-1 mt-1">
                              <button
                                onClick={() => navigateTo(loc.latitude, loc.longitude, 14)}
                                className="text-blue-500 hover:text-blue-700"
                                title="Go to location"
                              >
                                <MapPin className="w-3 h-3" />
                              </button>
                              <button
                                onClick={() => removeSavedLocation(loc.id)}
                                className="text-red-400 hover:text-red-600"
                                title="Remove"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {/* Population Section */}
                  <tr className="bg-green-50">
                    <td colSpan={savedLocations.length + 1} className="py-2 px-2">
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-green-600" />
                        <span className="font-semibold text-green-800">Population (1 mi)</span>
                      </div>
                    </td>
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 px-2 text-gray-600">Total Pop.</td>
                    {savedLocations.map((loc) => {
                      const metrics = getMetrics(loc.id);
                      const isLoading = loadingDemographics[loc.id];
                      return (
                        <td key={loc.id} className="text-center py-2 px-2">
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mx-auto text-gray-400" />
                          ) : (
                            <span className="font-medium">{formatNumber(metrics?.total_population ?? null)}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 px-2 text-gray-600">Households</td>
                    {savedLocations.map((loc) => {
                      const metrics = getMetrics(loc.id);
                      const isLoading = loadingDemographics[loc.id];
                      return (
                        <td key={loc.id} className="text-center py-2 px-2">
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mx-auto text-gray-400" />
                          ) : (
                            <span className="font-medium">{formatNumber(metrics?.total_households ?? null)}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 px-2 text-gray-600">Median Age</td>
                    {savedLocations.map((loc) => {
                      const metrics = getMetrics(loc.id);
                      const isLoading = loadingDemographics[loc.id];
                      return (
                        <td key={loc.id} className="text-center py-2 px-2">
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mx-auto text-gray-400" />
                          ) : (
                            <span className="font-medium">{metrics?.median_age?.toFixed(1) || 'N/A'}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>

                  {/* Income Section */}
                  <tr className="bg-emerald-50">
                    <td colSpan={savedLocations.length + 1} className="py-2 px-2">
                      <div className="flex items-center gap-2">
                        <DollarSign className="w-4 h-4 text-emerald-600" />
                        <span className="font-semibold text-emerald-800">Income (1 mi)</span>
                      </div>
                    </td>
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 px-2 text-gray-600">Median HH</td>
                    {savedLocations.map((loc) => {
                      const metrics = getMetrics(loc.id);
                      const isLoading = loadingDemographics[loc.id];
                      return (
                        <td key={loc.id} className="text-center py-2 px-2">
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mx-auto text-gray-400" />
                          ) : (
                            <span className="font-medium">{formatCurrency(metrics?.median_household_income ?? null)}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 px-2 text-gray-600">Avg HH</td>
                    {savedLocations.map((loc) => {
                      const metrics = getMetrics(loc.id);
                      const isLoading = loadingDemographics[loc.id];
                      return (
                        <td key={loc.id} className="text-center py-2 px-2">
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mx-auto text-gray-400" />
                          ) : (
                            <span className="font-medium">{formatCurrency(metrics?.average_household_income ?? null)}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 px-2 text-gray-600">Per Capita</td>
                    {savedLocations.map((loc) => {
                      const metrics = getMetrics(loc.id);
                      const isLoading = loadingDemographics[loc.id];
                      return (
                        <td key={loc.id} className="text-center py-2 px-2">
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mx-auto text-gray-400" />
                          ) : (
                            <span className="font-medium">{formatCurrency(metrics?.per_capita_income ?? null)}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="text-xs text-gray-400 text-center">
              Demographics shown for 1-mile radius from each location
            </p>
          </div>
        )}
      </div>

      {/* Footer */}
      {savedLocations.length > 0 && (
        <div className="p-3 border-t bg-gray-50 rounded-b-lg">
          <p className="text-xs text-gray-500 text-center">
            <ArrowRight className="w-3 h-3 inline mr-1" />
            Click location pin to navigate on map
          </p>
        </div>
      )}
    </div>
  );
}
