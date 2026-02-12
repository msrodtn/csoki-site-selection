import { useState, useCallback, useRef, useEffect } from 'react';
import { Rocket, Info, Search, X, MapPin, ScanSearch, Crosshair } from 'lucide-react';

const MAPBOX_TOKEN =
  (window as any).RUNTIME_CONFIG?.MAPBOX_TOKEN ||
  import.meta.env.VITE_MAPBOX_TOKEN ||
  import.meta.env.VITE_MAPBOX_ACCESS_TOKEN ||
  '';

interface GeoResult {
  id: string;
  name: string;
  fullAddress: string;
  lng: number;
  lat: number;
  type: string;
  state?: string;
}

const RADIUS_OPTIONS = [
  { value: 5, label: '5 mi' },
  { value: 10, label: '10 mi' },
  { value: 25, label: '25 mi' },
  { value: 50, label: '50 mi' },
];

export function DeployPage() {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<GeoResult[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [selected, setSelected] = useState<GeoResult | null>(null);
  const [scope, setScope] = useState<'area' | 'targeted'>('area');
  const [radius, setRadius] = useState(10);
  const [isDeploying, setIsDeploying] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close suggestions on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const fetchSuggestions = useCallback(async (text: string) => {
    if (!MAPBOX_TOKEN || text.length < 2) {
      setSuggestions([]);
      return;
    }

    setIsSearching(true);
    try {
      const params = new URLSearchParams({
        q: text,
        access_token: MAPBOX_TOKEN,
        country: 'US',
        types: 'place,region,district,postcode,address',
        limit: '6',
      });

      const res = await fetch(`https://api.mapbox.com/search/geocode/v6/forward?${params}`);
      if (!res.ok) throw new Error('Geocoding failed');

      const data = await res.json();
      const results: GeoResult[] = (data.features || []).map((f: any) => {
        const ctx = f.properties.context || {};
        let state = '';
        if (ctx.region?.region_code) {
          state = ctx.region.region_code;
        }

        return {
          id: f.id,
          name: f.properties.name,
          fullAddress: f.properties.full_address || f.properties.name,
          lng: f.geometry.coordinates[0],
          lat: f.geometry.coordinates[1],
          type: f.properties.feature_type,
          state,
        };
      });

      setSuggestions(results);
      setShowSuggestions(results.length > 0);
    } catch (err) {
      console.error('Geocoding error:', err);
      setSuggestions([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    setSelected(null);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (value.trim().length >= 2) {
      debounceRef.current = setTimeout(() => fetchSuggestions(value), 300);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleSelect = (result: GeoResult) => {
    setSelected(result);
    setQuery(result.fullAddress);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const clearSearch = () => {
    setQuery('');
    setSelected(null);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setShowSuggestions(false);
    if (e.key === 'Enter' && suggestions.length > 0) {
      e.preventDefault();
      handleSelect(suggestions[0]);
    }
  };

  const typeLabel = (type: string) => {
    const labels: Record<string, string> = {
      place: 'City',
      region: 'State',
      district: 'County',
      postcode: 'ZIP Code',
      address: 'Address',
    };
    return labels[type] || type;
  };

  const handleDeploy = () => {
    setIsDeploying(true);
    // TODO: Call API to create job when Mac Mini is ready
    setTimeout(() => setIsDeploying(false), 2000);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900">Deploy Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">Configure and launch a new SCOUT analysis job</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
          {/* Location Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Location</label>
            <div ref={containerRef} className="relative">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={query}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                  placeholder="Search by city, state, ZIP code, county, or address..."
                  className="w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500 placeholder-gray-400"
                />
                {query && !isSearching && (
                  <button onClick={clearSearch} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    <X className="w-4 h-4" />
                  </button>
                )}
                {isSearching && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <div className="w-4 h-4 border-2 border-gray-300 border-t-red-500 rounded-full animate-spin" />
                  </div>
                )}
              </div>

              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                  {suggestions.map((result) => (
                    <button
                      key={result.id}
                      onClick={() => handleSelect(result)}
                      className="w-full px-3 py-2.5 flex items-center gap-3 hover:bg-gray-50 text-left transition-colors border-b border-gray-100 last:border-b-0"
                    >
                      <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-gray-800 truncate">{result.name}</div>
                        <div className="text-xs text-gray-500 truncate">{result.fullAddress}</div>
                      </div>
                      <span className="text-[10px] font-medium text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded flex-shrink-0">
                        {typeLabel(result.type)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected location display */}
            {selected && (
              <div className="mt-3 flex items-center gap-3 p-3 bg-red-50 border border-red-100 rounded-lg">
                <MapPin className="w-4 h-4 text-red-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{selected.fullAddress}</p>
                  <p className="text-xs text-gray-500">
                    {selected.lat.toFixed(4)}, {selected.lng.toFixed(4)}
                    {selected.state && ` · ${selected.state}`}
                  </p>
                </div>
                <span className="text-xs font-medium text-red-600 bg-red-100 px-2 py-0.5 rounded">
                  {typeLabel(selected.type)}
                </span>
              </div>
            )}
          </div>

          {/* Scope */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Analysis Mode</label>
            <div className="flex gap-3">
              <button
                onClick={() => setScope('area')}
                className={`flex-1 p-4 rounded-lg border-2 text-left transition-all ${
                  scope === 'area'
                    ? 'border-red-500 bg-red-50'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <ScanSearch className={`w-4 h-4 ${scope === 'area' ? 'text-red-600' : 'text-gray-400'}`} />
                  <span className={`font-medium text-sm ${scope === 'area' ? 'text-red-700' : 'text-gray-900'}`}>
                    Area Scan
                  </span>
                </div>
                <p className="text-xs text-gray-500 ml-6">
                  Scans a radius around the selected location for all viable sites. Best for exploring a new market area.
                </p>
              </button>
              <button
                onClick={() => setScope('targeted')}
                className={`flex-1 p-4 rounded-lg border-2 text-left transition-all ${
                  scope === 'targeted'
                    ? 'border-red-500 bg-red-50'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Crosshair className={`w-4 h-4 ${scope === 'targeted' ? 'text-red-600' : 'text-gray-400'}`} />
                  <span className={`font-medium text-sm ${scope === 'targeted' ? 'text-red-700' : 'text-gray-900'}`}>
                    Targeted Analysis
                  </span>
                </div>
                <p className="text-xs text-gray-500 ml-6">
                  Analyzes one specific address or property. Best when you already have a site in mind.
                </p>
              </button>
            </div>
          </div>

          {/* Radius selector (only for Area Scan) */}
          {scope === 'area' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Scan Radius</label>
              <div className="flex gap-2">
                {RADIUS_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setRadius(opt.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      radius === opt.value
                        ? 'bg-red-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Config summary */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-gray-600">
                <p className="font-medium text-gray-700 mb-1">Analysis Configuration</p>
                <ul className="space-y-0.5 text-xs">
                  <li>Config: <span className="font-mono">csoki</span> (Verizon criteria)</li>
                  <li>Agents: Feasibility, Regulatory, Sentiment, Growth, Planning, Verification</li>
                  <li>
                    Est. time: {scope === 'area'
                      ? `~${radius <= 10 ? '2-4' : radius <= 25 ? '4-8' : '8-12'} hours for ${radius}mi area scan`
                      : '~30 minutes for targeted analysis'
                    }
                  </li>
                  <li>Concurrent agents: 4</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Deploy button */}
          <button
            onClick={handleDeploy}
            disabled={!selected || isDeploying}
            className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg text-sm font-medium transition-all ${
              selected && !isDeploying
                ? 'bg-red-600 text-white hover:bg-red-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            <Rocket className="w-4 h-4" />
            {isDeploying ? 'Deploying...' : 'Launch Analysis'}
          </button>
        </div>
      </div>
    </div>
  );
}
