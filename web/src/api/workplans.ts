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

export function useWorkplans() {
  return useQuery({
    queryKey: ['workplans'],
    queryFn: () => apiGet<PaginatedResponse<Workplan>>('/v1/workplans/'),
  });
}
