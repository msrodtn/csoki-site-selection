import { useMapStore } from '../../store/useMapStore';
import { MapPin } from 'lucide-react';

// Target market states
const TARGET_STATES = [
  { code: 'IA', name: 'Iowa', lat: 42.0, lng: -93.5 },
  { code: 'NE', name: 'Nebraska', lat: 41.5, lng: -99.8 },
  { code: 'NV', name: 'Nevada', lat: 39.5, lng: -116.9 },
  { code: 'ID', name: 'Idaho', lat: 44.1, lng: -114.7 },
];

export function StateFilter() {
  const { selectedState, setSelectedState, setViewport } = useMapStore();

  const handleStateClick = (state: typeof TARGET_STATES[0] | null) => {
    if (state) {
      setSelectedState(state.code);
      setViewport({
        latitude: state.lat,
        longitude: state.lng,
        zoom: 7,
      });
    } else {
      setSelectedState(null);
      // Reset to full US view
      setViewport({
        latitude: 39.5,
        longitude: -98.35,
        zoom: 4,
      });
    }
  };

  return (
    <div className="p-4 border-t border-gray-200">
      <h3 className="font-semibold text-gray-800 mb-3">Target Markets</h3>

      <div className="space-y-2">
        {/* All states option */}
        <button
          onClick={() => handleStateClick(null)}
          className={`
            w-full flex items-center gap-2 p-2 rounded-lg text-left
            transition-all duration-150
            ${!selectedState
              ? 'bg-blue-50 border border-blue-200 text-blue-700'
              : 'bg-gray-50 hover:bg-gray-100 text-gray-700'}
          `}
        >
          <MapPin className="w-4 h-4" />
          <span className="text-sm font-medium">All States</span>
        </button>

        {/* Target states */}
        {TARGET_STATES.map((state) => (
          <button
            key={state.code}
            onClick={() => handleStateClick(state)}
            className={`
              w-full flex items-center gap-2 p-2 rounded-lg text-left
              transition-all duration-150
              ${selectedState === state.code
                ? 'bg-blue-50 border border-blue-200 text-blue-700'
                : 'bg-gray-50 hover:bg-gray-100 text-gray-700'}
            `}
          >
            <span className="text-xs font-bold w-6">{state.code}</span>
            <span className="text-sm">{state.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
