/**
 * Competitor Access Panel
 *
 * Displays drive-time analysis from a potential site to nearby competitors.
 * Uses Mapbox Matrix API for accurate travel time calculations.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  X,
  Car,
  Clock,
  MapPin,
  Navigation,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Route,
  Download,
  Filter,
} from 'lucide-react';
import { analysisApi } from '../../services/api';
import { useMapStore } from '../../store/useMapStore';
import {
  BRAND_COLORS,
  BRAND_LABELS,
  BRAND_LOGOS,
  type BrandKey,
  type TravelProfile,
  type CompetitorAccessResponse,
  type CompetitorWithTravelTime,
} from '../../types/store';

interface CompetitorAccessPanelProps {
  latitude: number;
  longitude: number;
  onClose: () => void;
  onNavigateToCompetitor?: (lat: number, lng: number) => void;
}

const PROFILE_OPTIONS: { value: TravelProfile; label: string; icon: React.ReactNode }[] = [
  { value: 'driving', label: 'Driving', icon: <Car className="w-4 h-4" /> },
  { value: 'driving-traffic', label: 'With Traffic', icon: <Route className="w-4 h-4" /> },
];

// Format duration in minutes/hours
function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'N/A';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

// Format distance in miles
function formatDistance(meters: number | null): string {
  if (meters === null) return 'N/A';
  const miles = meters / 1609.34;
  return `${miles.toFixed(1)} mi`;
}

// Get color based on travel time
function getTravelTimeColor(seconds: number | null): string {
  if (seconds === null) return 'text-gray-400';
  const minutes = seconds / 60;
  if (minutes <= 5) return 'text-green-600';
  if (minutes <= 10) return 'text-lime-600';
  if (minutes <= 15) return 'text-yellow-600';
  if (minutes <= 20) return 'text-orange-600';
  return 'text-red-600';
}

export function CompetitorAccessPanel({
  latitude,
  longitude,
  onClose,
  onNavigateToCompetitor,
}: CompetitorAccessPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompetitorAccessResponse | null>(null);
  const [profile, setProfile] = useState<TravelProfile>('driving-traffic');
  const [expandedBrands, setExpandedBrands] = useState<Set<string>>(new Set());
  const [maxCompetitors] = useState(25);

  // Filter and sort state
  const [maxTravelTime, setMaxTravelTime] = useState<number>(60); // minutes
  const [sortBy, setSortBy] = useState<'time' | 'distance' | 'brand'>('time');
  const [showFilters, setShowFilters] = useState(false);

  const { navigateTo } = useMapStore();

  // Export to CSV function
  const exportToCSV = useCallback(() => {
    if (!result?.competitors) return;

    const headers = ['Brand', 'Address', 'City', 'State', 'Travel Time (min)', 'Distance (mi)'];
    const rows = result.competitors
      .filter(c => !maxTravelTime || (c.travel_time_minutes || 0) <= maxTravelTime)
      .map(c => [
        c.brand,
        c.street || '',
        c.city || '',
        c.state || '',
        c.travel_time_minutes?.toFixed(1) || '',
        c.distance_miles?.toFixed(1) || '',
      ]);

    const csv = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `competitor-access-${latitude.toFixed(4)}-${longitude.toFixed(4)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [result, maxTravelTime, latitude, longitude]);

  // Fetch competitor access data
  const fetchCompetitorAccess = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await analysisApi.analyzeCompetitorAccess({
        site_latitude: latitude,
        site_longitude: longitude,
        profile,
        max_competitors: maxCompetitors,
      });
      setResult(response);

      // Auto-expand brands with competitors
      const brandsWithCompetitors = new Set(
        response.competitors.map((c) => c.brand)
      );
      setExpandedBrands(brandsWithCompetitors);
    } catch (err) {
      console.error('Error fetching competitor access:', err);
      setError(err instanceof Error ? err.message : 'Failed to analyze competitor access');
    } finally {
      setIsLoading(false);
    }
  }, [latitude, longitude, profile, maxCompetitors]);

  // Fetch on mount and when parameters change
  useEffect(() => {
    fetchCompetitorAccess();
  }, [fetchCompetitorAccess]);

  // Filter competitors by travel time
  const filteredCompetitors = useMemo(() => {
    if (!result?.competitors) return [];
    return result.competitors.filter(c => {
      if (maxTravelTime && c.travel_time_minutes != null) {
        return c.travel_time_minutes <= maxTravelTime;
      }
      return true;
    });
  }, [result?.competitors, maxTravelTime]);

  // Sort competitors
  const sortedCompetitors = useMemo(() => {
    const sorted = [...filteredCompetitors];
    switch (sortBy) {
      case 'time':
        sorted.sort((a, b) => (a.travel_time_seconds || Infinity) - (b.travel_time_seconds || Infinity));
        break;
      case 'distance':
        sorted.sort((a, b) => (a.distance_meters || Infinity) - (b.distance_meters || Infinity));
        break;
      case 'brand':
        sorted.sort((a, b) => a.brand.localeCompare(b.brand));
        break;
    }
    return sorted;
  }, [filteredCompetitors, sortBy]);

  // Group competitors by brand
  const competitorsByBrand = useMemo(() => {
    return sortedCompetitors.reduce<Record<string, CompetitorWithTravelTime[]>>(
      (acc, competitor) => {
        const brand = competitor.brand;
        if (!acc[brand]) acc[brand] = [];
        acc[brand].push(competitor);
        return acc;
      },
      {}
    );
  }, [sortedCompetitors]);

  // Toggle brand expansion
  const toggleBrand = (brand: string) => {
    setExpandedBrands((prev) => {
      const next = new Set(prev);
      if (next.has(brand)) {
        next.delete(brand);
      } else {
        next.add(brand);
      }
      return next;
    });
  };

  // Navigate to competitor on map
  const handleNavigateToCompetitor = (competitor: CompetitorWithTravelTime) => {
    if (competitor.latitude && competitor.longitude) {
      navigateTo(competitor.latitude, competitor.longitude, 14);
      onNavigateToCompetitor?.(competitor.latitude, competitor.longitude);
    }
  };

  return (
    <div className="absolute top-4 right-4 w-96 bg-white rounded-lg shadow-xl z-50 max-h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Car className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Competitor Access</h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full transition-colors"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Controls */}
      <div className="p-4 border-b border-gray-100 space-y-3">
        {/* Site location */}
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <MapPin className="w-4 h-4 text-red-500" />
          <span>
            Site: {latitude.toFixed(4)}, {longitude.toFixed(4)}
          </span>
        </div>

        {/* Profile selector */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Mode:</span>
          <div className="flex gap-1">
            {PROFILE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setProfile(option.value)}
                className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-md transition-colors ${
                  profile === option.value
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {option.icon}
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={fetchCompetitorAccess}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-md transition-colors ${
              showFilters ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filter
          </button>
          <button
            onClick={exportToCSV}
            disabled={!result?.competitors?.length}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-green-100 text-green-700 hover:bg-green-200 rounded-md transition-colors disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>

        {/* Filter controls (collapsible) */}
        {showFilters && (
          <div className="p-3 bg-gray-50 rounded-lg space-y-3">
            {/* Max travel time filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 w-24">Max time:</span>
              <select
                value={maxTravelTime}
                onChange={(e) => setMaxTravelTime(Number(e.target.value))}
                className="flex-1 text-sm border border-gray-300 rounded-md px-2 py-1"
              >
                <option value={5}>Within 5 min</option>
                <option value={10}>Within 10 min</option>
                <option value={15}>Within 15 min</option>
                <option value={20}>Within 20 min</option>
                <option value={30}>Within 30 min</option>
                <option value={60}>Within 1 hour</option>
              </select>
            </div>

            {/* Sort by */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 w-24">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'time' | 'distance' | 'brand')}
                className="flex-1 text-sm border border-gray-300 rounded-md px-2 py-1"
              >
                <option value="time">Travel Time</option>
                <option value="distance">Distance</option>
                <option value="brand">Brand</option>
              </select>
            </div>

            {/* Filter summary */}
            <div className="text-xs text-gray-500">
              Showing {filteredCompetitors.length} of {result?.competitors?.length || 0} competitors
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="flex items-center gap-2 p-4 bg-red-50 text-red-700 rounded-md">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Results */}
        {result && !isLoading && !error && (
          <div className="space-y-3">
            {/* Summary */}
            <div className="text-sm text-gray-600 pb-2 border-b">
              Found {result.competitors.length} competitors within range
            </div>

            {/* Competitors by brand */}
            {Object.entries(competitorsByBrand).map(([brand, competitors]) => {
              const brandKey = brand as BrandKey;
              const isExpanded = expandedBrands.has(brand);
              const brandColor = BRAND_COLORS[brandKey] || '#666666';
              const brandLabel = BRAND_LABELS[brandKey] || brand;
              const brandLogo = BRAND_LOGOS[brandKey];

              // Calculate average travel time for this brand
              const avgTime =
                competitors.reduce((sum, c) => sum + (c.travel_time_seconds || 0), 0) /
                competitors.length;

              return (
                <div key={brand} className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* Brand header */}
                  <button
                    onClick={() => toggleBrand(brand)}
                    className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      {brandLogo ? (
                        <img
                          src={brandLogo}
                          alt={brand}
                          className="w-6 h-6 rounded-full object-cover"
                          style={{ border: `2px solid ${brandColor}` }}
                        />
                      ) : (
                        <div
                          className="w-6 h-6 rounded-full"
                          style={{ backgroundColor: brandColor }}
                        />
                      )}
                      <span className="font-medium text-gray-900">{brandLabel}</span>
                      <span className="text-sm text-gray-500">({competitors.length})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${getTravelTimeColor(avgTime)}`}>
                        avg {formatDuration(avgTime)}
                      </span>
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-gray-400" />
                      )}
                    </div>
                  </button>

                  {/* Competitor list */}
                  {isExpanded && (
                    <div className="divide-y divide-gray-100">
                      {competitors.map((competitor, idx) => (
                        <div
                          key={competitor.id || idx}
                          className="p-3 hover:bg-gray-50 transition-colors cursor-pointer"
                          onClick={() => handleNavigateToCompetitor(competitor)}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-gray-900 truncate">
                                {competitor.street || 'Unknown address'}
                              </p>
                              <p className="text-xs text-gray-500">
                                {competitor.city}, {competitor.state}
                              </p>
                            </div>
                            <div className="flex flex-col items-end ml-3">
                              <div className={`flex items-center gap-1 ${getTravelTimeColor(competitor.travel_time_seconds)}`}>
                                <Clock className="w-3.5 h-3.5" />
                                <span className="text-sm font-medium">
                                  {formatDuration(competitor.travel_time_seconds)}
                                </span>
                              </div>
                              <span className="text-xs text-gray-400">
                                {formatDistance(competitor.distance_meters)}
                              </span>
                            </div>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleNavigateToCompetitor(competitor);
                            }}
                            className="mt-2 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
                          >
                            <Navigation className="w-3 h-3" />
                            Navigate to store
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Empty state */}
            {Object.keys(competitorsByBrand).length === 0 && (
              <div className="text-center py-8 text-gray-500">
                <MapPin className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>No competitors found nearby</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200 bg-gray-50 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Travel times via Mapbox Matrix API
          {result?.profile === 'driving-traffic' && ' (with live traffic)'}
        </div>
      </div>
    </div>
  );
}

export default CompetitorAccessPanel;
