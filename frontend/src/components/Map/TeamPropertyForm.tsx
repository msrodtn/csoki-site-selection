/**
 * TeamPropertyForm - Modal form for flagging user-contributed properties
 *
 * Used when field reps spot properties with "For Sale" signs,
 * get tips from brokers, or hear about opportunities.
 */

import { useState, useCallback, useEffect } from 'react';
import { X, MapPin, Building2, DollarSign, FileText, User, Link, Loader2 } from 'lucide-react';
import { teamPropertiesApi } from '../../services/api';
import type { TeamPropertyCreate, PropertyType, TeamPropertySourceType } from '../../types/store';

interface TeamPropertyFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  // Pre-fill location if user clicked on map
  initialLatitude?: number;
  initialLongitude?: number;
}

const SOURCE_TYPE_OPTIONS: { value: TeamPropertySourceType; label: string }[] = [
  { value: 'for_sale_sign', label: 'Saw "For Sale" Sign' },
  { value: 'broker', label: 'Broker Contact' },
  { value: 'word_of_mouth', label: 'Word of Mouth' },
  { value: 'other', label: 'Other' },
];

const PROPERTY_TYPE_OPTIONS: { value: PropertyType; label: string }[] = [
  { value: 'retail', label: 'Retail' },
  { value: 'land', label: 'Land' },
  { value: 'office', label: 'Office' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'mixed_use', label: 'Mixed Use' },
];

export function TeamPropertyForm({
  isOpen,
  onClose,
  onSuccess,
  initialLatitude,
  initialLongitude,
}: TeamPropertyFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [latitude, setLatitude] = useState(initialLatitude?.toString() || '');
  const [longitude, setLongitude] = useState(initialLongitude?.toString() || '');
  const [propertyType, setPropertyType] = useState<PropertyType>('retail');
  const [sourceType, setSourceType] = useState<TeamPropertySourceType>('for_sale_sign');
  const [price, setPrice] = useState('');
  const [sqft, setSqft] = useState('');
  const [listingUrl, setListingUrl] = useState('');
  const [notes, setNotes] = useState('');
  const [contributorName, setContributorName] = useState('');

  // Update coordinates if initial values change
  useEffect(() => {
    if (initialLatitude !== undefined) {
      setLatitude(initialLatitude.toString());
    }
    if (initialLongitude !== undefined) {
      setLongitude(initialLongitude.toString());
    }
  }, [initialLatitude, initialLongitude]);

  const resetForm = useCallback(() => {
    setAddress('');
    setCity('');
    setState('');
    setPostalCode('');
    setLatitude(initialLatitude?.toString() || '');
    setLongitude(initialLongitude?.toString() || '');
    setPropertyType('retail');
    setSourceType('for_sale_sign');
    setPrice('');
    setSqft('');
    setListingUrl('');
    setNotes('');
    setContributorName('');
    setError(null);
  }, [initialLatitude, initialLongitude]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!address.trim()) {
      setError('Address is required');
      return;
    }
    if (!city.trim()) {
      setError('City is required');
      return;
    }
    if (!state.trim() || state.length !== 2) {
      setError('State must be a 2-letter code (e.g., IA, NE)');
      return;
    }
    if (!latitude || !longitude) {
      setError('Coordinates are required. Click on the map to set location.');
      return;
    }

    const lat = parseFloat(latitude);
    const lng = parseFloat(longitude);

    if (isNaN(lat) || isNaN(lng)) {
      setError('Invalid coordinates');
      return;
    }

    const propertyData: TeamPropertyCreate = {
      address: address.trim(),
      city: city.trim(),
      state: state.toUpperCase().trim(),
      postal_code: postalCode.trim() || undefined,
      latitude: lat,
      longitude: lng,
      property_type: propertyType,
      source_type: sourceType,
      price: price ? parseFloat(price) : undefined,
      sqft: sqft ? parseFloat(sqft) : undefined,
      listing_url: listingUrl.trim() || undefined,
      notes: notes.trim() || undefined,
      contributor_name: contributorName.trim() || undefined,
    };

    setIsSubmitting(true);

    try {
      await teamPropertiesApi.create(propertyData);
      resetForm();
      onSuccess();
      onClose();
    } catch (err) {
      console.error('Failed to create team property:', err);
      setError('Failed to save property. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-orange-50">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-orange-600" />
            <h2 className="text-lg font-semibold text-gray-900">Flag a Property</h2>
          </div>
          <button
            onClick={handleClose}
            className="p-1 hover:bg-orange-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="overflow-y-auto max-h-[calc(90vh-120px)]">
          <div className="p-4 space-y-4">
            {/* Error message */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            {/* Address */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Street Address *
              </label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="123 Main St"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                required
              />
            </div>

            {/* City, State, Zip */}
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  City *
                </label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Des Moines"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  State *
                </label>
                <input
                  type="text"
                  value={state}
                  onChange={(e) => setState(e.target.value.toUpperCase().slice(0, 2))}
                  placeholder="IA"
                  maxLength={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  ZIP
                </label>
                <input
                  type="text"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="50309"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                />
              </div>
            </div>

            {/* Coordinates */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Latitude *
                </label>
                <input
                  type="text"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  placeholder="41.5868"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Longitude *
                </label>
                <input
                  type="text"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  placeholder="-93.625"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  required
                />
              </div>
            </div>

            {/* How did you find this? */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <User className="w-4 h-4 inline mr-1" />
                How did you find this?
              </label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as TeamPropertySourceType)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              >
                {SOURCE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Property Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Building2 className="w-4 h-4 inline mr-1" />
                Property Type
              </label>
              <select
                value={propertyType}
                onChange={(e) => setPropertyType(e.target.value as PropertyType)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              >
                {PROPERTY_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Price and Sqft */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <DollarSign className="w-4 h-4 inline mr-1" />
                  Price (if known)
                </label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="500000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sqft (if known)
                </label>
                <input
                  type="number"
                  value={sqft}
                  onChange={(e) => setSqft(e.target.value)}
                  placeholder="2500"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                />
              </div>
            </div>

            {/* Listing URL */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Link className="w-4 h-4 inline mr-1" />
                Listing URL (optional)
              </label>
              <input
                type="url"
                value={listingUrl}
                onChange={(e) => setListingUrl(e.target.value)}
                placeholder="https://www.loopnet.com/..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <FileText className="w-4 h-4 inline mr-1" />
                Notes
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Good visibility from main road, former phone store..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 resize-none"
              />
            </div>

            {/* Contributor Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Your Name (optional)
              </label>
              <input
                type="text"
                value={contributorName}
                onChange={(e) => setContributorName(e.target.value)}
                placeholder="John Smith"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              />
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-4 py-3 border-t bg-gray-50">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <MapPin className="w-4 h-4" />
                  Flag Property
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default TeamPropertyForm;
