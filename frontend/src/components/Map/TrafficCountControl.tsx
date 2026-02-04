/**
 * Traffic Count Control - State Traffic Data Overlay
 * 
 * Displays annual average daily traffic (AADT) counts from state DOT data.
 * Fetches available states dynamically from backend.
 */

import { useState } from 'react';
import { BarChart3, ChevronDown, X } from 'lucide-react';

export interface TrafficCountSettings {
  enabled: boolean;
  selectedState: string | null;
}

interface TrafficCountControlProps {
  settings: TrafficCountSettings;
  onSettingsChange: (settings: TrafficCountSettings) => void;
}

interface AvailableState {
  code: string;
  name: string;
}

// Hardcoded states for now - will convert to Mapbox tilesets later
const AVAILABLE_STATES: AvailableState[] = [
  { code: 'IA', name: 'Iowa' },
  // Future: NE, NV, KS, etc. - will upload as Mapbox tilesets
];

export default function TrafficCountControl({ settings, onSettingsChange }: TrafficCountControlProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const selectState = (stateCode: string) => {
    onSettingsChange({
      enabled: true,
      selectedState: stateCode,
    });
    setIsExpanded(false);
  };

  const clearTraffic = () => {
    onSettingsChange({
      enabled: false,
      selectedState: null,
    });
  };

  const getSelectedStateName = () => {
    if (!settings.selectedState) return null;
    const state = AVAILABLE_STATES.find(s => s.code === settings.selectedState);
    return state?.name || settings.selectedState;
  };

  return (
    <div className="absolute top-36 left-4 z-10">
      {/* Toggle Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`
          bg-white rounded-lg shadow-lg px-4 py-2 flex items-center gap-2 transition-colors
          ${settings.enabled ? 'bg-orange-50 border-2 border-orange-500' : 'hover:bg-gray-50'}
        `}
        title="Traffic count overlay"
      >
        <BarChart3 className={`w-5 h-5 ${settings.enabled ? 'text-orange-600' : 'text-gray-700'}`} />
        <span className={`font-medium ${settings.enabled ? 'text-orange-700' : 'text-gray-700'}`}>
          {settings.enabled ? getSelectedStateName() : 'Traffic Count'}
        </span>
        {settings.enabled ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              clearTraffic();
            }}
            className="ml-1 p-0.5 hover:bg-orange-200 rounded transition-colors"
          >
            <X className="w-4 h-4 text-orange-600" />
          </button>
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-500" />
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
                <BarChart3 className="w-4 h-4" />
                Traffic Count Overlay
              </h3>
              <p className="text-xs text-gray-500 mt-1">
                Annual Average Daily Traffic (AADT) from state DOT data
              </p>
            </div>

            {/* State Selection */}
            <div className="p-3">
              <div className="text-xs font-medium text-gray-600 mb-2 uppercase tracking-wide">
                Select State
              </div>
              <div className="space-y-2">
                {AVAILABLE_STATES.map((state) => (
                  <button
                    key={state.code}
                    onClick={() => selectState(state.code)}
                    className={`
                      w-full text-left px-3 py-2 rounded-lg transition-colors text-sm font-medium
                      ${
                        settings.selectedState === state.code
                          ? 'bg-orange-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }
                    `}
                  >
                    {state.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Legend */}
            <div className="p-3 bg-gray-50 border-t border-gray-200">
              <div className="text-xs font-medium text-gray-700 mb-2">Traffic Volume</div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-1 bg-[#00C5FF] rounded"></div>
                  <span className="text-xs text-gray-600">0 - 999</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-1 bg-[#55FF00] rounded"></div>
                  <span className="text-xs text-gray-600">1,000 - 1,999</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-1 bg-[#FFAA00] rounded"></div>
                  <span className="text-xs text-gray-600">2,000 - 4,999</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-1 bg-[#FF0000] rounded"></div>
                  <span className="text-xs text-gray-600">5,000+</span>
                </div>
              </div>
            </div>

            {/* Info */}
            <div className="p-3 bg-orange-50 border-t border-orange-200">
              <p className="text-xs text-orange-800">
                💡 <strong>Tip:</strong> Traffic data updates monthly from state DOT sources. Click roads for detailed counts.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
