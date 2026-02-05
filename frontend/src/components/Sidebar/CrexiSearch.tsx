import { useState, useEffect } from 'react';
import { Search, AlertCircle, CheckCircle, Loader2, RefreshCw } from 'lucide-react';
import { listingsApi } from '../../services/api';

interface CrexiSearchProps {
  isVisible: boolean;
}

interface DiagnosticsStatus {
  playwrightAvailable: boolean;
  crexiLoaded: boolean;
  credentialsSet: boolean;
  error: string | null;
}

export function CrexiSearch({ isVisible }: CrexiSearchProps) {
  const [location, setLocation] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    total_filtered: number;
    empty_land_count: number;
    small_building_count: number;
    cached: boolean;
    message: string | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsStatus | null>(null);
  const [isLoadingDiagnostics, setIsLoadingDiagnostics] = useState(false);

  // Load diagnostics on mount
  useEffect(() => {
    if (isVisible && !diagnostics) {
      loadDiagnostics();
    }
  }, [isVisible]);

  const loadDiagnostics = async () => {
    setIsLoadingDiagnostics(true);
    try {
      const data = await listingsApi.getDiagnostics();
      setDiagnostics({
        playwrightAvailable: data.playwright.available,
        crexiLoaded: data.crexi.automation_loaded,
        credentialsSet: data.crexi.credentials.username_set && data.crexi.credentials.password_set,
        error: data.crexi.error || data.playwright.error || null,
      });
    } catch (err) {
      setDiagnostics({
        playwrightAvailable: false,
        crexiLoaded: false,
        credentialsSet: false,
        error: 'Failed to load diagnostics',
      });
    } finally {
      setIsLoadingDiagnostics(false);
    }
  };

  const handleSearch = async () => {
    if (!location.trim()) return;

    setIsSearching(true);
    setError(null);
    setResult(null);

    try {
      const response = await listingsApi.fetchCrexiArea({
        location: location.trim(),
        force_refresh: false,
      });
      setResult(response);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Search failed';
      setError(errorMessage);
    } finally {
      setIsSearching(false);
    }
  };

  const handleForceRefresh = async () => {
    if (!location.trim()) return;

    setIsSearching(true);
    setError(null);
    setResult(null);

    try {
      const response = await listingsApi.fetchCrexiArea({
        location: location.trim(),
        force_refresh: true,
      });
      setResult(response);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Search failed';
      setError(errorMessage);
    } finally {
      setIsSearching(false);
    }
  };

  if (!isVisible) return null;

  const isReady = diagnostics?.playwrightAvailable && diagnostics?.crexiLoaded && diagnostics?.credentialsSet;

  return (
    <div className="p-4 border-b border-gray-200 bg-blue-50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-blue-900 text-sm">Search Crexi Listings</h3>
        <button
          onClick={loadDiagnostics}
          disabled={isLoadingDiagnostics}
          className="text-blue-600 hover:text-blue-800 p-1"
          title="Refresh status"
        >
          <RefreshCw className={`w-4 h-4 ${isLoadingDiagnostics ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Status indicator */}
      {diagnostics && (
        <div className={`flex items-center gap-2 mb-3 text-xs ${isReady ? 'text-green-700' : 'text-amber-700'}`}>
          {isReady ? (
            <>
              <CheckCircle className="w-4 h-4" />
              <span>Crexi automation ready</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-4 h-4" />
              <span>
                {!diagnostics.playwrightAvailable && 'Playwright not installed'}
                {diagnostics.playwrightAvailable && !diagnostics.credentialsSet && 'Crexi credentials not set'}
                {diagnostics.playwrightAvailable && diagnostics.credentialsSet && !diagnostics.crexiLoaded && 'Crexi module error'}
              </span>
            </>
          )}
        </div>
      )}

      {/* Search input */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          placeholder="Des Moines, IA"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          disabled={!isReady || isSearching}
          className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
        />
        <button
          onClick={handleSearch}
          disabled={!isReady || isSearching || !location.trim()}
          className="px-3 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-1"
        >
          {isSearching ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Search className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-2 bg-red-100 border border-red-200 rounded text-xs text-red-700 mb-3">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="p-2 bg-white border border-blue-200 rounded">
          <div className="text-xs text-gray-700 space-y-1">
            <div className="flex justify-between">
              <span className="font-medium">Total Opportunities:</span>
              <span>{result.total_filtered}</span>
            </div>
            <div className="flex justify-between text-green-700">
              <span>Empty Land (0.8-2ac):</span>
              <span>{result.empty_land_count}</span>
            </div>
            <div className="flex justify-between text-purple-700">
              <span>Small Buildings:</span>
              <span>{result.small_building_count}</span>
            </div>
            {result.cached && (
              <div className="text-gray-500 text-xs pt-1 border-t">
                Using cached data
                <button
                  onClick={handleForceRefresh}
                  disabled={isSearching}
                  className="ml-2 text-blue-600 hover:underline"
                >
                  Refresh
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Help text when not ready */}
      {diagnostics && !isReady && (
        <div className="text-xs text-gray-500 mt-2">
          {!diagnostics.playwrightAvailable && (
            <p>Playwright browser automation is not available on this server.</p>
          )}
          {diagnostics.playwrightAvailable && !diagnostics.credentialsSet && (
            <p>Set CREXI_USERNAME and CREXI_PASSWORD environment variables in Railway.</p>
          )}
        </div>
      )}
    </div>
  );
}
