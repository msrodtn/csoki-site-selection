import { create } from 'zustand';
import type { Map as MapboxMap } from 'mapbox-gl';
import type {
  Store,
  BrandKey,
  TradeAreaAnalysis,
  POICategory,
  DemographicsResponse,
  NearestCompetitorsResponse,
  TrafficAnalysis,
  SavedLocation,
  PropertySearchResult,
  PropertyType,
  PropertyListing,
  ParcelInfo,
  OpportunitySearchResponse,
  OpportunityRanking,
  ActivityNodeCategory,
} from '../types/store';

// Target market states
const TARGET_STATES = ['IA', 'NE', 'NV', 'ID'];

interface MapState {
  // Mapbox Map instance (for direct navigation)
  mapInstance: MapboxMap | null;
  setMapInstance: (map: MapboxMap | null) => void;

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

  // Individual POI visibility (for hierarchical toggles)
  hiddenPOIs: Set<string>; // Set of place_ids to hide
  togglePOI: (placeId: string) => void;
  showAllPOIsInCategory: (category: POICategory, pois: Array<{ place_id: string; category: POICategory }>) => void;
  hideAllPOIsInCategory: (category: POICategory, pois: Array<{ place_id: string; category: POICategory }>) => void;

  // Expanded POI categories in panel (for hierarchical UI)
  expandedPOICategories: Set<POICategory>;
  togglePOICategoryExpanded: (category: POICategory) => void;

  // POI selection state (for native layer feature state)
  selectedPOIId: string | null;
  setSelectedPOIId: (id: string | null) => void;
  hoveredPOIId: string | null;
  setHoveredPOIId: (id: string | null) => void;

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

  // Traffic Counts (Streetlight)
  trafficData: TrafficAnalysis | null;
  setTrafficData: (data: TrafficAnalysis | null) => void;
  isTrafficLoading: boolean;
  setIsTrafficLoading: (loading: boolean) => void;
  trafficError: string | null;
  setTrafficError: (error: string | null) => void;

  // Map Layers
  visibleLayers: Set<string>;
  toggleLayer: (layer: string) => void;
  setLayerVisible: (layer: string, visible: boolean) => void;

  // Property source sub-toggles (for Properties For Sale layer)
  visiblePropertySources: Set<'attom' | 'team'>;
  togglePropertySource: (source: 'attom' | 'team') => void;

  // Boundary type sub-toggles (for Boundaries Explorer layer)
  visibleBoundaryTypes: Set<'counties' | 'cities' | 'zipcodes' | 'census_tracts'>;
  toggleBoundaryType: (type: 'counties' | 'cities' | 'zipcodes' | 'census_tracts') => void;

  // Activity node sub-toggles (for Activity Heat Map layer)
  visibleActivityNodeCategories: Set<ActivityNodeCategory>;
  toggleActivityNodeCategory: (category: ActivityNodeCategory) => void;

  // Demographic metric for choropleth coloring
  demographicMetric: 'population' | 'income' | 'density';
  setDemographicMetric: (metric: 'population' | 'income' | 'density') => void;

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

  // Selected Property (for info window)
  selectedProperty: PropertyListing | null;
  setSelectedProperty: (property: PropertyListing | null) => void;

  // Property Parcel (auto-fetched when property is selected)
  propertyParcel: ParcelInfo | null;
  setPropertyParcel: (parcel: ParcelInfo | null) => void;
  isLoadingPropertyParcel: boolean;
  setIsLoadingPropertyParcel: (loading: boolean) => void;
  propertyParcelError: string | null;
  setPropertyParcelError: (error: string | null) => void;
  showPropertyParcelPanel: boolean;
  setShowPropertyParcelPanel: (show: boolean) => void;

  // Opportunities (CSOKi-filtered ATTOM properties)
  opportunitiesResult: OpportunitySearchResponse | null;
  setOpportunitiesResult: (result: OpportunitySearchResponse | null) => void;
  isLoadingOpportunities: boolean;
  setIsLoadingOpportunities: (loading: boolean) => void;
  opportunitiesError: string | null;
  setOpportunitiesError: (error: string | null) => void;
  selectedOpportunity: OpportunityRanking | null;
  setSelectedOpportunity: (opportunity: OpportunityRanking | null) => void;
  clearOpportunities: () => void;

  // Opportunity Filters (CSOKi criteria)
  opportunityFilters: {
    minParcelAcres: number;
    maxParcelAcres: number;
    minBuildingSqft: number;
    maxBuildingSqft: number;
    includeLand: boolean;
    includeRetail: boolean;
    includeOffice: boolean;
  };
  setOpportunityFilters: (filters: Partial<MapState['opportunityFilters']>) => void;

  // Draw-to-analyze polygon
  drawnPolygon: GeoJSON.Feature | null;
  setDrawnPolygon: (polygon: GeoJSON.Feature | null) => void;
  isDrawMode: boolean;
  setIsDrawMode: (active: boolean) => void;

  // Measurement tool
  isMeasureMode: boolean;
  setIsMeasureMode: (active: boolean) => void;
  measureType: 'line' | 'polygon';
  setMeasureType: (type: 'line' | 'polygon') => void;
  measureUnit: 'feet' | 'miles' | 'km' | 'meters';
  setMeasureUnit: (unit: 'feet' | 'miles' | 'km' | 'meters') => void;
  measureAreaUnit: 'sqft' | 'acres' | 'sqmiles';
  setMeasureAreaUnit: (unit: 'sqft' | 'acres' | 'sqmiles') => void;
  measurePoints: [number, number][];
  addMeasurePoint: (point: [number, number]) => void;
  clearMeasurement: () => void;
  isMeasurementComplete: boolean;
  setIsMeasurementComplete: (complete: boolean) => void;

  // Clear analysis
  clearAnalysis: () => void;

  // ============================================
  // deck.gl 3D Visualization State
  // ============================================

  // 3D visualization mode toggle
  show3DVisualization: boolean;
  toggle3DVisualization: () => void;
  set3DVisualization: (show: boolean) => void;

  // deck.gl layer visibility
  deckLayerVisibility: {
    opportunityHexagons: boolean;
    competitorArcs: boolean;
  };
  toggleDeckLayer: (layer: 'opportunityHexagons' | 'competitorArcs') => void;
  setDeckLayerVisible: (layer: 'opportunityHexagons' | 'competitorArcs', visible: boolean) => void;

  // Hexagon layer settings
  hexagonSettings: {
    radius: number;
    elevationScale: number;
    colorMode: 'opportunity' | 'competition';
  };
  setHexagonSettings: (settings: Partial<MapState['hexagonSettings']>) => void;

  // Arc layer settings
  arcSettings: {
    highlightedCompetitorId: number | null;
    siteLocation: [number, number] | null;
  };
  setArcSettings: (settings: Partial<MapState['arcSettings']>) => void;

  // Competitor access analysis state
  competitorAccessResult: any | null;
  setCompetitorAccessResult: (result: any | null) => void;
  isLoadingCompetitorAccess: boolean;
  setIsLoadingCompetitorAccess: (loading: boolean) => void;
  competitorAccessError: string | null;
  setCompetitorAccessError: (error: string | null) => void;
  showCompetitorAccessPanel: boolean;
  setShowCompetitorAccessPanel: (show: boolean) => void;

  // Building Layer state
  showBuildingLayer: boolean;
  setShowBuildingLayer: (show: boolean) => void;
  selectedBuildingId: number | null;
  setSelectedBuildingId: (id: number | null) => void;
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
  'entertainment',
  'services',
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
      map.flyTo({
        center: [lng, lat],
        zoom,
        duration: 1500,
      });
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

  // Individual POI visibility (for hierarchical toggles)
  hiddenPOIs: new Set<string>(),
  togglePOI: (placeId) =>
    set((state) => {
      const newHidden = new Set(state.hiddenPOIs);
      if (newHidden.has(placeId)) {
        newHidden.delete(placeId);
      } else {
        newHidden.add(placeId);
      }
      return { hiddenPOIs: newHidden };
    }),
  showAllPOIsInCategory: (category, pois) =>
    set((state) => {
      const newHidden = new Set(state.hiddenPOIs);
      pois.filter((p) => p.category === category).forEach((p) => newHidden.delete(p.place_id));
      return { hiddenPOIs: newHidden };
    }),
  hideAllPOIsInCategory: (category, pois) =>
    set((state) => {
      const newHidden = new Set(state.hiddenPOIs);
      pois.filter((p) => p.category === category).forEach((p) => newHidden.add(p.place_id));
      return { hiddenPOIs: newHidden };
    }),

  // Expanded POI categories in panel (for hierarchical UI)
  expandedPOICategories: new Set<POICategory>(),
  togglePOICategoryExpanded: (category) =>
    set((state) => {
      const newExpanded = new Set(state.expandedPOICategories);
      if (newExpanded.has(category)) {
        newExpanded.delete(category);
      } else {
        newExpanded.add(category);
      }
      return { expandedPOICategories: newExpanded };
    }),

  // POI selection state (for native layer feature state)
  selectedPOIId: null,
  setSelectedPOIId: (id) => set({ selectedPOIId: id }),
  hoveredPOIId: null,
  setHoveredPOIId: (id) => set({ hoveredPOIId: id }),

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

  // Traffic Counts (Streetlight)
  trafficData: null,
  setTrafficData: (data) => set({ trafficData: data }),
  isTrafficLoading: false,
  setIsTrafficLoading: (loading) => set({ isTrafficLoading: loading }),
  trafficError: null,
  setTrafficError: (error) => set({ trafficError: error }),

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

  // Property source sub-toggles - all visible by default
  visiblePropertySources: new Set<'attom' | 'team'>(['attom', 'team']),
  togglePropertySource: (source) =>
    set((state) => {
      const newSources = new Set(state.visiblePropertySources);
      if (newSources.has(source)) {
        newSources.delete(source);
      } else {
        newSources.add(source);
      }
      return { visiblePropertySources: newSources };
    }),

  // Boundary type sub-toggles - counties and cities visible by default
  visibleBoundaryTypes: new Set<'counties' | 'cities' | 'zipcodes' | 'census_tracts'>(['counties', 'cities']),
  toggleBoundaryType: (type) =>
    set((state) => {
      const newTypes = new Set(state.visibleBoundaryTypes);
      if (newTypes.has(type)) {
        newTypes.delete(type);
      } else {
        newTypes.add(type);
      }
      return { visibleBoundaryTypes: newTypes };
    }),

  // Activity node sub-toggles - all categories visible by default
  visibleActivityNodeCategories: new Set<ActivityNodeCategory>(['shopping', 'entertainment', 'dining']),
  toggleActivityNodeCategory: (category) =>
    set((state) => {
      const newCats = new Set(state.visibleActivityNodeCategories);
      if (newCats.has(category)) {
        newCats.delete(category);
      } else {
        newCats.add(category);
      }
      return { visibleActivityNodeCategories: newCats };
    }),

  // Demographic metric for choropleth coloring
  demographicMetric: 'population',
  setDemographicMetric: (metric) => set({ demographicMetric: metric }),

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

  // Selected Property (for info window)
  selectedProperty: null,
  setSelectedProperty: (property) => set({ selectedProperty: property }),

  // Property Parcel (auto-fetched when property is selected)
  propertyParcel: null,
  setPropertyParcel: (parcel) => set({ propertyParcel: parcel }),
  isLoadingPropertyParcel: false,
  setIsLoadingPropertyParcel: (loading) => set({ isLoadingPropertyParcel: loading }),
  propertyParcelError: null,
  setPropertyParcelError: (error) => set({ propertyParcelError: error }),
  showPropertyParcelPanel: false,
  setShowPropertyParcelPanel: (show) => set({ showPropertyParcelPanel: show }),

  // Opportunities (CSOKi-filtered ATTOM properties)
  opportunitiesResult: null,
  setOpportunitiesResult: (result) => set({ opportunitiesResult: result }),
  isLoadingOpportunities: false,
  setIsLoadingOpportunities: (loading) => set({ isLoadingOpportunities: loading }),
  opportunitiesError: null,
  setOpportunitiesError: (error) => set({ opportunitiesError: error }),
  selectedOpportunity: null,
  setSelectedOpportunity: (opportunity) => set({ selectedOpportunity: opportunity }),
  clearOpportunities: () =>
    set({
      opportunitiesResult: null,
      opportunitiesError: null,
      selectedOpportunity: null,
    }),

  // Opportunity Filters (CSOKi criteria - defaults match store requirements)
  opportunityFilters: {
    minParcelAcres: 0.8,
    maxParcelAcres: 2.0,
    minBuildingSqft: 2500,
    maxBuildingSqft: 6000,
    includeLand: true,
    includeRetail: true,
    includeOffice: true,
  },
  setOpportunityFilters: (filters) =>
    set((state) => ({
      opportunityFilters: { ...state.opportunityFilters, ...filters },
    })),

  // Draw-to-analyze polygon
  drawnPolygon: null,
  setDrawnPolygon: (polygon) => set({ drawnPolygon: polygon }),
  isDrawMode: false,
  setIsDrawMode: (active) => set({ isDrawMode: active }),

  // Measurement tool
  isMeasureMode: false,
  setIsMeasureMode: (active) =>
    set({
      isMeasureMode: active,
      // Clear existing measurement when activating
      ...(active ? { measurePoints: [], isMeasurementComplete: false, isDrawMode: false } : {}),
    }),
  measureType: 'line',
  setMeasureType: (type) => set({ measureType: type, measurePoints: [], isMeasurementComplete: false }),
  measureUnit: 'feet',
  setMeasureUnit: (unit) => set({ measureUnit: unit }),
  measureAreaUnit: 'acres',
  setMeasureAreaUnit: (unit) => set({ measureAreaUnit: unit }),
  measurePoints: [],
  addMeasurePoint: (point) =>
    set((state) => ({ measurePoints: [...state.measurePoints, point] })),
  clearMeasurement: () => set({ measurePoints: [], isMeasurementComplete: false }),
  isMeasurementComplete: false,
  setIsMeasurementComplete: (complete) => set({ isMeasurementComplete: complete }),

  // Clear all analysis state
  clearAnalysis: () =>
    set({
      analysisResult: null,
      analyzedStore: null,
      analysisError: null,
      showAnalysisPanel: false,
      demographicsData: null,
      demographicsError: null,
      trafficData: null,
      trafficError: null,
      nearestCompetitors: null,
      hiddenPOIs: new Set<string>(),
      expandedPOICategories: new Set<POICategory>(),
      selectedPOIId: null,
      hoveredPOIId: null,
      drawnPolygon: null,
      isDrawMode: false,
    }),

  // ============================================
  // deck.gl 3D Visualization State
  // ============================================

  // 3D visualization mode
  show3DVisualization: false,
  toggle3DVisualization: () =>
    set((state) => ({ show3DVisualization: !state.show3DVisualization })),
  set3DVisualization: (show) => set({ show3DVisualization: show }),

  // deck.gl layer visibility
  deckLayerVisibility: {
    opportunityHexagons: false,
    competitorArcs: false,
  },
  toggleDeckLayer: (layer) =>
    set((state) => ({
      deckLayerVisibility: {
        ...state.deckLayerVisibility,
        [layer]: !state.deckLayerVisibility[layer],
      },
    })),
  setDeckLayerVisible: (layer, visible) =>
    set((state) => ({
      deckLayerVisibility: {
        ...state.deckLayerVisibility,
        [layer]: visible,
      },
    })),

  // Hexagon layer settings
  hexagonSettings: {
    radius: 500,
    elevationScale: 50,
    colorMode: 'opportunity',
  },
  setHexagonSettings: (settings) =>
    set((state) => ({
      hexagonSettings: { ...state.hexagonSettings, ...settings },
    })),

  // Arc layer settings
  arcSettings: {
    highlightedCompetitorId: null,
    siteLocation: null,
  },
  setArcSettings: (settings) =>
    set((state) => ({
      arcSettings: { ...state.arcSettings, ...settings },
    })),

  // Competitor access analysis
  competitorAccessResult: null,
  setCompetitorAccessResult: (result) => set({ competitorAccessResult: result }),
  isLoadingCompetitorAccess: false,
  setIsLoadingCompetitorAccess: (loading) => set({ isLoadingCompetitorAccess: loading }),
  competitorAccessError: null,
  setCompetitorAccessError: (error) => set({ competitorAccessError: error }),
  showCompetitorAccessPanel: false,
  setShowCompetitorAccessPanel: (show) => set({ showCompetitorAccessPanel: show }),

  // Building Layer state
  showBuildingLayer: false,
  setShowBuildingLayer: (show) => set({ showBuildingLayer: show }),
  selectedBuildingId: null,
  setSelectedBuildingId: (id) => set({ selectedBuildingId: id }),
}));
