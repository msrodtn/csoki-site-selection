import { useState, useEffect } from 'react';
import { ExternalLink, X, Building2, MapPin, Search } from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { PropertySearchLinks, ExternalSearchLink } from '../../types/store';

interface PropertySearchPanelProps {
  latitude: number;
  longitude: number;
  onClose: () => void;
}

// Icon mapping for different sources
const SOURCE_ICONS: Record<string, { bg: string; text: string }> = {
  crexi: { bg: 'bg-blue-900', text: 'text-white' },
  loopnet: { bg: 'bg-red-600', text: 'text-white' },
  commercialcafe: { bg: 'bg-purple-600', text: 'text-white' },
  google: { bg: 'bg-white border border-gray-300', text: 'text-gray-700' },
};

export function PropertySearchPanel({ latitude, longitude, onClose }: PropertySearchPanelProps) {
  const [links, setLinks] = useState<PropertySearchLinks | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchLinks() {
      setIsLoading(true);
      setError(null);

      try {
        const result = await analysisApi.searchProperties({
          latitude,
          longitude,
          radius_miles: 10,
        });

        if (mounted && result.external_links) {
          setLinks(result.external_links);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to generate search links');
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    fetchLinks();

    return () => {
      mounted = false;
    };
  }, [latitude, longitude]);

  const handleLinkClick = (link: ExternalSearchLink) => {
    window.open(link.url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="absolute bottom-24 left-4 z-50 bg-white rounded-lg shadow-xl border border-gray-200 w-80">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-green-600 text-white rounded-t-lg">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5" />
          <span className="font-semibold">Find Commercial Properties</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-green-700 rounded transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {isLoading ? (
          <div className="text-center py-6 text-gray-500">
            <div className="animate-spin inline-block w-6 h-6 border-2 border-green-600 border-t-transparent rounded-full mb-2" />
            <p className="text-sm">Generating search links...</p>
          </div>
        ) : error ? (
          <div className="text-center py-4 text-red-600 text-sm">
            {error}
          </div>
        ) : links ? (
          <>
            {/* Location indicator */}
            <div className="flex items-center gap-2 text-sm text-gray-600 mb-4 pb-3 border-b border-gray-200">
              <MapPin className="w-4 h-4 text-green-600" />
              <span className="font-medium">{links.city}, {links.state}</span>
            </div>

            {/* Description */}
            <p className="text-xs text-gray-500 mb-4">
              Click below to search commercial real estate listings on these platforms.
              Results open in a new tab with your location pre-filled.
            </p>

            {/* External links */}
            <div className="space-y-2">
              {links.links.map((link) => {
                const style = SOURCE_ICONS[link.icon] || SOURCE_ICONS.google;
                return (
                  <button
                    key={link.name}
                    onClick={() => handleLinkClick(link)}
                    className={`w-full flex items-center justify-between px-4 py-3 rounded-lg ${style.bg} ${style.text} hover:opacity-90 transition-opacity group`}
                  >
                    <div className="flex items-center gap-3">
                      <Search className="w-4 h-4" />
                      <span className="font-medium">{link.name}</span>
                    </div>
                    <ExternalLink className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
                  </button>
                );
              })}
            </div>

            {/* Tip */}
            <p className="text-[10px] text-gray-400 mt-4 text-center">
              Tip: Create free accounts on these platforms to save listings and get alerts
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}
