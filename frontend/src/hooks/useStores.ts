import { useQuery } from '@tanstack/react-query';
import { storeApi } from '../services/api';
import type { StoreListResponse, StoreStats } from '../types/store';

export function useStores(params?: {
  brand?: string;
  state?: string;
  city?: string;
  limit?: number;
}) {
  return useQuery<StoreListResponse>({
    queryKey: ['stores', params],
    queryFn: () => storeApi.getStores(params),
  });
}

export function useStoresByState(state: string, brand?: string) {
  return useQuery<StoreListResponse>({
    queryKey: ['stores', 'state', state, brand],
    queryFn: () => storeApi.getStoresByState(state, brand),
    enabled: !!state,
  });
}

export function useBrands() {
  return useQuery<string[]>({
    queryKey: ['brands'],
    queryFn: storeApi.getBrands,
  });
}

export function useStoreStats() {
  return useQuery<StoreStats[]>({
    queryKey: ['stats'],
    queryFn: storeApi.getStats,
  });
}
