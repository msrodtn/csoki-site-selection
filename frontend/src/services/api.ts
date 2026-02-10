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
  TrafficAnalysis,
  TrafficCountsRequest,
  SegmentCountEstimate,
  ParcelInfo,
  ParcelRequest,
  PropertySearchResult,
  PropertySearchRequest,
  TeamProperty,
  TeamPropertyCreate,
  TeamPropertyListResponse,
  ScrapeRequest,
  ScrapeResponse,
  ScrapedListingsResponse,
  ScrapedSourcesStatus,
  OpportunitySearchRequest,
  OpportunitySearchResponse,
  MatrixRequest,
  MatrixResponse,
  CompetitorAccessRequest,
  CompetitorAccessResponse,
  ActivityNodeBoundsRequest,
  ActivityNodeBoundsResponse,
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

  // Check all API key configuration status
  checkKeys: async (): Promise<{
    keys: Record<string, boolean>;
    all_configured: boolean;
    configured_count: number;
    total_count: number;
  }> => {
    const { data } = await api.get('/analysis/check-keys/');
    return data;
  },

  // Get demographics data from ArcGIS
  getDemographics: async (request: DemographicsRequest): Promise<DemographicsResponse> => {
    const { data } = await api.post('/analysis/demographics/', request);
    return data;
  },

  // Get traffic counts data from Streetlight
  getTrafficCounts: async (request: TrafficCountsRequest): Promise<TrafficAnalysis> => {
    const { data } = await api.post('/analysis/traffic-counts/', request);
    return data;
  },

  // Estimate segment count (for quota planning)
  estimateTrafficSegments: async (request: {
    latitude: number;
    longitude: number;
    radius_miles?: number;
  }): Promise<SegmentCountEstimate> => {
    const { data } = await api.post('/analysis/traffic-counts/estimate/', request);
    return data;
  },

  // Get StreetLight API quota usage (non-billable)
  getTrafficQuotaUsage: async (): Promise<{
    total_quota: number;
    segments_used: number;
    segments_remaining: number;
    job_count: number;
  }> => {
    const { data } = await api.get('/analysis/traffic-counts/usage/');
    return data;
  },

  // Get parcel information from ReportAll
  getParcelInfo: async (request: ParcelRequest): Promise<ParcelInfo> => {
    const { data } = await api.post('/analysis/parcel/', request);
    return data;
  },

  // Search for commercial properties for sale (legacy - uses Tavily/AI)
  searchProperties: async (request: PropertySearchRequest): Promise<PropertySearchResult> => {
    const { data } = await api.post('/analysis/property-search/', request);
    return data;
  },

  // Search for properties by radius using ATTOM
  searchPropertiesATTOM: async (request: {
    latitude: number;
    longitude: number;
    radius_miles?: number;
    property_types?: string[];
    min_opportunity_score?: number;
    limit?: number;
  }): Promise<PropertySearchResult> => {
    const { data } = await api.post('/analysis/properties/search/', request);
    return data;
  },

  // Search for properties by map bounds using ATTOM
  searchPropertiesByBounds: async (request: {
    min_lat: number;
    max_lat: number;
    min_lng: number;
    max_lng: number;
    property_types?: string[];
    min_opportunity_score?: number;
    limit?: number;
  }): Promise<PropertySearchResult> => {
    const { data } = await api.post('/analysis/properties/search-bounds/', request);
    return data;
  },

  // ============================================
  // Matrix API (Drive-Time Analysis)
  // ============================================

  // Calculate travel time matrix between origins and destinations
  calculateMatrix: async (request: MatrixRequest): Promise<MatrixResponse> => {
    const { data } = await api.post('/analysis/matrix/', request);
    return data;
  },

  // Calculate matrix for large datasets with automatic batching
  calculateMatrixBatched: async (request: MatrixRequest): Promise<MatrixResponse> => {
    const { data } = await api.post('/analysis/matrix/batched/', request);
    return data;
  },

  // Analyze drive times from a site to nearby competitors
  analyzeCompetitorAccess: async (request: CompetitorAccessRequest): Promise<CompetitorAccessResponse> => {
    const { data } = await api.post('/analysis/competitor-access/', request);
    return data;
  },

  // Get Matrix API cache statistics
  getMatrixCacheStats: async (): Promise<{
    total_entries: number;
    valid_entries: number;
    expired_entries: number;
  }> => {
    const { data } = await api.get('/analysis/matrix/cache-stats/');
    return data;
  },

  // Clear Matrix API cache
  clearMatrixCache: async (): Promise<{ status: string; message: string }> => {
    const { data } = await api.post('/analysis/matrix/clear-cache/');
    return data;
  },

  // ============================================
  // Demographic Boundaries (Census Tracts & Counties Choropleth)
  // ============================================

  // Get boundaries with demographic data for choropleth visualization
  getDemographicBoundaries: async (request: {
    state: string;
    metric?: 'population' | 'income' | 'density';
    geography?: 'tract' | 'county';
  }): Promise<GeoJSON.FeatureCollection> => {
    const { data } = await api.get('/analysis/demographic-boundaries/', {
      params: {
        state: request.state,
        metric: request.metric || 'population',
        geography: request.geography || 'tract',
      },
    });
    return data;
  },

  // ============================================
  // Census TIGER Boundaries (Counties, Cities, ZIP Codes)
  // ============================================

  // Get county boundaries for a state
  getCountyBoundaries: async (state: string): Promise<GeoJSON.FeatureCollection> => {
    const { data } = await api.get('/analysis/boundaries/counties/', {
      params: { state },
    });
    return data;
  },

  // Get city/place boundaries for a state
  getCityBoundaries: async (state: string): Promise<GeoJSON.FeatureCollection> => {
    const { data } = await api.get('/analysis/boundaries/cities/', {
      params: { state },
    });
    return data;
  },

  // Get ZIP Code (ZCTA) boundaries for a state
  getZipCodeBoundaries: async (state: string): Promise<GeoJSON.FeatureCollection> => {
    const { data } = await api.get('/analysis/boundaries/zipcodes/', {
      params: { state },
    });
    return data;
  },
};

// ============================================
// Team Properties API (User-Contributed)
// ============================================

export const teamPropertiesApi = {
  // Create a new team property
  create: async (property: TeamPropertyCreate): Promise<TeamProperty> => {
    const { data } = await api.post('/team-properties/', property);
    return data;
  },

  // List all team properties with optional filters
  list: async (params?: {
    status?: string;
    state?: string;
    property_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<TeamPropertyListResponse> => {
    const { data } = await api.get('/team-properties/', { params });
    return data;
  },

  // Get a single team property by ID
  get: async (id: number): Promise<TeamProperty> => {
    const { data } = await api.get(`/team-properties/${id}`);
    return data;
  },

  // Update a team property
  update: async (id: number, updates: Partial<TeamPropertyCreate> & {
    status?: string;
    is_verified?: boolean;
  }): Promise<TeamProperty> => {
    const { data } = await api.put(`/team-properties/${id}`, updates);
    return data;
  },

  // Delete a team property
  delete: async (id: number): Promise<void> => {
    await api.delete(`/team-properties/${id}`);
  },

  // Get team properties within map bounds
  getInBounds: async (bounds: {
    min_lat: number;
    max_lat: number;
    min_lng: number;
    max_lng: number;
    status?: string;
  }): Promise<TeamPropertyListResponse> => {
    const { data } = await api.post('/team-properties/in-bounds/', bounds);
    return data;
  },
};

// ============================================
// Listings API (Scraped from Crexi/LoopNet)
// ============================================

export const listingsApi = {
  // Trigger a scrape of commercial listings
  triggerScrape: async (request: ScrapeRequest): Promise<ScrapeResponse> => {
    const { data } = await api.post('/listings/scrape', request);
    return data;
  },

  // Get the status of a scrape job
  getScrapeStatus: async (jobId: string): Promise<{
    city: string;
    state: string;
    sources: string[];
    status: string;
    started_at: string;
    results?: Record<string, number>;
    total_saved?: number;
    error?: string;
  }> => {
    const { data } = await api.get(`/listings/scrape/${jobId}`);
    return data;
  },

  // Search cached listings by city/state
  search: async (params: {
    city: string;
    state: string;
    source?: string;
    property_type?: string;
    min_price?: number;
    max_price?: number;
    limit?: number;
  }): Promise<ScrapedListingsResponse> => {
    const { data } = await api.get('/listings/search', { params });
    return data;
  },

  // Search cached listings by map bounds
  searchByBounds: async (params: {
    min_lat: number;
    max_lat: number;
    min_lng: number;
    max_lng: number;
    source?: string;
    property_type?: string;
    limit?: number;
  }): Promise<ScrapedListingsResponse> => {
    const { data } = await api.post('/listings/search-bounds', params);
    return data;
  },

  // Get configured sources status
  getSources: async (): Promise<ScrapedSourcesStatus> => {
    const { data } = await api.get('/listings/sources');
    return data;
  },

  // Deactivate a listing (mark as sold/removed)
  deactivate: async (listingId: number): Promise<{ message: string }> => {
    const { data } = await api.delete(`/listings/${listingId}`);
    return data;
  },

  // Get diagnostics for Crexi/Playwright status
  getDiagnostics: async (): Promise<{
    playwright: {
      available: boolean;
      error: string | null;
    };
    crexi: {
      automation_loaded: boolean;
      error: string | null;
      credentials: {
        username_set: boolean;
        password_set: boolean;
      };
    };
    loopnet: {
      credentials: {
        username_set: boolean;
        password_set: boolean;
      };
    };
    recommendations: string[];
  }> => {
    const { data } = await api.get('/listings/diagnostics');
    return data;
  },

  // Fetch Crexi listings for an area via automated CSV export
  fetchCrexiArea: async (request: {
    location: string;
    property_types?: string[];
    force_refresh?: boolean;
  }): Promise<{
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
  }> => {
    const { data } = await api.post('/listings/fetch-crexi-area', request);
    return data;
  },

  // Upload a Crexi CSV/Excel export for parsing and import
  uploadCrexiCSV: async (file: File): Promise<{
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
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/listings/upload-crexi-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    });
    return data;
  },
};

// ============================================
// Opportunities API (CSOKi-filtered ATTOM properties)
// ============================================

export const opportunitiesApi = {
  // Search for CSOKi-qualified property opportunities
  search: async (request: OpportunitySearchRequest): Promise<OpportunitySearchResponse> => {
    const { data } = await api.post('/opportunities/search', request);
    return data;
  },

  // Get opportunity statistics and metadata
  getStats: async (): Promise<{
    priority_order: Array<{
      rank: number;
      signal: string;
      description: string;
      points: number;
    }>;
    bonus_signals: Array<{
      signal: string;
      description: string;
      points: number;
    }>;
    criteria: {
      parcel_size: string;
      building_size: string;
      property_types: string[];
      excludes: string[];
    };
  }> => {
    const { data } = await api.get('/opportunities/stats');
    return data;
  },
};

// ============================================
// Activity Nodes API (Shopping/Entertainment/Dining heat map)
// ============================================

export const activityNodesApi = {
  // Get activity nodes within map viewport bounds
  getInBounds: async (request: ActivityNodeBoundsRequest): Promise<ActivityNodeBoundsResponse> => {
    const { data } = await api.post('/activity-nodes/within-bounds/', request);
    return data;
  },

  // Get import statistics
  getStats: async (): Promise<{
    total: number;
    by_category: Record<string, { total: number; by_state: Record<string, number> }>;
  }> => {
    const { data } = await api.get('/activity-nodes/stats/');
    return data;
  },
};

export default api;
