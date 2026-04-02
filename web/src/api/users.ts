import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, apiPatch, apiDelete } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserSummary {
  id: number;
  username: string;
  is_staff: boolean;
  is_active: boolean;
  user_type: string;
  date_joined: string;
  last_login: string | null;
}

export interface Membership {
  id: number;
  user_id: number;
  username: string;
  project_id: string;
  role: string;
  created_at: string;
}

export interface UserDetail extends UserSummary {
  memberships: Membership[];
}

export interface ExternalIdentity {
  id: number;
  provider: string;
  external_id: string;
  workspace_id: string;
  linked_at: string;
}

export interface SessionRecord {
  id: number;
  project_id: string;
  role: string;
  channel: string;
  started_at: string;
  ended_at: string | null;
  summary: string;
}

export interface AgentLock {
  id: number;
  project_id: string;
  role: string;
  user: string;
  session_id: string;
  created_at: string;
  last_activity: string;
}

export interface ChannelMapping {
  id: number;
  provider: string;
  channel_id: string;
  channel_name: string;
  project_id: string;
  created_at: string;
}

interface ListResponse<T> {
  results: T[];
}

// ---------------------------------------------------------------------------
// Admin: Users
// ---------------------------------------------------------------------------

export function useUsers(search?: string, userType?: string) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (userType) params.set('user_type', userType);
  const qs = params.toString();
  return useQuery({
    queryKey: ['admin', 'users', search, userType],
    queryFn: () => apiGet<ListResponse<UserSummary>>(`/v1/users/${qs ? `?${qs}` : ''}`),
  });
}

export function useUserDetail(id: number | string) {
  return useQuery({
    queryKey: ['admin', 'users', id],
    queryFn: () => apiGet<UserDetail>(`/v1/users/${id}/`),
    enabled: !!id,
  });
}

export function useUpdateUserType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, userType }: { id: number; userType: string }) =>
      apiPatch<UserDetail>(`/v1/users/${id}/`, { user_type: userType }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Admin: Locks
// ---------------------------------------------------------------------------

export function useLocks(projectId?: string) {
  const qs = projectId ? `?project_id=${projectId}` : '';
  return useQuery({
    queryKey: ['admin', 'locks', projectId],
    queryFn: () => apiGet<ListResponse<AgentLock>>(`/v1/locks/${qs}`),
  });
}

export function useReleaseLock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lockId: number) => apiDelete(`/v1/locks/${lockId}/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'locks'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Admin: Channel Mappings
// ---------------------------------------------------------------------------

export function useChannelMappings(provider?: string) {
  const qs = provider ? `?provider=${provider}` : '';
  return useQuery({
    queryKey: ['admin', 'channel-mappings', provider],
    queryFn: () => apiGet<ListResponse<ChannelMapping>>(`/v1/channel-mappings/${qs}`),
  });
}

export function useCreateMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { provider: string; channel_id: string; project_id: string; channel_name?: string }) =>
      apiPost<ChannelMapping>('/v1/channel-mappings/', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'channel-mappings'] });
    },
  });
}

export function useDeleteMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/v1/channel-mappings/${id}/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'channel-mappings'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Admin: Service Accounts
// ---------------------------------------------------------------------------

export function useCreateServiceAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiPost<{ id: number; username: string; token: string; user_type: string }>('/v1/service-accounts/', { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Self-service: External Identities
// ---------------------------------------------------------------------------

export function useExternalIdentities() {
  return useQuery({
    queryKey: ['profile', 'identities'],
    queryFn: () => apiGet<ListResponse<ExternalIdentity>>('/v1/external-identities/'),
  });
}

export function useLinkIdentity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { provider: string; external_id: string; workspace_id?: string }) =>
      apiPost<ExternalIdentity>('/v1/external-identities/', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile', 'identities'] });
    },
  });
}

export function useUnlinkIdentity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/v1/external-identities/${id}/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile', 'identities'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Self-service: Session History
// ---------------------------------------------------------------------------

export function useSessionHistory(project?: string) {
  const qs = project ? `?project=${project}` : '';
  return useQuery({
    queryKey: ['profile', 'sessions', project],
    queryFn: () => apiGet<ListResponse<SessionRecord>>(`/v1/profile/sessions/${qs}`),
  });
}
