import { Marker, type MarkerEvent } from '@vis.gl/react-mapbox';
import type { OpportunityRanking } from '../../types/store';

const PULSE_THRESHOLD = 5;

function getZoomBasedSize(zoom: number, isSelected: boolean): number {
  let baseSize: number;
  if (zoom <= 6) {
    baseSize = 24;
  } else if (zoom <= 10) {
    baseSize = 24 + ((zoom - 6) / 4) * 8;
  } else if (zoom <= 14) {
    baseSize = 32 + ((zoom - 10) / 4) * 8;
  } else {
    baseSize = 40 + ((zoom - 14) / 4) * 8;
  }
  return isSelected ? Math.round(baseSize * 1.25) : Math.round(baseSize);
}

interface PulsingOpportunityMarkerProps {
  opportunity: OpportunityRanking;
  isSelected: boolean;
  zoom: number;
  onClick: (e: MarkerEvent<MouseEvent>) => void;
}

export function PulsingOpportunityMarker({
  opportunity,
  isSelected,
  zoom,
  onClick,
}: PulsingOpportunityMarkerProps) {
  const prop = opportunity.property;
  if (!prop.latitude || !prop.longitude) return null;

  const size = getZoomBasedSize(zoom, isSelected);
  const isPulsing = opportunity.rank <= PULSE_THRESHOLD;

  return (
    <Marker
      longitude={prop.longitude}
      latitude={prop.latitude}
      anchor="center"
      onClick={onClick}
      style={{ zIndex: isSelected ? 1500 : 300 }}
    >
      <div
        className="relative cursor-pointer transition-transform duration-150 flex items-center justify-center"
        style={{
          transform: isSelected ? 'scale(1.3)' : 'scale(1)',
          width: size,
          height: size,
        }}
      >
        {/* Pulsing ring for top-ranked opportunities */}
        {isPulsing && (
          <div
            className="absolute rounded-full pulse-ring"
            style={{
              width: size,
              height: size,
              backgroundColor: '#9333EA',
            }}
          />
        )}
        {/* Purple diamond with rank number */}
        <svg
          width={size}
          height={size}
          viewBox="0 0 24 24"
          className="relative"
        >
          <path
            d="M12 2 L22 12 L12 22 L2 12 Z"
            fill="#9333EA"
            stroke="white"
            strokeWidth="1.5"
            opacity={isSelected ? 1 : 0.85}
          />
          <text
            x="12"
            y="15"
            textAnchor="middle"
            fill="white"
            fontSize="10"
            fontWeight="bold"
          >
            {opportunity.rank}
          </text>
        </svg>
      </div>
    </Marker>
  );
}
