import { useState, useCallback, useMemo } from 'react';
import { useMapStore } from '../../store/useMapStore';
import { Eye, EyeOff, GripVertical, Navigation } from 'lucide-react';

// Target market states with coordinates
const STATE_DATA: Record<string, { name: string; lat: number; lng: number }> = {
  IA: { name: 'Iowa', lat: 42.0, lng: -93.5 },
  NE: { name: 'Nebraska', lat: 41.5, lng: -99.8 },
  NV: { name: 'Nevada', lat: 39.5, lng: -116.9 },
  ID: { name: 'Idaho', lat: 44.1, lng: -114.7 },
};

export function StateFilter() {
  const {
    visibleStates,
    toggleStateVisibility,
    setAllStatesVisible,
    stateOrder,
    setStateOrder,
    setViewport,
  } = useMapStore();

  const [draggedItem, setDraggedItem] = useState<string | null>(null);
  const [dragOverItem, setDragOverItem] = useState<string | null>(null);

  // Convert Set to Array for reliable checking
  const visibleStatesArray = useMemo(() => Array.from(visibleStates), [visibleStates]);

  const allVisible = visibleStatesArray.length === stateOrder.length;
  const noneVisible = visibleStatesArray.length === 0;

  // Navigate to state (zoom)
  const handleNavigateToState = useCallback(
    (stateCode: string) => {
      const state = STATE_DATA[stateCode];
      if (state) {
        setViewport({
          latitude: state.lat,
          longitude: state.lng,
          zoom: 7,
        });
      }
    },
    [setViewport]
  );

  // Drag and drop handlers
  const handleDragStart = (e: React.DragEvent, stateCode: string) => {
    setDraggedItem(stateCode);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', stateCode);
  };

  const handleDragOver = (e: React.DragEvent, stateCode: string) => {
    e.preventDefault();
    if (draggedItem && draggedItem !== stateCode) {
      setDragOverItem(stateCode);
    }
  };

  const handleDragLeave = () => {
    setDragOverItem(null);
  };

  const handleDrop = (e: React.DragEvent, targetStateCode: string) => {
    e.preventDefault();
    if (!draggedItem || draggedItem === targetStateCode) {
      setDraggedItem(null);
      setDragOverItem(null);
      return;
    }

    const newOrder = [...stateOrder];
    const draggedIndex = newOrder.indexOf(draggedItem);
    const targetIndex = newOrder.indexOf(targetStateCode);

    // Remove dragged item and insert at target position
    newOrder.splice(draggedIndex, 1);
    newOrder.splice(targetIndex, 0, draggedItem);

    setStateOrder(newOrder);
    setDraggedItem(null);
    setDragOverItem(null);
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
    setDragOverItem(null);
  };

  return (
    <div className="p-4 border-t border-gray-200">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800">Target Markets</h3>
        <button
          onClick={() => setAllStatesVisible(!allVisible)}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
        >
          {allVisible ? 'Hide All' : 'Show All'}
        </button>
      </div>

      <p className="text-xs text-gray-500 mb-3">
        Drag to reorder. Click eye to toggle. Click arrow to zoom.
      </p>

      <div className="space-y-1">
        {stateOrder.map((stateCode) => {
          const state = STATE_DATA[stateCode];
          if (!state) return null;

          const isVisible = visibleStatesArray.includes(stateCode);
          const isDragging = draggedItem === stateCode;
          const isDragOver = dragOverItem === stateCode;

          return (
            <div
              key={stateCode}
              draggable
              onDragStart={(e) => handleDragStart(e, stateCode)}
              onDragOver={(e) => handleDragOver(e, stateCode)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, stateCode)}
              onDragEnd={handleDragEnd}
              className={`
                flex items-center gap-2 p-2 rounded-lg
                transition-all duration-150 cursor-move
                ${isDragging ? 'opacity-50 bg-gray-200' : ''}
                ${isDragOver ? 'border-2 border-blue-400 bg-blue-50' : 'border-2 border-transparent'}
                ${isVisible ? 'bg-gray-50' : 'bg-gray-100 opacity-60'}
              `}
            >
              {/* Drag handle */}
              <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />

              {/* State code */}
              <span className="text-xs font-bold w-6 text-gray-600">{stateCode}</span>

              {/* State name */}
              <span className="text-sm flex-1 text-gray-700">{state.name}</span>

              {/* Navigate button */}
              <button
                onClick={() => handleNavigateToState(stateCode)}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
                title={`Zoom to ${state.name}`}
              >
                <Navigation className="w-4 h-4 text-blue-500" />
              </button>

              {/* Visibility toggle */}
              <button
                onClick={() => toggleStateVisibility(stateCode)}
                className={`p-1 rounded transition-colors ${
                  isVisible ? 'hover:bg-gray-200' : 'hover:bg-gray-300'
                }`}
                title={isVisible ? 'Hide stores' : 'Show stores'}
              >
                {isVisible ? (
                  <Eye className="w-4 h-4 text-green-600" />
                ) : (
                  <EyeOff className="w-4 h-4 text-gray-400" />
                )}
              </button>
            </div>
          );
        })}
      </div>

      {noneVisible && (
        <p className="text-xs text-amber-600 mt-2">
          No states selected. Enable at least one to see stores.
        </p>
      )}
    </div>
  );
}
