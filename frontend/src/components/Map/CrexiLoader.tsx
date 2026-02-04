/**
 * Crexi Loader - Automated Crexi CSV export with adjustable filters
 * 
 * Allows users to load Crexi listings for a location with automated export.
 * Includes filter controls for acreage and square footage ranges.
 * 
 * Created by Subagent - Feb 4, 2026
 */

import React, { useState } from 'react';
import { X, Download, CheckCircle, AlertCircle, Loader, RefreshCw, MapPin, Sliders } from 'lucide-react';
import api from '../../services/api';

interface CrexiLoaderProps {
  onClose: () => void;
  onSuccess?: (count: number) => void;
  defaultLocation?: string;
}

interface CrexiAreaResponse {
  success: boolean;
  imported: number;
  updated: number;
  total_filtered: number;
  empty_land_count: number;
  small_building_count: number;
  cached: boolean;
  cache_age_minutes?: number;
  timestamp: string;
  expires_at: string;
  location: string;
  message?: string;
}

export const CrexiLoader: React.FC<CrexiLoaderProps> = ({
  onClose,
  onSuccess,
  defaultLocation = ''
}) => {
  const [location, setLocation] = useState(defaultLocation);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CrexiAreaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  
  // Filter state (future enhancement - not yet implemented in backend)
  const [minAcres, setMinAcres] = useState(0.8);
  const [maxAcres, setMaxAcres] = useState(2.0);
  const [minSqft, setMinSqft] = useState(2500);
  const [maxSqft, setMaxSqft] = useState(6000);
  const [propertyTypes, setPropertyTypes] = useState<string[]>(['Land', 'Retail', 'Office']);

  const handleLoad = async (forceRefresh: boolean = false) => {
    if (!location.trim()) {
      setError('Please enter a location');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.post('/listings/fetch-crexi-area', {
        location: location.trim(),
        property_types: propertyTypes.length > 0 ? propertyTypes : null,
        force_refresh: forceRefresh
      });

      setResult(response.data);
      
      if (response.data.success && onSuccess) {
        onSuccess(response.data.total_filtered);
      }
    } catch (err: any) {
      console.error('Crexi load error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to load Crexi listings';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    handleLoad(true);
  };

  const formatCacheAge = (minutes?: number): string => {
    if (!minutes) return 'just now';
    if (minutes < 60) return `${minutes} minutes ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days > 1 ? 's' : ''} ago`;
  };

  const togglePropertyType = (type: string) => {
    setPropertyTypes(prev => 
      prev.includes(type) 
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <Download className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Load Crexi Listings</h2>
              <p className="text-sm text-gray-500">Automated CSV export with smart filtering</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Location Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <MapPin className="w-4 h-4 inline mr-1" />
              Location
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., Des Moines, IA or 50309"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              disabled={loading}
            />
            <p className="text-xs text-gray-500 mt-1">
              Enter a city/state or ZIP code to search
            </p>
          </div>

          {/* Property Types */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Property Types
            </label>
            <div className="flex flex-wrap gap-2">
              {['Land', 'Retail', 'Office', 'Industrial'].map(type => (
                <button
                  key={type}
                  onClick={() => togglePropertyType(type)}
                  disabled={loading}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    propertyTypes.includes(type)
                      ? 'bg-emerald-100 text-emerald-700 border-2 border-emerald-400'
                      : 'bg-gray-100 text-gray-600 border-2 border-transparent hover:bg-gray-200'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* Advanced Filters Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
          >
            <Sliders className="w-4 h-4" />
            Advanced Filters {showFilters ? '▼' : '▶'}
          </button>

          {/* Advanced Filters (Collapsible) */}
          {showFilters && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Empty Land: {minAcres} - {maxAcres} acres
                </label>
                <div className="flex gap-4 items-center">
                  <input
                    type="range"
                    min="0.5"
                    max="3"
                    step="0.1"
                    value={minAcres}
                    onChange={(e) => setMinAcres(parseFloat(e.target.value))}
                    className="flex-1"
                  />
                  <input
                    type="range"
                    min="0.5"
                    max="3"
                    step="0.1"
                    value={maxAcres}
                    onChange={(e) => setMaxAcres(parseFloat(e.target.value))}
                    className="flex-1"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Small Buildings: {minSqft.toLocaleString()} - {maxSqft.toLocaleString()} sqft
                </label>
                <div className="flex gap-4 items-center">
                  <input
                    type="range"
                    min="1000"
                    max="10000"
                    step="100"
                    value={minSqft}
                    onChange={(e) => setMinSqft(parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <input
                    type="range"
                    min="1000"
                    max="10000"
                    step="100"
                    value={maxSqft}
                    onChange={(e) => setMaxSqft(parseInt(e.target.value))}
                    className="flex-1"
                  />
                </div>
              </div>

              <p className="text-xs text-amber-600">
                ⚠️ Note: Advanced filter controls are UI-only. Backend uses fixed criteria (0.8-2 acres, 2500-6000 sqft).
              </p>
            </div>
          )}

          {/* Load Button */}
          <button
            onClick={() => handleLoad(false)}
            disabled={loading || !location.trim()}
            className={`w-full py-3 px-4 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
              loading || !location.trim()
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-emerald-600 text-white hover:bg-emerald-700'
            }`}
          >
            {loading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Loading... (~60 seconds)
              </>
            ) : (
              <>
                <Download className="w-5 h-5" />
                Load Crexi Listings
              </>
            )}
          </button>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-900">Error</p>
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          )}

          {/* Success Result */}
          {result && result.success && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-3">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-emerald-900">
                    {result.message || 'Success!'}
                  </p>
                  <p className="text-sm text-emerald-700 mt-1">
                    Loaded <strong>{result.total_filtered}</strong> properties from Crexi
                  </p>
                </div>
                {result.cached && (
                  <button
                    onClick={handleRefresh}
                    className="text-emerald-600 hover:text-emerald-700 flex items-center gap-1 text-sm"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                  </button>
                )}
              </div>

              {/* Stats Breakdown */}
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div className="bg-white rounded-lg p-3">
                  <p className="text-xs text-gray-500">Empty Land</p>
                  <p className="text-2xl font-bold text-emerald-600">{result.empty_land_count}</p>
                  <p className="text-xs text-gray-500">0.8-2 acres</p>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <p className="text-xs text-gray-500">Small Buildings</p>
                  <p className="text-2xl font-bold text-emerald-600">{result.small_building_count}</p>
                  <p className="text-xs text-gray-500">2500-6000 sqft</p>
                </div>
              </div>

              {/* Cache Info */}
              {result.cached && (
                <div className="flex items-center gap-2 text-xs text-gray-600">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
                  Last updated {formatCacheAge(result.cache_age_minutes)}
                  <span className="text-gray-400">•</span>
                  <span>Expires {new Date(result.expires_at).toLocaleTimeString()}</span>
                </div>
              )}

              {/* Action Info */}
              {result.imported > 0 && (
                <p className="text-xs text-emerald-600">
                  ✓ {result.imported} new propert{result.imported === 1 ? 'y' : 'ies'} added to database
                </p>
              )}
              {result.updated > 0 && (
                <p className="text-xs text-emerald-600">
                  ✓ {result.updated} propert{result.updated === 1 ? 'y' : 'ies'} updated
                </p>
              )}
            </div>
          )}

          {/* Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-900 mb-2">How it works:</p>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>• Automatically logs into Crexi and exports CSV data</li>
              <li>• Filters for empty land (0.8-2 acres) OR small buildings (2500-6000 sqft)</li>
              <li>• Results cached for 24 hours per location</li>
              <li>• Properties appear as green pins on the map</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
