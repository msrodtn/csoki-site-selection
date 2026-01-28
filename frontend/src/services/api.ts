import axios from 'axios';
import type { StoreListResponse, StoreStats } from '../types/store';

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
    const { data } = await api.get('/locations', { params });
    return data;
  },

  // Get stores by state
  getStoresByState: async (
    state: string,
    brand?: string
  ): Promise<StoreListResponse> => {
    const { data } = await api.get(`/locations/state/${state}`, {
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
    const { data } = await api.post('/locations/within-bounds', bounds);
    return data;
  },

  // Get stores within radius
  getStoresInRadius: async (params: {
    latitude: number;
    longitude: number;
    radius_miles: number;
    brands?: string[];
  }): Promise<StoreListResponse> => {
    const { data } = await api.post('/locations/within-radius', params);
    return data;
  },

  // Get all brand names
  getBrands: async (): Promise<string[]> => {
    const { data } = await api.get('/locations/brands');
    return data;
  },

  // Get statistics
  getStats: async (): Promise<StoreStats[]> => {
    const { data } = await api.get('/locations/stats');
    return data;
  },
};

export default api;
