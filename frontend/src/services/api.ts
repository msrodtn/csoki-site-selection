import axios from 'axios';
import type {
  StoreListResponse,
  StoreStats,
  TradeAreaAnalysis,
  TradeAreaRequest,
  DemographicsResponse,
  DemographicsRequest,
  NearestCompetitorsResponse,
  NearestCompetitorsRequest,
  ParcelInfo,
  ParcelRequest,
  PropertySearchResult,
  PropertySearchRequest,
} from '../types/store';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const storeApi = {
  // Get all stores with optional filters
  getStores: async (params?: {
    brand?: string;
    state?: string;
    city?: string;
    limit?: number;
    offset?: number;
  }): Promise<StoreListResponse> => {
    const { data } = await api.get('/locations/', { params });
    return data;
  },

  // Get stores by state
  getStoresByState: async (
    state: string,
    brand?: string
  ): Promise<StoreListResponse> => {
    const { data } = await api.get(`/locations/state/${state}/`, {
      params: brand ? { brand } : undefined,
    });
    return data;
  },

  // Get stores within map bounds
  getStoresInBounds: async (bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
    brands?: string[];
  }): Promise<StoreListResponse> => {
    const { data } = await api.post('/locations/within-bounds/', bounds);
    return data;
  },

  // Get stores within radius
  getStoresInRadius: async (params: {
    latitude: number;
    longitude: number;
    radius_miles: number;
    brands?: string[];
  }): Promise<StoreListResponse> => {
    const { data } = await api.post('/locations/within-radius/', params);
    return data;
  },

  // Get all brand names
  getBrands: async (): Promise<string[]> => {
    const { data } = await api.get('/locations/brands/');
    return data;
  },

  // Get statistics
  getStats: async (): Promise<StoreStats[]> => {
    const { data } = await api.get('/locations/stats/');
    return data;
  },

  // Get nearest competitor of each brand from a point
  getNearestCompetitors: async (
    request: NearestCompetitorsRequest
  ): Promise<NearestCompetitorsResponse> => {
    const { data } = await api.post('/locations/nearest-competitors/', request);
    return data;
  },
};

export const analysisApi = {
  // Analyze trade area around a location
  analyzeTradeArea: async (request: TradeAreaRequest): Promise<TradeAreaAnalysis> => {
    const { data } = await api.post('/analysis/trade-area/', request);
    return data;
  },

  // Check if Places API key is configured
  checkApiKey: async (): Promise<{ configured: boolean; message: string }> => {
    const { data } = await api.get('/analysis/check-api-key/');
    return data;
  },

  // Get demographics data from ArcGIS
  getDemographics: async (request: DemographicsRequest): Promise<DemographicsResponse> => {
    const { data } = await api.post('/analysis/demographics/', request);
    return data;
  },

  // Check if ArcGIS API key is configured
  checkArcGISKey: async (): Promise<{ configured: boolean; message: string }> => {
    const { data } = await api.get('/analysis/check-arcgis-key/');
    return data;
  },

  // Get parcel information from ReportAll
  getParcelInfo: async (request: ParcelRequest): Promise<ParcelInfo> => {
    const { data } = await api.post('/analysis/parcel/', request);
    return data;
  },

  // Check if ReportAll API key is configured
  checkReportAllKey: async (): Promise<{ configured: boolean; message: string }> => {
    const { data } = await api.get('/analysis/check-reportall-key/');
    return data;
  },

  // Search for commercial properties for sale
  searchProperties: async (request: PropertySearchRequest): Promise<PropertySearchResult> => {
    const { data } = await api.post('/analysis/property-search/', request);
    return data;
  },

  // Check if property search API keys are configured
  checkPropertySearchKeys: async (): Promise<{
    tavily_configured: boolean;
    openai_configured: boolean;
    google_configured: boolean;
    crexi_configured: boolean;
    all_required_configured: boolean;
  }> => {
    const { data } = await api.get('/analysis/check-property-search-keys/');
    return data;
  },
};

export default api;
