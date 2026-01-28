import { useState, useCallback, useEffect, useRef } from 'react';
import { Search, X, MapPin } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';

interface PlacePrediction {
  place_id: string;
  description: string;
  structured_formatting: {
    main_text: string;
    secondary_text: string;
  };
}

export function SearchBar() {
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState<PlacePrediction[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setViewport, setAllStatesVisible } = useMapStore();

  const autocompleteService = useRef<google.maps.places.AutocompleteService | null>(null);
  const placesService = useRef<google.maps.places.PlacesService | null>(null);
  const debounceTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize services when Google Maps loads
  useEffect(() => {
    const initServices = () => {
      if (typeof google !== 'undefined' && google.maps && google.maps.places) {
        autocompleteService.current = new google.maps.places.AutocompleteService();
        // PlacesService needs a DOM element or map
        const dummyDiv = document.createElement('div');
        placesService.current = new google.maps.places.PlacesService(dummyDiv);
      }
    };

    // Check immediately
    initServices();

    // Also check after a delay in case Google Maps loads later
    const timeout = setTimeout(initServices, 1000);
    return () => clearTimeout(timeout);
  }, []);

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

  // Fetch autocomplete suggestions
  const fetchSuggestions = useCallback((input: string) => {
    if (!autocompleteService.current || input.length < 2) {
      setSuggestions([]);
      return;
    }

    setIsLoading(true);

    autocompleteService.current.getPlacePredictions(
      {
        input,
        componentRestrictions: { country: 'us' },
        types: ['(cities)'], // Focus on cities
      },
      (predictions, status) => {
        setIsLoading(false);
        if (status === google.maps.places.PlacesServiceStatus.OK && predictions) {
          setSuggestions(predictions.slice(0, 5));
          setShowSuggestions(true);
        } else {
          setSuggestions([]);
        }
      }
    );
  }, []);

  // Handle input change with debounce
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    setError(null);

    // Debounce API calls
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
  const handleSelectSuggestion = useCallback((prediction: PlacePrediction) => {
    if (!placesService.current) {
      setError('Places service not available');
      return;
    }

    setIsLoading(true);
    setShowSuggestions(false);
    setSearchQuery(prediction.structured_formatting.main_text);

    placesService.current.getDetails(
      {
        placeId: prediction.place_id,
        fields: ['geometry'],
      },
      (place, status) => {
        setIsLoading(false);
        if (status === google.maps.places.PlacesServiceStatus.OK && place?.geometry?.location) {
          const lat = place.geometry.location.lat();
          const lng = place.geometry.location.lng();

          // Enable all states to show stores in searched area
          setAllStatesVisible(true);

          // Zoom to location
          setViewport({
            latitude: lat,
            longitude: lng,
            zoom: 12,
          });

          setSearchQuery('');
          setSuggestions([]);
        } else {
          setError('Could not get location details');
        }
      }
    );
  }, [setViewport, setAllStatesVisible]);

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
    setSearchQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    setError(null);
  };

  return (
    <div className="p-4 border-b border-gray-200" ref={containerRef}>
      <h3 className="font-semibold text-gray-800 mb-3">Search Location</h3>

      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          placeholder="Type a city name..."
          className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm placeholder-gray-400"
          disabled={isLoading}
        />

        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
        />

        {searchQuery && !isLoading && (
          <button
            onClick={clearSearch}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-gray-300 border-t-red-500 rounded-full animate-spin" />
          </div>
        )}

        {/* Suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
            {suggestions.map((prediction) => (
              <button
                key={prediction.place_id}
                onClick={() => handleSelectSuggestion(prediction)}
                className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-50 text-left transition-colors border-b border-gray-100 last:border-b-0"
              >
                <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {prediction.structured_formatting.main_text}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {prediction.structured_formatting.secondary_text}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}

      <p className="mt-2 text-xs text-gray-500">
        Start typing to see suggestions
      </p>
    </div>
  );
}
