import { useCallback, useMemo, useState } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF } from '@react-google-maps/api';
import { useMapStore } from '../../store/useMapStore';
import { useStores } from '../../hooks/useStores';
import { BRAND_COLORS, BRAND_LABELS, type BrandKey } from '../../types/store';
import type { Store } from '../../types/store';

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

const mapContainerStyle = {
  width: '100%',
  height: '100%',
};

const mapOptions: google.maps.MapOptions = {
  disableDefaultUI: false,
  zoomControl: true,
  mapTypeControl: true,
  scaleControl: true,
  streetViewControl: false,
  rotateControl: false,
  fullscreenControl: true,
  styles: [
    {
      featureType: 'poi',
      elementType: 'labels',
      stylers: [{ visibility: 'off' }],
    },
  ],
};

export function StoreMap() {
  const {
    viewport,
    selectedStore,
    setSelectedStore,
    visibleBrands,
    selectedState,
  } = useMapStore();

  const [map, setMap] = useState<google.maps.Map | null>(null);

  // Load Google Maps
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_API_KEY,
  });

  // Fetch stores based on state filter
  const { data: storeData, isLoading } = useStores({
    state: selectedState || undefined,
    limit: 5000,
  });

  // Convert Set to Array for reliable checking
  const visibleBrandsArray = useMemo(() => Array.from(visibleBrands), [visibleBrands]);

  // Filter stores by visible brands and those with coordinates
  const visibleStores = useMemo(() => {
    if (!storeData?.stores) return [];

    return storeData.stores.filter(
      (store) =>
        store.latitude != null &&
        store.longitude != null &&
        visibleBrandsArray.includes(store.brand as BrandKey)
    );
  }, [storeData?.stores, visibleBrandsArray]);

  const handleMarkerClick = useCallback(
    (store: Store) => {
      setSelectedStore(store);
    },
    [setSelectedStore]
  );

  const handleMapClick = useCallback(() => {
    setSelectedStore(null);
  }, [setSelectedStore]);

  const onLoad = useCallback((map: google.maps.Map) => {
    setMap(map);
  }, []);

  const onUnmount = useCallback(() => {
    setMap(null);
  }, []);

  // Update map center when viewport changes
  useMemo(() => {
    if (map && viewport) {
      map.panTo({ lat: viewport.latitude, lng: viewport.longitude });
      map.setZoom(viewport.zoom);
    }
  }, [map, viewport]);

  // Create SVG marker icon for each brand
  const createMarkerIcon = (brand: string, isSelected: boolean): google.maps.Symbol => {
    const color = BRAND_COLORS[brand as BrandKey] || '#666';
    const scale = isSelected ? 10 : 6;

    return {
      path: google.maps.SymbolPath.CIRCLE,
      fillColor: color,
      fillOpacity: 1,
      strokeColor: isSelected ? '#ffffff' : color,
      strokeWeight: isSelected ? 2 : 1,
      scale: scale,
    };
  };

  if (loadError) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100">
        <div className="text-red-600">Error loading Google Maps</div>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100">
        <div className="text-gray-600">Loading map...</div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Loading indicator */}
      {isLoading && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-white px-4 py-2 rounded-lg shadow-md">
          Loading stores...
        </div>
      )}

      {/* Store count */}
      <div className="absolute top-4 right-4 z-10 bg-white px-3 py-1 rounded-lg shadow-md text-sm">
        {visibleStores.length.toLocaleString()} stores visible
      </div>

      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        center={{ lat: viewport.latitude, lng: viewport.longitude }}
        zoom={viewport.zoom}
        onLoad={onLoad}
        onUnmount={onUnmount}
        onClick={handleMapClick}
        options={mapOptions}
      >
        {/* Store markers */}
        {visibleStores.map((store) => (
          <MarkerF
            key={store.id}
            position={{ lat: store.latitude!, lng: store.longitude! }}
            icon={createMarkerIcon(store.brand, selectedStore?.id === store.id)}
            onClick={() => handleMarkerClick(store)}
          />
        ))}

        {/* Info window for selected store */}
        {selectedStore && selectedStore.latitude && selectedStore.longitude && (
          <InfoWindowF
            position={{ lat: selectedStore.latitude, lng: selectedStore.longitude }}
            onCloseClick={() => setSelectedStore(null)}
          >
            <div className="min-w-[200px] p-1">
              <div
                className="text-xs font-semibold px-2 py-1 rounded mb-2 text-white"
                style={{
                  backgroundColor:
                    BRAND_COLORS[selectedStore.brand as BrandKey] || '#666',
                }}
              >
                {BRAND_LABELS[selectedStore.brand as BrandKey] || selectedStore.brand}
              </div>
              <div className="text-sm">
                {selectedStore.street && (
                  <p className="font-medium">{selectedStore.street}</p>
                )}
                <p>
                  {selectedStore.city}, {selectedStore.state} {selectedStore.postal_code}
                </p>
              </div>
            </div>
          </InfoWindowF>
        )}
      </GoogleMap>
    </div>
  );
}
