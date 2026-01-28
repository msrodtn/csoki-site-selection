import { useState, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';

export function SearchBar() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setViewport, setAllStatesVisible } = useMapStore();

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;

    // Check if Google Maps is loaded
    if (typeof google === 'undefined' || !google.maps) {
      setError('Map not loaded yet. Please wait and try again.');
      return;
    }

    setIsSearching(true);
    setError(null);

    try {
      // Use Google Geocoding API via the loaded Google Maps
      const geocoder = new google.maps.Geocoder();

      // Add "USA" to the query to focus on US locations
      const query = searchQuery.includes(',')
        ? searchQuery + ', USA'
        : searchQuery + ', USA';

      const result = await new Promise<google.maps.GeocoderResult[]>((resolve, reject) => {
        geocoder.geocode({ address: query }, (results, status) => {
          if (status === 'OK' && results && results.length > 0) {
            resolve(results);
          } else {
            reject(new Error('Location not found: ' + status));
          }
        });
      });

      const location = result[0].geometry.location;
      const lat = location.lat();
      const lng = location.lng();

      // Enable all states when searching to show stores in the searched area
      setAllStatesVisible(true);

      // Update viewport to center on the search result
      setViewport({
        latitude: lat,
        longitude: lng,
        zoom: 12,
      });

      setSearchQuery('');
    } catch (err) {
      setError('Location not found. Try a different search.');
      console.error('Geocoding error:', err);
    } finally {
      setIsSearching(false);
    }
  }, [searchQuery, setViewport, setAllStatesVisible]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const clearSearch = () => {
    setSearchQuery('');
    setError(null);
  };

  return (
    <div className="p-4 border-b border-gray-200">
      <h3 className="font-semibold text-gray-800 mb-3">Search Location</h3>

      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter city or zip code..."
          className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm placeholder-gray-400"
          disabled={isSearching}
        />

        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
        />

        {searchQuery && (
          <button
            onClick={clearSearch}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <button
        onClick={handleSearch}
        disabled={!searchQuery.trim() || isSearching}
        className="w-full mt-2 py-2 px-4 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium transition-colors"
      >
        {isSearching ? 'Searching...' : 'Search'}
      </button>

      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}

      <p className="mt-2 text-xs text-gray-500">
        Examples: "Des Moines, IA" or "50309"
      </p>
    </div>
  );
}
