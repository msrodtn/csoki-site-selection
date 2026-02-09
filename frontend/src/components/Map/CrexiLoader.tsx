/**
 * Crexi Loader - Upload Crexi CSV/Excel exports for import.
 *
 * User exports CSV from Crexi.com, uploads here, backend parses and
 * filters to empty land (0.8-2ac) and small buildings (2500-6000 sqft).
 */

import React, { useState, useRef, useCallback } from 'react';
import { X, Upload, CheckCircle, AlertCircle, Loader, FileSpreadsheet, ExternalLink } from 'lucide-react';
import { listingsApi } from '../../services/api';

interface CrexiLoaderProps {
  onClose: () => void;
  onSuccess?: (count: number) => void;
}

interface CrexiAreaResponse {
  success: boolean;
  imported: number;
  updated: number;
  total_filtered: number;
  empty_land_count: number;
  small_building_count: number;
  cached: boolean;
  cache_age_minutes: number | null;
  timestamp: string;
  expires_at: string;
  location: string;
  message: string | null;
}

export const CrexiLoader: React.FC<CrexiLoaderProps> = ({ onClose, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<CrexiAreaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    if (!validExtensions.includes(ext)) {
      setError(`Invalid file type "${ext}". Please upload an .xlsx, .xls, or .csv file.`);
      return;
    }

    setFileName(file.name);
    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const response = await listingsApi.uploadCrexiCSV(file);
      setResult(response);
      if (response.success && onSuccess) {
        onSuccess(response.total_filtered);
      }
    } catch (err: any) {
      console.error('Crexi upload error:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to upload Crexi CSV');
    } finally {
      setUploading(false);
    }
  }, [onSuccess]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <Upload className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Import Crexi Listings</h2>
              <p className="text-sm text-gray-500">Upload a CSV export from Crexi.com</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Instructions */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-900 mb-2">How to export from Crexi:</p>
            <ol className="text-sm text-blue-700 space-y-1 list-decimal list-inside">
              <li>Go to <a href="https://www.crexi.com/properties" target="_blank" rel="noopener noreferrer" className="underline font-medium inline-flex items-center gap-1">Crexi.com/properties <ExternalLink className="w-3 h-3 inline" /></a></li>
              <li>Search your target market and apply filters (Land, Retail, Office)</li>
              <li>Click the <strong>Export</strong> button to download the Excel file</li>
              <li>Upload that file below</li>
            </ol>
            <p className="text-xs text-blue-600 mt-2">
              Auto-filters to: empty land (0.8-2 acres) and small buildings (2,500-6,000 sqft, single-tenant)
            </p>
          </div>

          {/* Drop Zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
              ${isDragging
                ? 'border-emerald-400 bg-emerald-50'
                : uploading
                  ? 'border-gray-300 bg-gray-50 cursor-wait'
                  : 'border-gray-300 hover:border-emerald-400 hover:bg-emerald-50/50'
              }
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleFileInput}
              className="hidden"
              disabled={uploading}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-3">
                <Loader className="w-8 h-8 text-emerald-500 animate-spin" />
                <p className="text-sm text-gray-600">Uploading and parsing {fileName}...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <FileSpreadsheet className="w-10 h-10 text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    {fileName ? `Selected: ${fileName}` : 'Drop Crexi export here or click to browse'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Accepts .xlsx, .xls, or .csv</p>
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-900">Error</p>
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          )}

          {/* Success Result */}
          {result && result.success && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-3">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-emerald-900">
                    {result.message || 'Import complete!'}
                  </p>
                  <p className="text-sm text-emerald-700 mt-1">
                    <strong>{result.total_filtered}</strong> properties match criteria in {result.location}
                  </p>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div className="bg-white rounded-lg p-3">
                  <p className="text-xs text-gray-500">Empty Land</p>
                  <p className="text-2xl font-bold text-emerald-600">{result.empty_land_count}</p>
                  <p className="text-xs text-gray-500">0.8-2 acres</p>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <p className="text-xs text-gray-500">Small Buildings</p>
                  <p className="text-2xl font-bold text-emerald-600">{result.small_building_count}</p>
                  <p className="text-xs text-gray-500">2,500-6,000 sqft</p>
                </div>
              </div>

              {result.imported > 0 && (
                <p className="text-xs text-emerald-600">
                  + {result.imported} new propert{result.imported === 1 ? 'y' : 'ies'} added to database
                </p>
              )}
              {result.updated > 0 && (
                <p className="text-xs text-emerald-600">
                  + {result.updated} propert{result.updated === 1 ? 'y' : 'ies'} updated
                </p>
              )}

              <p className="text-xs text-gray-500">
                Listings will appear on the map when you toggle the CSOKi Opportunities layer.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
