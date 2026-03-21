import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiGetPaginated, apiPost } from './client';

export interface Milestone {
  id: string;
  name: string;
  description: string;
  workplan: string;
  status: 'pending' | 'active' | 'completed';
  order: number;
  created_at: string;
}

export interface MilestoneStats {
  milestone_id: string;
  total_tasks: number;
  by_status: Record<string, number>;
  completed_percentage: number;
}

export function useMilestones(workplanId: string) {
  return useQuery({
    queryKey: ['milestones', workplanId],
    queryFn: () => apiGetPaginated<Milestone>(`/v1/workplans/${workplanId}/milestones/`),
    enabled: !!workplanId,
  });
}

export function useMilestone(milestoneId: string | undefined) {
  return useQuery({
    queryKey: ['milestone', milestoneId],
    queryFn: () => apiGet<Milestone>(`/v1/milestones/${milestoneId}/`),
    enabled: !!milestoneId,
  });
}

export function useMilestoneStats(milestoneId: string) {
  return useQuery({
    queryKey: ['milestone-stats', milestoneId],
    queryFn: async () => {
      const res = await fetch(`/v1/milestones/${milestoneId}/stats/`, {
        credentials: 'include',
        headers: {
          ...(localStorage.getItem('vtf_token')
            ? { Authorization: `Token ${localStorage.getItem('vtf_token')}` }
            : {}),
        },
      });
      return res.json() as Promise<MilestoneStats>;
    },
    enabled: !!milestoneId,
  });
}

export function useActivateMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (milestoneId: string) => apiPost<Milestone>(`/v1/milestones/${milestoneId}/activate/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestones'] });
    },
  });
}

export function useCompleteMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (milestoneId: string) => apiPost<Milestone>(`/v1/milestones/${milestoneId}/complete/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestones'] });
    },
  });
}
