/**
 * PropertyInfoCard - Displays detailed property information when a marker is clicked.
 *
 * Shows:
 * - Basic property details (address, price, size, type)
 * - Ownership information
 * - Opportunity signals (for predictive properties)
 * - Quick actions (view parcel, external links)
 * - Contextual data (nearby competitors, demographics)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { X, ExternalLink, MapPin, Building2, Calendar, User, TrendingUp, AlertTriangle, Eye, Loader2, GripHorizontal, Navigation } from 'lucide-react';
import type { PropertyListing, ParcelInfo } from '../../types/store';
import { analysisApi } from '../../services/api';
import { PROPERTY_TYPE_COLORS, PROPERTY_TYPE_LABELS } from '../../types/store';

interface PropertyInfoCardProps {
  property: PropertyListing;
  onClose: () => void;
  initialPosition?: { x: number; y: number };
  onPositionChange?: (position: { x: number; y: number }) => void;
  opportunityRank?: number;
  opportunitySignals?: string[];
}

const SIGNAL_STRENGTH_COLORS = {
  high: 'bg-red-100 text-red-800 border-red-200',
  medium: 'bg-amber-100 text-amber-800 border-amber-200',
  low: 'bg-blue-100 text-blue-800 border-blue-200',
};

const SOURCE_LABELS: Record<string, string> = {
  attom: 'ATTOM Property Data',
  reportall: 'ReportAll',
  quantumlisting: 'QuantumListing',
  team_contributed: 'Team Contributed',
};

export function PropertyInfoCard({ property, onClose, initialPosition, onPositionChange, opportunityRank, opportunitySignals }: PropertyInfoCardProps) {
  const [parcelInfo, setParcelInfo] = useState<ParcelInfo | null>(null);
  const [isLoadingParcel, setIsLoadingParcel] = useState(false);
  const [parcelError, setParcelError] = useState<string | null>(null);
  const [showParcelDetails, setShowParcelDetails] = useState(false);

  // Draggable state - start at a safe default, will be adjusted on mount
  const [position, setPosition] = useState(initialPosition || { x: 20, y: 80 });
  const [isDragging, setIsDragging] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const panelRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const isOpportunity = property.listing_type === 'opportunity';

  // Calculate initial position based on container size on mount
  useEffect(() => {
    if (!initialPosition && containerRef.current && panelRef.current) {
      const containerRect = containerRef.current.getBoundingClientRect();
      const panelWidth = panelRef.current.offsetWidth || 384;
      // Position card at right side of container with some padding
      const initialX = Math.max(20, containerRect.width - panelWidth - 20);
      setPosition({ x: initialX, y: 80 });
    }
  }, [initialPosition]);

  // Drag handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (panelRef.current) {
      const rect = panelRef.current.getBoundingClientRect();
      dragOffset.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
      setIsDragging(true);
      e.preventDefault();
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging && panelRef.current && containerRef.current) {
      const containerRect = containerRef.current.getBoundingClientRect();
      const newX = e.clientX - containerRect.left - dragOffset.current.x;
      const newY = e.clientY - containerRect.top - dragOffset.current.y;

      // Keep panel within container bounds
      const maxX = containerRect.width - (panelRef.current.offsetWidth || 384);
      const maxY = containerRect.height - 100; // Leave some room at bottom

      const boundedPosition = {
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY)),
      };

      setPosition(boundedPosition);
      onPositionChange?.(boundedPosition);
    }
  }, [isDragging, onPositionChange]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Fetch parcel details from ReportAll
  const handleGetParcelDetails = async () => {
    if (parcelInfo) {
      setShowParcelDetails(true);
      return;
    }

    setIsLoadingParcel(true);
    setParcelError(null);

    try {
      const result = await analysisApi.getParcelInfo({
        latitude: property.latitude,
        longitude: property.longitude,
      });
      setParcelInfo(result);
      setShowParcelDetails(true);
    } catch (error: any) {
      setParcelError(error.response?.data?.detail || 'Failed to fetch parcel info');
    } finally {
      setIsLoadingParcel(false);
    }
  };

  // Format currency
  const formatCurrency = (value: number | null | undefined) => {
    if (!value) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Format date
  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const propertyTypeColor = PROPERTY_TYPE_COLORS[property.property_type] || '#6B7280';

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div
        ref={panelRef}
        className="bg-white rounded-lg shadow-xl border border-gray-200 w-96 max-h-[80vh] overflow-hidden flex flex-col pointer-events-auto"
        style={{
          position: 'absolute',
          left: position.x,
          top: position.y,
          zIndex: 3000,
        }}
      >
      {/* Header - Draggable */}
      <div
        className="px-4 py-3 border-b flex items-center justify-between cursor-move select-none"
        style={{ backgroundColor: `${propertyTypeColor}10` }}
        onMouseDown={handleMouseDown}
      >
        <div className="flex items-center gap-2">
          <GripHorizontal className="w-4 h-4 text-gray-400 flex-shrink-0" />
          {isOpportunity ? (
            <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-purple-600" />
            </div>
          ) : (
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center"
              style={{ backgroundColor: propertyTypeColor }}
            >
              <Building2 className="w-4 h-4 text-white" />
            </div>
          )}
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              {isOpportunity ? 'Opportunity' : 'Active Listing'}
            </div>
            <div className="text-sm font-semibold" style={{ color: propertyTypeColor }}>
              {PROPERTY_TYPE_LABELS[property.property_type] || 'Property'}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          onMouseDown={(e) => e.stopPropagation()} // Prevent drag when clicking close
          className="p-1 hover:bg-gray-200 rounded transition-colors"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Content - Scrollable */}
      <div className="flex-1 overflow-y-auto">
        {/* Address */}
        <div className="px-4 py-3 border-b">
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <div className="font-medium text-gray-900">{property.address}</div>
              <div className="text-sm text-gray-600">
                {property.city}, {property.state} {property.zip_code}
              </div>
              {/* CSOKi Opportunity Badge */}
              {opportunityRank && (
                <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-1 bg-purple-100 text-purple-800 rounded-full text-xs font-semibold">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2 L22 12 L12 22 L2 12 Z" />
                  </svg>
                  Priority #{opportunityRank}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="px-4 py-3 border-b grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Est. Value</div>
            <div className="text-lg font-bold text-gray-900">
              {property.price_display || formatCurrency(property.price || property.market_value)}
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Size</div>
            <div className="text-lg font-bold text-gray-900">
              {property.sqft ? `${property.sqft.toLocaleString()} SF` : 'N/A'}
            </div>
          </div>
          {property.lot_size_acres && (
            <div className="bg-gray-50 rounded-lg p-2">
              <div className="text-xs text-gray-500 uppercase tracking-wide">Lot Size</div>
              <div className="text-lg font-bold text-gray-900">
                {property.lot_size_acres.toFixed(2)} acres
              </div>
            </div>
          )}
          {property.year_built && (
            <div className="bg-gray-50 rounded-lg p-2">
              <div className="text-xs text-gray-500 uppercase tracking-wide">Year Built</div>
              <div className="text-lg font-bold text-gray-900">{property.year_built}</div>
            </div>
          )}
        </div>

        {/* Opportunity Signals (if any) */}
        {((isOpportunity && property.opportunity_signals && property.opportunity_signals.length > 0) || (opportunitySignals && opportunitySignals.length > 0)) && (
          <div className="px-4 py-3 border-b">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-semibold text-purple-900">
                Why This Opportunity?
              </span>
              {property.opportunity_score && (
                <span className="ml-auto text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full font-medium">
                  Score: {property.opportunity_score.toFixed(0)}
                </span>
              )}
            </div>
            <div className="space-y-1.5">
              {/* Show priority signals if passed directly (CSOKi Opportunities) */}
              {opportunitySignals && opportunitySignals.length > 0 ? (
                opportunitySignals.map((signal, index) => (
                  <div
                    key={index}
                    className="text-xs px-2 py-1.5 rounded border bg-amber-100 text-amber-800 border-amber-200"
                  >
                    <span className="font-medium">{signal}</span>
                  </div>
                ))
              ) : (
                /* Otherwise show property signals */
                property.opportunity_signals?.map((signal, index) => (
                  <div
                    key={index}
                    className={`text-xs px-2 py-1.5 rounded border ${SIGNAL_STRENGTH_COLORS[signal.strength]}`}
                  >
                    <span className="font-medium">{signal.description}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Ownership Info */}
        {(property.owner_name || property.owner_type) && (
          <div className="px-4 py-3 border-b">
            <div className="flex items-center gap-2 mb-2">
              <User className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-semibold text-gray-700">Ownership</span>
            </div>
            <div className="text-sm text-gray-600">
              {property.owner_name && <div>{property.owner_name}</div>}
              {property.owner_type && (
                <div className="text-xs text-gray-500 capitalize">{property.owner_type}</div>
              )}
            </div>
          </div>
        )}

        {/* Transaction History */}
        {(property.last_sale_date || property.last_sale_price) && (
          <div className="px-4 py-3 border-b">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-semibold text-gray-700">Last Sale</span>
            </div>
            <div className="text-sm text-gray-600 grid grid-cols-2 gap-2">
              <div>
                <div className="text-xs text-gray-500">Date</div>
                <div>{formatDate(property.last_sale_date)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Price</div>
                <div>{formatCurrency(property.last_sale_price)}</div>
              </div>
            </div>
          </div>
        )}

        {/* Parcel Details (expandable) */}
        {showParcelDetails && parcelInfo && (
          <div className="px-4 py-3 border-b bg-blue-50">
            <div className="text-sm font-semibold text-blue-900 mb-2">
              Parcel Details (ReportAll)
            </div>
            <div className="text-xs text-gray-600 space-y-1">
              {parcelInfo.parcel_id && (
                <div>
                  <span className="text-gray-500">Parcel ID:</span> {parcelInfo.parcel_id}
                </div>
              )}
              {parcelInfo.zoning && (
                <div>
                  <span className="text-gray-500">Zoning:</span> {parcelInfo.zoning}
                </div>
              )}
              {parcelInfo.land_use && (
                <div>
                  <span className="text-gray-500">Land Use:</span> {parcelInfo.land_use}
                </div>
              )}
              {parcelInfo.total_value && (
                <div>
                  <span className="text-gray-500">Assessed Value:</span>{' '}
                  {formatCurrency(parcelInfo.total_value)}
                </div>
              )}
              {parcelInfo.acreage && (
                <div>
                  <span className="text-gray-500">Acreage:</span> {parcelInfo.acreage.toFixed(2)}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Source */}
        <div className="px-4 py-2 bg-gray-50 text-xs text-gray-500">
          Source: {SOURCE_LABELS[property.source] || property.source}
        </div>
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t bg-gray-50 space-y-2">
        <div className="flex gap-2">
          <button
            onClick={handleGetParcelDetails}
            disabled={isLoadingParcel}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {isLoadingParcel ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Eye className="w-4 h-4" />
            )}
            {showParcelDetails ? 'Refresh Parcel' : 'Get Parcel Details'}
          </button>
          {property.external_url && (
            <a
              href={property.external_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1.5 px-3 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              View Listing
            </a>
          )}
        </div>
        {/* Street View Button */}
        <a
          href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${property.latitude},${property.longitude}`}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-green-500 text-green-700 text-sm font-medium rounded-lg hover:bg-green-50 transition-colors"
        >
          <Navigation className="w-4 h-4" />
          View on Street View
        </a>
      </div>

      {/* Error Display */}
      {parcelError && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-200 text-xs text-red-700">
          {parcelError}
        </div>
      )}
      </div>
    </div>
  );
}

export default PropertyInfoCard;
