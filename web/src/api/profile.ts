import { useQuery } from '@tanstack/react-query';
import { apiGet } from './client';

export interface RecentAccessItem {
  resource_type: 'project' | 'workplan' | 'task';
  resource_id: string;
  resource_title: string;
  resource_status: string;
  accessed_at: string;
}

interface RecentAccessResponse {
  results: RecentAccessItem[];
}

export function useRecentAccess() {
  return useQuery({
    queryKey: ['profile', 'recent'],
    queryFn: () => apiGet<RecentAccessResponse>('/v1/profile/recent/'),
    staleTime: 30_000,
  });
}
