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
