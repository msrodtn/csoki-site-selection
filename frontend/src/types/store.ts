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
