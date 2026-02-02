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
export type POICategory = 'anchors' | 'quick_service' | 'restaurants' | 'retail';

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
  summary: Record<POICategory, number>;
}

export interface TradeAreaRequest {
  latitude: number;
  longitude: number;
  radius_miles: number;
}

export const POI_CATEGORY_COLORS: Record<POICategory, string> = {
  anchors: '#8B5CF6',      // Purple
  quick_service: '#F59E0B', // Amber
  restaurants: '#10B981',   // Emerald
  retail: '#3B82F6',        // Blue
};

export const POI_CATEGORY_LABELS: Record<POICategory, string> = {
  anchors: 'Anchor Stores',
  quick_service: 'Quick Service',
  restaurants: 'Restaurants',
  retail: 'Retail',
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

// Property Search Types (AI-powered CRE listings)
export type PropertyType = 'retail' | 'land' | 'office' | 'industrial' | 'mixed_use';

export interface PropertyListing {
  id: string;
  address: string;
  city: string;
  state: string;
  price: string | null;
  price_numeric: number | null;
  sqft: string | null;
  sqft_numeric: number | null;
  property_type: PropertyType;
  source: string;  // crexi, loopnet, zillow, etc.
  url: string | null;
  latitude: number | null;
  longitude: number | null;
  description: string | null;
  listing_date: string | null;
}

export interface PropertySearchResult {
  center_latitude: number;
  center_longitude: number;
  radius_miles: number;
  search_query: string;
  listings: PropertyListing[];
  sources_searched: string[];
  total_found: number;
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
};

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  retail: 'Retail',
  land: 'Land',
  office: 'Office',
  industrial: 'Industrial',
  mixed_use: 'Mixed Use',
};

// Source icons/colors for property listings
export const PROPERTY_SOURCE_COLORS: Record<string, string> = {
  crexi: '#1E3A8A',       // Dark Blue
  loopnet: '#DC2626',     // Red
  zillow: '#006AFF',      // Zillow Blue
  default: '#6B7280',     // Gray
};
