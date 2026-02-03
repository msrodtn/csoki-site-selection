/**
 * URL Import Panel - Quick listing import from Crexi/LoopNet URLs
 * 
 * Allows users to paste a listing URL and automatically extract data.
 * Created by Flash - Feb 3, 2026
 */

import React, { useState } from 'react';
import { X, Link as LinkIcon, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { api } from '../../services/api';

interface URLImportPanelProps {
  onClose: () => void;
  onSuccess?: (listingId: number) => void;
}

interface ImportResult {
  success: boolean;
  source: string;
  external_id?: string;
  listing_url: string;
  
  // Extracted data
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  latitude?: number;
  longitude?: number;
  property_type?: string;
  price?: number;
  price_display?: string;
  sqft?: number;
  lot_size_acres?: number;
  year_built?: number;
  title?: string;
  description?: string;
  broker_name?: string;
  broker_company?: string;
  images?: string[];
  
  // Metadata
  confidence: number;
  extraction_method: string;
  error_message?: string;
  listing_id?: number;
}

export const URLImportPanel: React.FC<URLImportPanelProps> = ({
  onClose,
  onSuccess
}) => {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [step, setStep] = useState<'input' | 'preview' | 'success'>('input');

  const handleExtract = async () => {
    if (!url.trim()) {
      alert('Please enter a URL');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // First, extract without saving (preview mode)
      const response = await api.post('/listings/import-url/', {
        url: url.trim(),
        use_playwright: true,
        save_to_database: false
      });

      setResult(response.data);
      if (response.data.success) {
        setStep('preview');
      } else {
        // Show error but stay on input step
        alert(`Failed to extract data: ${response.data.error_message || 'Unknown error'}`);
      }
    } catch (error: any) {
      console.error('Import error:', error);
      alert(`Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!result) return;

    setLoading(true);

    try {
      // Now save to database
      const response = await api.post('/listings/import-url/', {
        url: url.trim(),
        use_playwright: true,
        save_to_database: true
      });

      if (response.data.success && response.data.listing_id) {
        setStep('success');
        if (onSuccess) {
          onSuccess(response.data.listing_id);
        }
      } else {
        alert('Failed to save listing');
      }
    } catch (error: any) {
      console.error('Save error:', error);
      alert(`Error saving: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'bg-green-500';
    if (confidence >= 60) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 80) return 'High Confidence';
    if (confidence >= 60) return 'Medium Confidence';
    return 'Low Confidence';
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white">
          <div className="flex items-center gap-2">
            <LinkIcon className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-semibold">Import from URL</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {step === 'input' && (
            <>
              <p className="text-sm text-gray-600 mb-4">
                Paste a Crexi, LoopNet, or other commercial real estate listing URL.
                We'll automatically extract all the property details.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Listing URL
                  </label>
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://www.crexi.com/properties/..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={loading}
                  />
                </div>

                <button
                  onClick={handleExtract}
                  disabled={loading || !url.trim()}
                  className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin" />
                      Extracting data...
                    </>
                  ) : (
                    <>
                      <LinkIcon className="w-4 h-4" />
                      Extract Data
                    </>
                  )}
                </button>
              </div>

              <div className="mt-6 p-4 bg-blue-50 rounded-md">
                <h3 className="font-medium text-sm mb-2">Pro Tip: Use the Bookmarklet</h3>
                <p className="text-xs text-gray-600">
                  For even faster imports, drag the "Add to CSOKi" bookmarklet to your
                  bookmarks bar. Then you can add listings with one click while browsing!
                </p>
              </div>
            </>
          )}

          {step === 'preview' && result && (
            <>
              {/* Confidence Badge */}
              <div className="mb-4 flex items-center gap-2">
                <div className={`${getConfidenceColor(result.confidence)} text-white px-3 py-1 rounded-full text-xs font-semibold`}>
                  {getConfidenceLabel(result.confidence)} ({result.confidence}%)
                </div>
                <div className="text-xs text-gray-500">
                  via {result.source}
                </div>
              </div>

              {/* Extracted Data Preview */}
              <div className="space-y-3">
                {result.title && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">TITLE</div>
                    <div className="text-sm">{result.title}</div>
                  </div>
                )}

                {result.address && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">ADDRESS</div>
                    <div className="text-sm">{result.address}</div>
                    {result.city && (
                      <div className="text-sm text-gray-600">
                        {result.city}, {result.state} {result.postal_code}
                      </div>
                    )}
                  </div>
                )}

                {result.price_display && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">PRICE</div>
                    <div className="text-sm font-semibold">{result.price_display}</div>
                  </div>
                )}

                {result.property_type && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">PROPERTY TYPE</div>
                    <div className="text-sm">{result.property_type}</div>
                  </div>
                )}

                {(result.sqft || result.lot_size_acres) && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">SIZE</div>
                    <div className="text-sm">
                      {result.sqft && `${result.sqft.toLocaleString()} SF`}
                      {result.sqft && result.lot_size_acres && ' • '}
                      {result.lot_size_acres && `${result.lot_size_acres} AC`}
                    </div>
                  </div>
                )}

                {result.description && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">DESCRIPTION</div>
                    <div className="text-sm text-gray-600 line-clamp-3">{result.description}</div>
                  </div>
                )}

                {result.broker_name && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">BROKER</div>
                    <div className="text-sm">
                      {result.broker_name}
                      {result.broker_company && ` • ${result.broker_company}`}
                    </div>
                  </div>
                )}

                {result.images && result.images.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 font-medium">IMAGES</div>
                    <div className="text-sm">{result.images.length} image(s) found</div>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="mt-6 flex gap-3">
                <button
                  onClick={handleSave}
                  disabled={loading}
                  className="flex-1 bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Save to Database
                    </>
                  )}
                </button>
                <button
                  onClick={() => {
                    setStep('input');
                    setResult(null);
                  }}
                  disabled={loading}
                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>

              {result.confidence < 60 && (
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                  <div className="flex gap-2">
                    <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
                    <div className="text-xs text-yellow-800">
                      <strong>Low confidence:</strong> Some fields may be missing or incorrect.
                      You can edit the listing after saving.
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {step === 'success' && result && (
            <div className="text-center py-8">
              <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Listing Saved!</h3>
              <p className="text-sm text-gray-600 mb-1">
                {result.title || 'Listing'} has been added to your database.
              </p>
              {result.listing_id && (
                <p className="text-xs text-gray-500">
                  Listing ID: {result.listing_id}
                </p>
              )}
              <button
                onClick={onClose}
                className="mt-6 bg-blue-600 text-white py-2 px-6 rounded-md hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default URLImportPanel;
