import { useState, useRef, useCallback } from 'react';
import { X, GripHorizontal } from 'lucide-react';
import type { ParcelInfo } from '../../types/store';

interface DraggableParcelInfoProps {
  parcel: ParcelInfo | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

export function DraggableParcelInfo({
  parcel,
  isLoading,
  error,
  onClose,
}: DraggableParcelInfoProps) {
  const [position, setPosition] = useState({ x: 20, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const panelRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (panelRef.current) {
      const rect = panelRef.current.getBoundingClientRect();
      dragOffset.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
      setIsDragging(true);
    }
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging) {
        const parentRect = panelRef.current?.parentElement?.getBoundingClientRect();
        if (parentRect) {
          const newX = e.clientX - parentRect.left - dragOffset.current.x;
          const newY = e.clientY - parentRect.top - dragOffset.current.y;
          // Keep panel within bounds
          const maxX = parentRect.width - (panelRef.current?.offsetWidth || 300);
          const maxY = parentRect.height - (panelRef.current?.offsetHeight || 400);
          setPosition({
            x: Math.max(0, Math.min(newX, maxX)),
            y: Math.max(0, Math.min(newY, maxY)),
          });
        }
      }
    },
    [isDragging]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  if (!parcel && !isLoading && !error) return null;

  return (
    <div
      className="absolute inset-0 pointer-events-none"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div
        ref={panelRef}
        className="absolute bg-white rounded-lg shadow-xl border border-gray-200 pointer-events-auto"
        style={{
          left: position.x,
          top: position.y,
          width: 320,
          maxHeight: 'calc(100% - 40px)',
          zIndex: 1000,
        }}
      >
        {/* Draggable header */}
        <div
          className="flex items-center justify-between px-3 py-2 bg-amber-700 text-white rounded-t-lg cursor-move select-none"
          onMouseDown={handleMouseDown}
        >
          <div className="flex items-center gap-2">
            <GripHorizontal className="w-4 h-4 opacity-70" />
            <span className="text-sm font-semibold">Parcel Information</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-amber-800 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
          {isLoading ? (
            <div className="text-center py-6 text-gray-500">
              <div className="animate-spin inline-block w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full mb-2"></div>
              <p className="text-sm">Loading parcel data...</p>
            </div>
          ) : error ? (
            <div className="text-center py-4 text-red-600 text-sm">
              {error}
            </div>
          ) : parcel ? (
            <div className="text-sm space-y-3">
              {/* Parcel ID */}
              {parcel.parcel_id && (
                <div>
                  <span className="text-gray-500 text-xs font-medium">Parcel ID</span>
                  <p className="font-semibold text-gray-900">{parcel.parcel_id}</p>
                </div>
              )}

              {/* Address */}
              {parcel.address && (
                <div>
                  <span className="text-gray-500 text-xs font-medium">Address</span>
                  <p className="font-semibold text-gray-900">{parcel.address}</p>
                  {(parcel.city || parcel.state) && (
                    <p className="text-gray-600 text-xs">
                      {[parcel.city, parcel.state, parcel.zip_code]
                        .filter(Boolean)
                        .join(', ')}
                    </p>
                  )}
                </div>
              )}

              {/* Owner */}
              {parcel.owner && (
                <div>
                  <span className="text-gray-500 text-xs font-medium">Property Owner</span>
                  <p className="font-semibold text-gray-900">{parcel.owner}</p>
                </div>
              )}

              {/* Key metrics grid */}
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-200">
                {parcel.acreage != null && (
                  <div>
                    <span className="text-gray-500 text-xs font-medium">Acreage</span>
                    <p className="font-semibold text-gray-900">{parcel.acreage.toFixed(2)} ac</p>
                  </div>
                )}
                {parcel.building_sqft != null && (
                  <div>
                    <span className="text-gray-500 text-xs font-medium">Building Sq Ft</span>
                    <p className="font-semibold text-gray-900">{parcel.building_sqft.toLocaleString()}</p>
                  </div>
                )}
                {parcel.zoning && (
                  <div>
                    <span className="text-gray-500 text-xs font-medium">Zoning</span>
                    <p className="font-semibold text-gray-900">{parcel.zoning}</p>
                  </div>
                )}
                {parcel.land_use && (
                  <div>
                    <span className="text-gray-500 text-xs font-medium">Land Use</span>
                    <p className="font-semibold text-gray-900">{parcel.land_use}</p>
                  </div>
                )}
                {parcel.year_built != null && (
                  <div>
                    <span className="text-gray-500 text-xs font-medium">Year Built</span>
                    <p className="font-semibold text-gray-900">{parcel.year_built}</p>
                  </div>
                )}
              </div>

              {/* Values section */}
              {(parcel.land_value != null || parcel.building_value != null || parcel.total_value != null) && (
                <div className="pt-2 border-t border-gray-200">
                  <span className="text-gray-500 text-xs font-medium block mb-2">Assessed Values</span>
                  <div className="grid grid-cols-2 gap-2">
                    {parcel.land_value != null && (
                      <div>
                        <span className="text-gray-400 text-xs">Land</span>
                        <p className="font-medium text-gray-800">${parcel.land_value.toLocaleString()}</p>
                      </div>
                    )}
                    {parcel.building_value != null && (
                      <div>
                        <span className="text-gray-400 text-xs">Building</span>
                        <p className="font-medium text-gray-800">${parcel.building_value.toLocaleString()}</p>
                      </div>
                    )}
                    {parcel.total_value != null && (
                      <div className="col-span-2">
                        <span className="text-gray-400 text-xs">Total Value</span>
                        <p className="font-semibold text-green-700 text-lg">${parcel.total_value.toLocaleString()}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Sale history */}
              {(parcel.sale_price != null || parcel.sale_date) && (
                <div className="pt-2 border-t border-gray-200">
                  <span className="text-gray-500 text-xs font-medium">Last Sale</span>
                  <p className="font-semibold text-gray-900">
                    {parcel.sale_price != null && `$${parcel.sale_price.toLocaleString()}`}
                    {parcel.sale_price != null && parcel.sale_date && ' on '}
                    {parcel.sale_date}
                  </p>
                </div>
              )}

              {/* Raw data debug (collapsible) */}
              {parcel.raw_data && (
                <details className="pt-2 border-t border-gray-200">
                  <summary className="text-gray-400 text-xs cursor-pointer hover:text-gray-600">
                    Raw API Fields ({Object.keys(parcel.raw_data).length} fields)
                  </summary>
                  <div className="text-xs text-gray-600 mt-2 max-h-40 overflow-y-auto bg-gray-50 p-2 rounded">
                    {Object.entries(parcel.raw_data)
                      .filter(([, v]) => v !== null && v !== '')
                      .map(([key, value]) => (
                        <div key={key} className="truncate py-0.5">
                          <span className="font-medium text-gray-700">{key}:</span>{' '}
                          {String(value).substring(0, 50)}
                        </div>
                      ))}
                  </div>
                </details>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
