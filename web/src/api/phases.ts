import { useQuery } from '@tanstack/react-query';
import { apiGetPaginated } from './client';

export interface Phase {
  id: string;
  name: string;
  description: string;
  workplan: string;
  status: 'pending' | 'active' | 'completed';
  order: number;
  created_at: string;
}

export interface PhaseStats {
  phase_id: string;
  total_tasks: number;
  by_status: Record<string, number>;
  completed_percentage: number;
}

export function usePhases(workplanId: string) {
  return useQuery({
    queryKey: ['phases', workplanId],
    queryFn: () => apiGetPaginated<Phase>(`/v1/workplans/${workplanId}/phases/`),
    enabled: !!workplanId,
  });
}

export function usePhaseStats(phaseId: string) {
  return useQuery({
    queryKey: ['phase-stats', phaseId],
    queryFn: async () => {
      const res = await fetch(`/v1/phases/${phaseId}/stats/`, {
        credentials: 'include',
        headers: {
          ...(localStorage.getItem('vtf_token')
            ? { Authorization: `Token ${localStorage.getItem('vtf_token')}` }
            : {}),
        },
      });
      return res.json() as Promise<PhaseStats>;
    },
    enabled: !!phaseId,
  });
}
