/**
 * Mapbox Geocoding Search Bar
 *
 * Uses Mapbox Geocoding API for city/address autocomplete
 * as an alternative to Google Places Autocomplete.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, X, MapPin } from 'lucide-react';

// Try runtime config first (for Docker), then build-time env vars
const MAPBOX_TOKEN = 
  (window as any).RUNTIME_CONFIG?.MAPBOX_TOKEN || 
  import.meta.env.VITE_MAPBOX_TOKEN || 
  import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 
  '';

interface GeocodingFeature {
  id: string;
  place_name: string;
  text: string;
  center: [number, number]; // [lng, lat]
  place_type: string[];
  // Context can be array (v5) or object (v6)
  context?: Array<{
    id: string;
    text: string;
    short_code?: string;
  }> | any;
}

interface MapboxSearchBarProps {
  onSelect: (lng: number, lat: number, placeName: string, placeType: string) => void;
  placeholder?: string;
}

export function MapboxSearchBar({
  onSelect,
  placeholder = 'Search city or address...',
}: MapboxSearchBarProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<GeocodingFeature[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debounceTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle clicks outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch suggestions from Mapbox Geocoding API
  const fetchSuggestions = useCallback(async (searchText: string) => {
    if (!MAPBOX_TOKEN || searchText.length < 2) {
      setSuggestions([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Use Mapbox Geocoding API v6
      const params = new URLSearchParams({
        q: searchText,
        access_token: MAPBOX_TOKEN,
        country: 'US',
        types: 'place,locality,neighborhood,address,postcode',
        limit: '5',
      });

      const response = await fetch(
        `https://api.mapbox.com/search/geocode/v6/forward?${params}`
      );

      if (!response.ok) {
        throw new Error('Geocoding request failed');
      }

      const data = await response.json();

      // Map v6 response format to our interface
      const features: GeocodingFeature[] = (data.features || []).map((f: any) => ({
        id: f.id,
        place_name: f.properties.full_address || f.properties.name,
        text: f.properties.name,
        center: f.geometry.coordinates,
        place_type: [f.properties.feature_type],
        context: f.properties.context,
      }));

      setSuggestions(features);
      setShowSuggestions(features.length > 0);
    } catch (err) {
      console.error('Geocoding error:', err);
      setError('Search failed');
      setSuggestions([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle input change with debounce
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    setError(null);

    if (debounceTimeout.current) {
      clearTimeout(debounceTimeout.current);
    }

    if (value.trim().length >= 2) {
      debounceTimeout.current = setTimeout(() => {
        fetchSuggestions(value);
      }, 300);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  // Handle suggestion selection
  const handleSelectSuggestion = useCallback(
    (feature: GeocodingFeature) => {
      const [lng, lat] = feature.center;
      setQuery(feature.text);
      setSuggestions([]);
      setShowSuggestions(false);
      onSelect(lng, lat, feature.place_name, feature.place_type[0] || 'place');
    },
    [onSelect]
  );

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setShowSuggestions(false);
    } else if (e.key === 'Enter' && suggestions.length > 0) {
      e.preventDefault();
      handleSelectSuggestion(suggestions[0]);
    }
  };

  const clearSearch = () => {
    setQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    setError(null);
  };

  // Extract state from context (API v6 format - context is now an object)
  const getStateFromFeature = (feature: GeocodingFeature): string => {
    if (feature.context) {
      // API v6: context is object like { region: {...}, country: {...} }
      if (Array.isArray(feature.context)) {
        // Fallback for v5 array format
        const region = feature.context.find((c) => c.id.startsWith('region'));
        if (region?.short_code) {
          return region.short_code.replace('US-', '');
        }
      } else {
        // v6 object format
        const contextObj = feature.context as any;
        if (contextObj.region?.region_code) {
          return contextObj.region.region_code;
        }
      }
    }
    return '';
  };

  if (!MAPBOX_TOKEN) {
    return (
      <div className="p-4 border-b border-gray-200">
        <div className="text-xs text-amber-600 bg-amber-50 p-2 rounded">
          Mapbox token not configured
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 border-b border-gray-200" ref={containerRef}>
      <h3 className="font-semibold text-gray-800 mb-3">Search Location</h3>

      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          placeholder={placeholder}
          className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm placeholder-gray-400"
          disabled={isLoading}
        />

        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />

        {query && !isLoading && (
          <button
            onClick={clearSearch}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
          </div>
        )}

        {/* Suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
            {suggestions.map((feature) => (
              <button
                key={feature.id}
                onClick={() => handleSelectSuggestion(feature)}
                className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-50 text-left transition-colors border-b border-gray-100 last:border-b-0"
              >
                <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {feature.text}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {feature.place_name}
                  </div>
                </div>
                {getStateFromFeature(feature) && (
                  <span className="ml-auto text-xs text-gray-400">
                    {getStateFromFeature(feature)}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <p className="mt-2 text-xs text-gray-500">
        Powered by Mapbox Geocoding API
      </p>
    </div>
  );
}
