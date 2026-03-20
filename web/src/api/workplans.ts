import { useQuery } from '@tanstack/react-query';
import { apiGet, PaginatedResponse } from './client';

export interface Workplan {
  id: string;
  name: string;
  description: string;
  status: string;
  tags: string[];
  created_at: string;
}

export interface WorkplanStats {
  total_tasks: number;
  by_status: Record<string, number>;
  completed_percentage: number;
}

export function useWorkplans() {
  return useQuery({
    queryKey: ['workplans'],
    queryFn: () => apiGet<PaginatedResponse<Workplan>>('/v1/workplans/'),
  });
}

export function useWorkplanStats(workplanId: string) {
  return useQuery({
    queryKey: ['workplan-stats', workplanId],
    queryFn: () => apiGet<WorkplanStats>(`/v1/workplans/${workplanId}/stats/`),
    enabled: !!workplanId,
  });
}
