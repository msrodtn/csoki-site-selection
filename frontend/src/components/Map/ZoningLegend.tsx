interface ZoningLegendProps {
  isVisible: boolean;
}

// Zoning category colors - used for parcel boundary highlighting
export const ZONING_COLORS: Record<string, { color: string; fill: string; label: string }> = {
  // Commercial
  commercial: { color: '#DC2626', fill: '#FEE2E2', label: 'Commercial' },
  // Residential
  residential: { color: '#2563EB', fill: '#DBEAFE', label: 'Residential' },
  // Industrial
  industrial: { color: '#7C3AED', fill: '#EDE9FE', label: 'Industrial' },
  // Mixed Use
  mixed: { color: '#D97706', fill: '#FEF3C7', label: 'Mixed Use' },
  // Agricultural
  agricultural: { color: '#059669', fill: '#D1FAE5', label: 'Agricultural' },
  // Public/Institutional
  public: { color: '#0891B2', fill: '#CFFAFE', label: 'Public/Institutional' },
  // Unknown/Other
  unknown: { color: '#6B7280', fill: '#F3F4F6', label: 'Unknown' },
};

// Map zoning codes to categories
export function getZoningCategory(zoning: string | null | undefined, landUse: string | null | undefined): string {
  const code = (zoning || landUse || '').toUpperCase();

  // Commercial patterns
  if (/^C\d?|COMM|COMMERCIAL|RETAIL|BUSINESS|^B\d?|CBD|^GC|^NC|^CC|SHOP|STORE/.test(code)) {
    return 'commercial';
  }

  // Residential patterns
  if (/^R\d?|RESID|RESIDENTIAL|SINGLE|MULTI|FAMILY|DUPLEX|^SF|^MF|DWELLING|HOME|HOUSE|^DR|^RM|^RS/.test(code)) {
    return 'residential';
  }

  // Industrial patterns
  if (/^I\d?|^M\d?|INDUST|INDUSTRIAL|MANUFACT|WAREHOUSE|LIGHT|HEAVY|^LI|^HI/.test(code)) {
    return 'industrial';
  }

  // Mixed Use patterns
  if (/MIXED|MIX|MU\d?|^PUD|PLANNED|URBAN/.test(code)) {
    return 'mixed';
  }

  // Agricultural patterns
  if (/^A\d?|AGRI|AGRICULT|FARM|RURAL|^AG|CONSERV/.test(code)) {
    return 'agricultural';
  }

  // Public/Institutional patterns
  if (/PUBLIC|INSTIT|GOVT|GOVERNMENT|SCHOOL|CHURCH|HOSPITAL|PARK|^P\d?|CIVIC|MUNICIPAL/.test(code)) {
    return 'public';
  }

  return 'unknown';
}

export function ZoningLegend({ isVisible }: ZoningLegendProps) {
  if (!isVisible) return null;

  const categories = Object.entries(ZONING_COLORS);

  return (
    <div className="absolute bottom-20 right-4 z-10 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 text-xs">
      <div className="font-semibold text-gray-800 mb-2 flex items-center gap-1.5">
        <div className="w-3 h-3 rounded-sm bg-gradient-to-r from-red-500 via-blue-500 to-green-500" />
        Zoning Colors
      </div>
      <div className="space-y-1.5">
        {categories.map(([key, { color, label }]) => (
          <div key={key} className="flex items-center gap-2">
            <div
              className="w-4 h-3 rounded-sm border"
              style={{ backgroundColor: color, borderColor: color }}
            />
            <span className="text-gray-600">{label}</span>
          </div>
        ))}
      </div>
      <p className="text-gray-400 mt-2 text-[10px] border-t pt-2">
        Click a parcel to see zoning details
      </p>
    </div>
  );
}
