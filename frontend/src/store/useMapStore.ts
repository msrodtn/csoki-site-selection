import { create } from 'zustand';
import type {
  Store,
  BrandKey,
  TradeAreaAnalysis,
  POICategory,
  DemographicsResponse,
  NearestCompetitorsResponse,
  SavedLocation,
  PropertySearchResult,
  PropertyType,
} from '../types/store';

// Target market states
const TARGET_STATES = ['IA', 'NE', 'NV', 'ID'];

interface MapState {
  // Google Map instance (for direct navigation)
  mapInstance: google.maps.Map | null;
  setMapInstance: (map: google.maps.Map | null) => void;

  // Navigate to a location (calls map methods directly)
  navigateTo: (lat: number, lng: number, zoom: number) => void;

  // Selected store
  selectedStore: Store | null;
  setSelectedStore: (store: Store | null) => void;

  // Brand filters
  visibleBrands: Set<BrandKey>;
  toggleBrand: (brand: BrandKey) => void;
  setAllBrandsVisible: (visible: boolean) => void;

  // State visibility (which states' stores are shown)
  visibleStates: Set<string>;
  toggleStateVisibility: (state: string) => void;
  setAllStatesVisible: (visible: boolean) => void;

  // State display order (for drag-and-drop reordering)
  stateOrder: string[];
  setStateOrder: (order: string[]) => void;

  // Hover state
  hoveredStoreId: number | null;
  setHoveredStoreId: (id: number | null) => void;

  // Trade Area Analysis
  analysisResult: TradeAreaAnalysis | null;
  setAnalysisResult: (result: TradeAreaAnalysis | null) => void;
  analyzedStore: Store | null;  // Store info captured when analysis starts (persists even if selectedStore changes)
  setAnalyzedStore: (store: Store | null) => void;
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

  // Demographics (ArcGIS)
  demographicsData: DemographicsResponse | null;
  setDemographicsData: (data: DemographicsResponse | null) => void;
  isDemographicsLoading: boolean;
  setIsDemographicsLoading: (loading: boolean) => void;
  demographicsError: string | null;
  setDemographicsError: (error: string | null) => void;
  selectedDemographicsRadius: number;
  setSelectedDemographicsRadius: (radius: number) => void;

  // Map Layers
  visibleLayers: Set<string>;
  toggleLayer: (layer: string) => void;
  setLayerVisible: (layer: string, visible: boolean) => void;

  // Nearest Competitors
  nearestCompetitors: NearestCompetitorsResponse | null;
  setNearestCompetitors: (data: NearestCompetitorsResponse | null) => void;
  isNearestCompetitorsLoading: boolean;
  setIsNearestCompetitorsLoading: (loading: boolean) => void;

  // Saved Locations (for Compare feature)
  savedLocations: SavedLocation[];
  addSavedLocation: (location: SavedLocation) => void;
  removeSavedLocation: (id: string) => void;
  clearSavedLocations: () => void;

  // Compare Panel
  showComparePanel: boolean;
  setShowComparePanel: (show: boolean) => void;
  compareLocationIds: string[];
  setCompareLocationIds: (ids: string[]) => void;

  // Property Search (CRE Listings)
  propertySearchResult: PropertySearchResult | null;
  setPropertySearchResult: (result: PropertySearchResult | null) => void;
  isPropertySearching: boolean;
  setIsPropertySearching: (searching: boolean) => void;
  propertySearchError: string | null;
  setPropertySearchError: (error: string | null) => void;
  visiblePropertyTypes: Set<PropertyType>;
  togglePropertyType: (type: PropertyType) => void;
  setAllPropertyTypesVisible: (visible: boolean) => void;
  clearPropertySearch: () => void;

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

const ALL_PROPERTY_TYPES: PropertyType[] = [
  'retail',
  'land',
  'office',
  'industrial',
  'mixed_use',
];

export const useMapStore = create<MapState>((set, get) => ({
  // Map instance - stored for direct navigation
  mapInstance: null,
  setMapInstance: (map) => set({ mapInstance: map }),

  // Direct navigation - no state sync, just call map methods
  navigateTo: (lat, lng, zoom) => {
    const map = get().mapInstance;
    if (map) {
      map.panTo({ lat, lng });
      map.setZoom(zoom);
    }
  },

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

  // State visibility - only target markets visible by default
  visibleStates: new Set(TARGET_STATES),
  toggleStateVisibility: (stateCode) =>
    set((state) => {
      const newStates = new Set(state.visibleStates);
      if (newStates.has(stateCode)) {
        newStates.delete(stateCode);
      } else {
        newStates.add(stateCode);
      }
      return { visibleStates: newStates };
    }),
  setAllStatesVisible: (visible) =>
    set({ visibleStates: visible ? new Set(TARGET_STATES) : new Set() }),

  // State order - default order with priority markets first
  stateOrder: ['IA', 'NE', 'NV', 'ID'],
  setStateOrder: (order) => set({ stateOrder: order }),

  // Hover
  hoveredStoreId: null,
  setHoveredStoreId: (id) => set({ hoveredStoreId: id }),

  // Trade Area Analysis
  analysisResult: null,
  setAnalysisResult: (result) => set({ analysisResult: result }),
  analyzedStore: null,
  setAnalyzedStore: (store) => set({ analyzedStore: store }),
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

  // Demographics (ArcGIS)
  demographicsData: null,
  setDemographicsData: (data) => set({ demographicsData: data }),
  isDemographicsLoading: false,
  setIsDemographicsLoading: (loading) => set({ isDemographicsLoading: loading }),
  demographicsError: null,
  setDemographicsError: (error) => set({ demographicsError: error }),
  selectedDemographicsRadius: 1,  // Default to 1 mile view
  setSelectedDemographicsRadius: (radius) => set({ selectedDemographicsRadius: radius }),

  // Map Layers - none visible by default
  visibleLayers: new Set<string>(),
  toggleLayer: (layer) =>
    set((state) => {
      const newLayers = new Set(state.visibleLayers);
      if (newLayers.has(layer)) {
        newLayers.delete(layer);
      } else {
        newLayers.add(layer);
      }
      return { visibleLayers: newLayers };
    }),
  setLayerVisible: (layer, visible) =>
    set((state) => {
      const newLayers = new Set(state.visibleLayers);
      if (visible) {
        newLayers.add(layer);
      } else {
        newLayers.delete(layer);
      }
      return { visibleLayers: newLayers };
    }),

  // Nearest Competitors
  nearestCompetitors: null,
  setNearestCompetitors: (data) => set({ nearestCompetitors: data }),
  isNearestCompetitorsLoading: false,
  setIsNearestCompetitorsLoading: (loading) => set({ isNearestCompetitorsLoading: loading }),

  // Saved Locations (for Compare feature)
  savedLocations: [],
  addSavedLocation: (location) =>
    set((state) => ({
      savedLocations: [...state.savedLocations, location],
    })),
  removeSavedLocation: (id) =>
    set((state) => ({
      savedLocations: state.savedLocations.filter((loc) => loc.id !== id),
    })),
  clearSavedLocations: () => set({ savedLocations: [] }),

  // Compare Panel
  showComparePanel: false,
  setShowComparePanel: (show) => set({ showComparePanel: show }),
  compareLocationIds: [],
  setCompareLocationIds: (ids) => set({ compareLocationIds: ids }),

  // Property Search (CRE Listings)
  propertySearchResult: null,
  setPropertySearchResult: (result) => set({ propertySearchResult: result }),
  isPropertySearching: false,
  setIsPropertySearching: (searching) => set({ isPropertySearching: searching }),
  propertySearchError: null,
  setPropertySearchError: (error) => set({ propertySearchError: error }),
  visiblePropertyTypes: new Set(ALL_PROPERTY_TYPES),
  togglePropertyType: (type) =>
    set((state) => {
      const newTypes = new Set(state.visiblePropertyTypes);
      if (newTypes.has(type)) {
        newTypes.delete(type);
      } else {
        newTypes.add(type);
      }
      return { visiblePropertyTypes: newTypes };
    }),
  setAllPropertyTypesVisible: (visible) =>
    set({ visiblePropertyTypes: visible ? new Set(ALL_PROPERTY_TYPES) : new Set() }),
  clearPropertySearch: () =>
    set({
      propertySearchResult: null,
      propertySearchError: null,
    }),

  // Clear all analysis state
  clearAnalysis: () =>
    set({
      analysisResult: null,
      analyzedStore: null,
      analysisError: null,
      showAnalysisPanel: false,
      demographicsData: null,
      demographicsError: null,
      nearestCompetitors: null,
    }),
}));
