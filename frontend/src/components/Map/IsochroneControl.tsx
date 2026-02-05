/**
 * Isochrone Control - Drive Time Areas
 *
 * Shows areas reachable within X minutes by car/walk/bike from a selected point.
 * Uses Mapbox Isochrone API to calculate travel time polygons.
 */

import { useState } from 'react';
import { Clock, Car, Bike, Footprints, X, Loader2, AlertCircle, Users } from 'lucide-react';

export type TravelMode = 'driving' | 'walking' | 'cycling';

export interface IsochroneSettings {
  enabled: boolean;
  minutes: number;
  mode: TravelMode;
  coordinates: [number, number] | null;
}

interface IsochroneControlProps {
  settings: IsochroneSettings;
  onSettingsChange: (settings: IsochroneSettings) => void;
  isLoading?: boolean;
  error?: string | null;
  onClearError?: () => void;
  onShowCompetitorAccess?: () => void;
}

const TIME_OPTIONS = [5, 10, 15, 20, 30];

export default function IsochroneControl({
  settings,
  onSettingsChange,
  isLoading = false,
  error = null,
  onClearError,
  onShowCompetitorAccess,
}: IsochroneControlProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const setMinutes = (minutes: number) => {
    onSettingsChange({
      ...settings,
      minutes,
      enabled: true, // Auto-enable when selecting time
    });
  };

  const setMode = (mode: TravelMode) => {
    onSettingsChange({
      ...settings,
      mode,
      enabled: true, // Auto-enable when selecting mode
    });
  };

  const clearIsochrone = () => {
    onSettingsChange({
      ...settings,
      enabled: false,
      coordinates: null,
    });
  };

  const getModeIcon = (mode: TravelMode) => {
    switch (mode) {
      case 'driving':
        return <Car className="w-4 h-4" />;
      case 'walking':
        return <Footprints className="w-4 h-4" />;
      case 'cycling':
        return <Bike className="w-4 h-4" />;
    }
  };

  const getModeLabel = (mode: TravelMode) => {
    switch (mode) {
      case 'driving':
        return 'Driving';
      case 'walking':
        return 'Walking';
      case 'cycling':
        return 'Cycling';
    }
  };

  return (
    <div className="absolute top-20 left-4 z-10">
      {/* Toggle Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`
          bg-white rounded-lg shadow-lg px-4 py-2 flex items-center gap-2 transition-colors
          ${settings.enabled ? 'bg-blue-50 border-2 border-blue-500' : 'hover:bg-gray-50'}
          ${error ? 'border-2 border-red-400' : ''}
        `}
        title="Drive time areas"
      >
        {isLoading ? (
          <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
        ) : error ? (
          <AlertCircle className="w-5 h-5 text-red-500" />
        ) : (
          <Clock className={`w-5 h-5 ${settings.enabled ? 'text-blue-600' : 'text-gray-700'}`} />
        )}
        <span className={`font-medium ${error ? 'text-red-600' : settings.enabled ? 'text-blue-700' : 'text-gray-700'}`}>
          {isLoading
            ? 'Calculating...'
            : error
              ? 'Error'
              : settings.enabled
                ? `${settings.minutes} min ${getModeLabel(settings.mode)}`
                : 'Drive Time'}
        </span>
        {settings.enabled && !isLoading && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              clearIsochrone();
              onClearError?.();
            }}
            className="ml-1 p-0.5 hover:bg-blue-200 rounded transition-colors"
          >
            <X className="w-4 h-4 text-blue-600" />
          </button>
        )}
      </button>

      {/* Dropdown Panel */}
      {isExpanded && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-0"
            onClick={() => setIsExpanded(false)}
          />

          {/* Menu */}
          <div className="absolute top-12 left-0 bg-white rounded-lg shadow-xl border border-gray-200 w-64 overflow-hidden z-10">
            <div className="p-3 bg-gray-50 border-b border-gray-200">
              <h3 className="font-semibold text-gray-700 text-sm flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Travel Time Areas
              </h3>
              <p className="text-xs text-gray-500 mt-1">
                Click a store or property to show reachable area
              </p>
            </div>

            {/* Travel Mode Selection */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-xs font-medium text-gray-600 mb-2 uppercase tracking-wide">
                Travel Mode
              </div>
              <div className="grid grid-cols-3 gap-2">
                {(['driving', 'walking', 'cycling'] as TravelMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setMode(mode)}
                    className={`
                      flex flex-col items-center gap-1 px-2 py-2 rounded-lg transition-colors text-xs
                      ${
                        settings.mode === mode
                          ? 'bg-blue-100 text-blue-700 border-2 border-blue-500'
                          : 'bg-gray-50 text-gray-700 hover:bg-gray-100 border-2 border-transparent'
                      }
                    `}
                  >
                    {getModeIcon(mode)}
                    <span className="font-medium">{getModeLabel(mode)}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Time Selection */}
            <div className="p-3">
              <div className="text-xs font-medium text-gray-600 mb-2 uppercase tracking-wide">
                Travel Time
              </div>
              <div className="grid grid-cols-3 gap-2">
                {TIME_OPTIONS.map((minutes) => (
                  <button
                    key={minutes}
                    onClick={() => setMinutes(minutes)}
                    className={`
                      px-3 py-2 rounded-lg transition-colors text-sm font-medium
                      ${
                        settings.minutes === minutes
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }
                    `}
                  >
                    {minutes} min
                  </button>
                ))}
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="p-3 bg-red-50 border-t border-red-200">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-xs text-red-700">{error}</p>
                    <button
                      onClick={() => onClearError?.()}
                      className="text-xs text-red-600 underline hover:text-red-800 mt-1"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Quick Actions - when location is selected */}
            {settings.coordinates && onShowCompetitorAccess && (
              <div className="p-3 border-t border-gray-200">
                <div className="text-xs font-medium text-gray-600 mb-2 uppercase tracking-wide">
                  Quick Actions
                </div>
                <button
                  onClick={() => {
                    onShowCompetitorAccess();
                    setIsExpanded(false);
                  }}
                  disabled={isLoading}
                  className="w-full flex items-center gap-2 px-3 py-2 bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 rounded-lg transition-colors text-sm font-medium"
                >
                  <Users className="w-4 h-4" />
                  View Competitor Travel Times
                </button>
              </div>
            )}

            {/* Instructions */}
            {!error && (
              <div className="p-3 bg-blue-50 border-t border-blue-200">
                <p className="text-xs text-blue-800">
                  {settings.coordinates
                    ? '✓ Location selected. Change time/mode above, or click another location.'
                    : '💡 Click any store or property pin on the map to show the travel time area.'}
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
