export interface Store {
  id: number;
  brand: string;
  street: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface StoreListResponse {
  total: number;
  stores: Store[];
}

export interface StoreStats {
  brand: string;
  count: number;
  states: string[];
}

export type BrandKey =
  | 'csoki'
  | 'russell_cellular'
  | 'verizon_corporate'
  | 'victra'
  | 'tmobile'
  | 'uscellular';

export const BRAND_COLORS: Record<BrandKey, string> = {
  csoki: '#E31837',
  russell_cellular: '#FF6B00',
  verizon_corporate: '#CD040B',
  victra: '#000000',
  tmobile: '#E20074',
  uscellular: '#00A3E0',
};

export const BRAND_LABELS: Record<BrandKey, string> = {
  csoki: 'Cellular Sales (CSOKi)',
  russell_cellular: 'Russell Cellular',
  verizon_corporate: 'Verizon Corporate',
  victra: 'Victra',
  tmobile: 'T-Mobile',
  uscellular: 'US Cellular',
};

// Brand logos - paths relative to /public folder
export const BRAND_LOGOS: Record<BrandKey, string> = {
  csoki: '/logos/csoki.jpg',
  russell_cellular: '/logos/russellcellular.jpg',
  verizon_corporate: '/logos/verizon.png',
  victra: '/logos/victra.jpeg',
  tmobile: '/logos/tmobile.png',
  uscellular: '/logos/uscellular.jpg',
};

// Trade Area Analysis Types
export type POICategory =
  | 'anchors'
  | 'quick_service'
  | 'restaurants'
  | 'retail'
  | 'entertainment'
  | 'services';

export interface POI {
  place_id: string;
  name: string;
  category: POICategory;
  types: string[];
  latitude: number;
  longitude: number;
  address: string | null;
  rating: number | null;
  user_ratings_total: number | null;
}

export interface TradeAreaAnalysis {
  center_latitude: number;
  center_longitude: number;
  radius_meters: number;
  pois: POI[];
  summary: Record<string, number>;  // Flexible for any category
}

export interface TradeAreaRequest {
  latitude: number;
  longitude: number;
  radius_miles: number;
}

export const POI_CATEGORY_COLORS: Record<POICategory, string> = {
  anchors: '#8B5CF6',       // Purple
  quick_service: '#F59E0B', // Amber
  restaurants: '#10B981',   // Emerald
  retail: '#3B82F6',        // Blue
  entertainment: '#EC4899', // Pink
  services: '#6366F1',      // Indigo
};

export const POI_CATEGORY_LABELS: Record<POICategory, string> = {
  anchors: 'Anchor Stores',
  quick_service: 'Quick Service',
  restaurants: 'Restaurants',
  retail: 'Retail',
  entertainment: 'Entertainment',
  services: 'Services',
};

// Demographics Types (ArcGIS GeoEnrichment)
export interface DemographicMetrics {
  radius_miles: number;

  // Population
  total_population: number | null;
  total_households: number | null;
  population_density: number | null;
  median_age: number | null;

  // Income
  median_household_income: number | null;
  average_household_income: number | null;
  per_capita_income: number | null;

  // Employment
  total_businesses: number | null;
  total_employees: number | null;

  // Consumer Spending
  spending_food_away: number | null;
  spending_apparel: number | null;
  spending_entertainment: number | null;
  spending_retail_total: number | null;
}

export interface DemographicsResponse {
  latitude: number;
  longitude: number;
  radii: DemographicMetrics[];
  data_vintage: string;
  census_supplemented?: boolean;
}

export interface DemographicsRequest {
  latitude: number;
  longitude: number;
}

// Nearest Competitors Types
export interface NearestCompetitor {
  brand: string;
  distance_miles: number;
  store: Store;
}

export interface NearestCompetitorsResponse {
  latitude: number;
  longitude: number;
  competitors: NearestCompetitor[];
}

export interface NearestCompetitorsRequest {
  latitude: number;
  longitude: number;
}

// Traffic Counts Types (Streetlight Advanced Traffic Counts API)
export interface IncomeBreakdown {
  under_15k: number | null;
  income_15k_25k: number | null;
  income_25k_35k: number | null;
  income_35k_50k: number | null;
  income_50k_75k: number | null;
  income_75k_100k: number | null;
  income_100k_150k: number | null;
  income_150k_200k: number | null;
  over_200k: number | null;
}

export interface TripPurposeBreakdown {
  hbw: number | null;  // Home-Based Work
  hbo: number | null;  // Home-Based Other
  nhbw: number | null; // Non-Home-Based Work
  wbo: number | null;  // Work-Based Other
}

export interface VehicleClassBreakdown {
  sedan: number | null;
  suv: number | null;
  truck: number | null;
  pickup: number | null;
  minivan: number | null;
  hatchback: number | null;
  coupe: number | null;
  cuv: number | null;
  other: number | null;
}

export interface PowerTrainBreakdown {
  ev: number | null;     // Electric Vehicle
  hybrid: number | null;
  ice: number | null;    // Internal Combustion Engine
  other: number | null;
}

export interface TrafficAnalysis {
  latitude: number;
  longitude: number;
  radius_miles: number;

  // Volume metrics
  total_segments: number;
  total_daily_traffic: number | null;
  avg_segment_volume: number | null;
  total_vmt: number | null;

  // Speed metrics
  avg_speed: number | null;
  avg_free_flow_speed: number | null;

  // Traveler demographics
  income_breakdown: IncomeBreakdown | null;
  trip_purpose_breakdown: TripPurposeBreakdown | null;

  // Vehicle attributes
  vehicle_class_breakdown: VehicleClassBreakdown | null;
  power_train_breakdown: PowerTrainBreakdown | null;

  // Metadata
  data_source: string;
  date_range: string | null;
  segments_queried: number;
}

export interface TrafficCountsRequest {
  latitude: number;
  longitude: number;
  radius_miles?: number;
  include_demographics?: boolean;
  include_vehicle_attributes?: boolean;
  year?: number;
  month?: number;
}

export interface SegmentCountEstimate {
  segment_count: number;
  geometry_type: string;
}

// Saved Location for Compare feature
export interface SavedLocation {
  id: string;
  name: string;
  brand?: string;  // Brand key (e.g., 'csoki', 'tmobile')
  city?: string;
  state?: string;
  latitude: number;
  longitude: number;
  savedAt: Date;
  demographics?: DemographicsResponse;
}

// Parcel Info Types (ReportAll API)
export interface ParcelInfo {
  parcel_id: string | null;
  owner: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  acreage: number | null;
  land_value: number | null;
  building_value: number | null;
  total_value: number | null;
  land_use: string | null;
  zoning: string | null;
  year_built: number | null;
  building_sqft: number | null;
  sale_price: number | null;
  sale_date: string | null;
  latitude: number;
  longitude: number;
  geometry: string | null;  // WKT geometry for boundary highlighting
  raw_data?: Record<string, unknown>;
}

export interface ParcelRequest {
  latitude: number;
  longitude: number;
}

// Property Search Types (ATTOM-powered property intelligence)
export type PropertyType = 'retail' | 'land' | 'office' | 'industrial' | 'mixed_use' | 'unknown';

export type PropertySource = 'attom' | 'reportall' | 'quantumlisting' | 'team_contributed';

export interface OpportunitySignal {
  signal_type: string;  // e.g., "tax_delinquent", "owner_age", "vacancy", "distress"
  description: string;
  strength: 'high' | 'medium' | 'low';
}

export interface PropertyListing {
  id: string;
  address: string;
  city: string;
  state: string;
  zip_code: string | null;
  latitude: number;
  longitude: number;

  // Listing details
  property_type: PropertyType;
  price: number | null;
  price_display: string | null;  // Formatted price string (e.g., "$1.2M")
  sqft: number | null;
  lot_size_acres: number | null;
  year_built: number | null;

  // Ownership
  owner_name: string | null;
  owner_type: string | null;  // "individual", "corporate", "trust", etc.

  // Valuation
  assessed_value: number | null;
  market_value: number | null;

  // Transaction history
  last_sale_date: string | null;
  last_sale_price: number | null;

  // Source and status
  source: PropertySource;
  listing_type: 'active_listing' | 'opportunity';  // opportunity = likely to sell soon

  // Opportunity signals (for predictive properties)
  opportunity_signals: OpportunitySignal[];
  opportunity_score: number | null;  // 0-100 score

  // External links
  external_url: string | null;

  // Legacy fields for backwards compatibility
  price_numeric?: number | null;
  sqft_numeric?: number | null;
  url?: string | null;
  description?: string | null;
  listing_date?: string | null;
}

// External search link for link-out strategy
export interface ExternalSearchLink {
  name: string;  // Display name (e.g., "Crexi", "LoopNet")
  url: string;   // Pre-filled search URL
  icon: string;  // Icon identifier
}

export interface PropertySearchLinks {
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  links: ExternalSearchLink[];
}

export interface PropertySearchResult {
  center_latitude: number;
  center_longitude: number;
  radius_miles: number;
  properties: PropertyListing[];
  total_found: number;
  sources: string[];
  search_timestamp: string;
  // Legacy fields for backwards compatibility
  search_query?: string;
  listings?: PropertyListing[];
  sources_searched?: string[];
  external_links?: PropertySearchLinks;
}

export interface MapBounds {
  min_lat: number;
  max_lat: number;
  min_lng: number;
  max_lng: number;
}

export interface PropertySearchRequest {
  latitude: number;
  longitude: number;
  radius_miles?: number;
  property_types?: PropertyType[];
  bounds?: MapBounds;  // Map viewport bounds for precise filtering
}

// Property type colors for map markers
export const PROPERTY_TYPE_COLORS: Record<PropertyType, string> = {
  retail: '#22C55E',      // Green
  land: '#A16207',        // Amber/Brown
  office: '#3B82F6',      // Blue
  industrial: '#6B7280',  // Gray
  mixed_use: '#8B5CF6',   // Purple
  unknown: '#9CA3AF',     // Light Gray
};

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  retail: 'Retail',
  land: 'Land',
  office: 'Office',
  industrial: 'Industrial',
  mixed_use: 'Mixed Use',
  unknown: 'Unknown',
};

// Source icons/colors for property listings
export const PROPERTY_SOURCE_COLORS: Record<string, string> = {
  crexi: '#1E3A8A',       // Dark Blue
  loopnet: '#DC2626',     // Red
  zillow: '#006AFF',      // Zillow Blue
  default: '#6B7280',     // Gray
};

// =============================================================================
// Team Properties (User-Contributed)
// =============================================================================

export type TeamPropertySourceType = 'for_sale_sign' | 'broker' | 'word_of_mouth' | 'other';

export type TeamPropertyStatus = 'active' | 'reviewed' | 'archived' | 'sold';

export interface TeamProperty {
  id: number;
  address: string;
  city: string;
  state: string;
  postal_code: string | null;
  latitude: number;
  longitude: number;
  property_type: PropertyType;
  price: number | null;
  sqft: number | null;
  lot_size_acres: number | null;
  listing_url: string | null;
  source_type: TeamPropertySourceType | null;
  notes: string | null;
  contributor_name: string | null;
  contributor_email: string | null;
  status: TeamPropertyStatus;
  is_verified: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface TeamPropertyCreate {
  address: string;
  city: string;
  state: string;
  postal_code?: string;
  latitude: number;
  longitude: number;
  property_type?: string;
  price?: number;
  sqft?: number;
  lot_size_acres?: number;
  listing_url?: string;
  source_type?: string;
  notes?: string;
  contributor_name?: string;
  contributor_email?: string;
}

export interface TeamPropertyListResponse {
  total: number;
  properties: TeamProperty[];
}

// Team property marker color (orange pin)
export const TEAM_PROPERTY_COLOR = '#F97316';

// Source type labels
export const TEAM_PROPERTY_SOURCE_LABELS: Record<TeamPropertySourceType, string> = {
  for_sale_sign: 'For Sale Sign',
  broker: 'Broker Contact',
  word_of_mouth: 'Word of Mouth',
  other: 'Other',
};

// =============================================================================
// Scraped Listings (from Crexi/LoopNet via browser automation)
// =============================================================================

export interface ScrapedListing {
  id: number;
  source: 'crexi' | 'loopnet';
  external_id: string | null;
  listing_url: string | null;
  address: string | null;
  city: string;
  state: string;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  property_type: PropertyType | null;
  price: number | null;
  price_display: string | null;
  sqft: number | null;
  lot_size_acres: number | null;
  title: string | null;
  broker_name: string | null;
  broker_company: string | null;
  images: string[] | null;
  scraped_at: string;
}

export interface ScrapeRequest {
  city: string;
  state: string;
  sources?: ('crexi' | 'loopnet')[];
  property_types?: string[];
  force_refresh?: boolean;
}

export interface ScrapeResponse {
  job_id: string;
  status: 'started' | 'running' | 'completed' | 'failed';
  message: string;
}

export interface ScrapedListingsResponse {
  total: number;
  listings: ScrapedListing[];
  sources: string[];
  cached: boolean;
  cache_age_minutes: number | null;
}

export interface ScrapedSourcesStatus {
  crexi: {
    configured: boolean;
    username_set: boolean;
  };
  loopnet: {
    configured: boolean;
    username_set: boolean;
  };
}

// Scraped listing marker color (blue for active listings)
export const SCRAPED_LISTING_COLOR = '#3B82F6';

// =============================================================================
// Opportunities (ATTOM-based CSOKi property filtering)
// =============================================================================

export interface OpportunityRanking {
  property: PropertyListing;
  rank: number;  // 1-based ranking (1 = highest priority)
  priority_signals: string[];  // Which high-priority signals are present
  signal_count: number;  // Total number of signals
}

export interface OpportunitySearchRequest {
  min_lat: number;
  max_lat: number;
  min_lng: number;
  max_lng: number;
  
  // Optional overrides for parcel/building size
  min_parcel_acres?: number;
  max_parcel_acres?: number;
  min_building_sqft?: number;
  max_building_sqft?: number;
  
  // Property type preferences
  include_retail?: boolean;
  include_office?: boolean;
  include_land?: boolean;
  
  // Opportunity signal filtering
  require_opportunity_signal?: boolean;
  min_opportunity_score?: number;
  
  limit?: number;
}

export interface OpportunitySearchResponse {
  center_latitude: number;
  center_longitude: number;
  total_found: number;
  opportunities: OpportunityRanking[];
  search_timestamp: string;
  filters_applied: {
    parcel_size_acres: string;
    building_size_sqft: string;
    property_types: string[];
    min_opportunity_score: number;
  };
}

// Opportunity marker color (distinct from properties)
export const OPPORTUNITY_COLOR = '#9333EA';  // Purple

// =============================================================================
// Matrix API Types (Drive-Time Analysis)
// =============================================================================

export type TravelProfile = 'driving' | 'driving-traffic' | 'walking' | 'cycling';

export interface MatrixElement {
  origin_index: number;
  destination_index: number;
  duration_seconds: number | null;
  distance_meters: number | null;
}

export interface MatrixRequest {
  origins: [number, number][];  // [lng, lat][]
  destinations: [number, number][];  // [lng, lat][]
  profile?: TravelProfile;
}

export interface MatrixResponse {
  elements: MatrixElement[];
  profile: string;
  total_origins: number;
  total_destinations: number;
  cached: boolean;
  timestamp: string;
}

export interface CompetitorAccessRequest {
  site_latitude: number;
  site_longitude: number;
  competitor_ids?: number[];
  max_competitors?: number;
  profile?: TravelProfile;
}

export interface CompetitorWithTravelTime extends Store {
  travel_time_seconds: number | null;
  travel_time_minutes: number | null;
  distance_meters: number | null;
  distance_miles: number | null;
}

export interface CompetitorAccessResponse {
  site_latitude: number;
  site_longitude: number;
  competitors: CompetitorWithTravelTime[];
  profile: string;
  analysis_timestamp: string;
}
