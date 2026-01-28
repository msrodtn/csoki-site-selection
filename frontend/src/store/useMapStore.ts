import { create } from 'zustand';
import type { Store, BrandKey, TradeAreaAnalysis, POICategory } from '../types/store';

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

  // Trade Area Analysis
  analysisResult: TradeAreaAnalysis | null;
  setAnalysisResult: (result: TradeAreaAnalysis | null) => void;
  isAnalyzing: boolean;
  setIsAnalyzing: (analyzing: boolean) => void;
  analysisError: string | null;
  setAnalysisError: (error: string | null) => void;
  analysisRadius: number;
  setAnalysisRadius: (radius: number) => void;

  // POI visibility by category
  visiblePOICategories: Set<POICategory>;
  togglePOICategory: (category: POICategory) => void;
  setAllPOICategoriesVisible: (visible: boolean) => void;

  // Analysis panel visibility
  showAnalysisPanel: boolean;
  setShowAnalysisPanel: (show: boolean) => void;

  // Clear analysis
  clearAnalysis: () => void;
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

const ALL_POI_CATEGORIES: POICategory[] = [
  'anchors',
  'quick_service',
  'restaurants',
  'retail',
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

  // Trade Area Analysis
  analysisResult: null,
  setAnalysisResult: (result) => set({ analysisResult: result }),
  isAnalyzing: false,
  setIsAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),
  analysisError: null,
  setAnalysisError: (error) => set({ analysisError: error }),
  analysisRadius: 1.0,
  setAnalysisRadius: (radius) => set({ analysisRadius: radius }),

  // POI visibility - all visible by default
  visiblePOICategories: new Set(ALL_POI_CATEGORIES),
  togglePOICategory: (category) =>
    set((state) => {
      const newCategories = new Set(state.visiblePOICategories);
      if (newCategories.has(category)) {
        newCategories.delete(category);
      } else {
        newCategories.add(category);
      }
      return { visiblePOICategories: newCategories };
    }),
  setAllPOICategoriesVisible: (visible) =>
    set({ visiblePOICategories: visible ? new Set(ALL_POI_CATEGORIES) : new Set() }),

  // Analysis panel
  showAnalysisPanel: false,
  setShowAnalysisPanel: (show) => set({ showAnalysisPanel: show }),

  // Clear all analysis state
  clearAnalysis: () =>
    set({
      analysisResult: null,
      analysisError: null,
      showAnalysisPanel: false,
    }),
}));
