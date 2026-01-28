import { create } from 'zustand';
import type { Store, BrandKey } from '../types/store';

interface MapState {
  // View state
  viewport: {
    latitude: number;
    longitude: number;
    zoom: number;
  };
  setViewport: (viewport: Partial<MapState['viewport']>) => void;

  // Selected store
  selectedStore: Store | null;
  setSelectedStore: (store: Store | null) => void;

  // Brand filters
  visibleBrands: Set<BrandKey>;
  toggleBrand: (brand: BrandKey) => void;
  setAllBrandsVisible: (visible: boolean) => void;

  // State filter
  selectedState: string | null;
  setSelectedState: (state: string | null) => void;

  // Hover state
  hoveredStoreId: number | null;
  setHoveredStoreId: (id: number | null) => void;
}

// Default to center of US with all brands visible
const ALL_BRANDS: BrandKey[] = [
  'csoki',
  'russell_cellular',
  'verizon_corporate',
  'victra',
  'tmobile',
  'uscellular',
];

export const useMapStore = create<MapState>((set) => ({
  // Initial viewport - centered on Iowa/Nebraska region
  viewport: {
    latitude: 41.5,
    longitude: -96.0,
    zoom: 6,
  },
  setViewport: (viewport) =>
    set((state) => ({
      viewport: { ...state.viewport, ...viewport },
    })),

  // Selected store
  selectedStore: null,
  setSelectedStore: (store) => set({ selectedStore: store }),

  // Brand visibility - all visible by default
  visibleBrands: new Set(ALL_BRANDS),
  toggleBrand: (brand) =>
    set((state) => {
      const newBrands = new Set(state.visibleBrands);
      if (newBrands.has(brand)) {
        newBrands.delete(brand);
      } else {
        newBrands.add(brand);
      }
      return { visibleBrands: newBrands };
    }),
  setAllBrandsVisible: (visible) =>
    set({ visibleBrands: visible ? new Set(ALL_BRANDS) : new Set() }),

  // State filter
  selectedState: null,
  setSelectedState: (state) => set({ selectedState: state }),

  // Hover
  hoveredStoreId: null,
  setHoveredStoreId: (id) => set({ hoveredStoreId: id }),
}));
