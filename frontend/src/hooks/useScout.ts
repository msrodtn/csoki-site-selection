import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scoutApi } from '../services/api';
import type { ScoutDecisionCreate } from '../types/store';

export function useScoutStats() {
  return useQuery({
    queryKey: ['scout', 'stats'],
    queryFn: () => scoutApi.getStats(),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useScoutJobs(params?: { status?: string; market?: string }) {
  return useQuery({
    queryKey: ['scout', 'jobs', params],
    queryFn: () => scoutApi.listJobs(params),
    staleTime: 10_000,
    retry: 1,
    placeholderData: [],
  });
}

export function useScoutJob(jobId: string) {
  return useQuery({
    queryKey: ['scout', 'jobs', jobId],
    queryFn: () => scoutApi.getJob(jobId),
    enabled: !!jobId,
  });
}

export function useScoutReports(params?: {
  job_id?: string;
  min_confidence?: number;
  market?: string;
}) {
  return useQuery({
    queryKey: ['scout', 'reports', params],
    queryFn: () => scoutApi.listReports(params),
    staleTime: 10_000,
    retry: 1,
    placeholderData: [],
  });
}

export function useScoutReport(reportId: string) {
  return useQuery({
    queryKey: ['scout', 'reports', reportId],
    queryFn: () => scoutApi.getReport(reportId),
    enabled: !!reportId,
  });
}

export function useScoutDecisions(params?: {
  report_id?: string;
  decision?: string;
}) {
  return useQuery({
    queryKey: ['scout', 'decisions', params],
    queryFn: () => scoutApi.listDecisions(params),
    staleTime: 10_000,
    retry: 1,
    placeholderData: [],
  });
}

export function useSubmitDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (decision: ScoutDecisionCreate) => scoutApi.submitDecision(decision),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scout'] });
    },
  });
}
