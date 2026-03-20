import { useQuery } from '@tanstack/react-query';
import { apiGet, PaginatedResponse } from './client';
import type { Workplan } from './workplans';

export interface Task {
  id: string;
  title: string;
  status: string;
  phase_id: string;
  workplan_id: string;
  claimed_by: string | null;
  claimed_at: string | null;
  assigned_to: string | null;
  requires: string[];
  description: string;
  acceptance_criteria: string[];
  notes: string[];
  created_at: string;
  updated_at: string;
}

export function useTasksByWorkplan(workplanId: string) {
  return useQuery({
    queryKey: ['tasks', 'workplan', workplanId],
    queryFn: () => apiGet<PaginatedResponse<Task>>(`/v1/tasks/?workplan=${workplanId}`),
    enabled: !!workplanId,
  });
}

export function useWorkplan(id: string) {
  return useQuery({
    queryKey: ['workplans', id],
    queryFn: () => apiGet<Workplan>(`/v1/workplans/${id}`),
    enabled: !!id,
  });
}
