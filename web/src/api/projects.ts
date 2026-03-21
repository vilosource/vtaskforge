import { useQuery } from '@tanstack/react-query';
import { apiGet, apiGetPaginated, PaginatedResponse } from './client';

export interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  repo_url: string | null;
  default_branch: string;
  tags: string[];
  owner: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectStats {
  project_id: string;
  total_tasks: number;
  backlog_tasks: number;
  workplan_tasks: number;
  by_status: Record<string, number>;
  completed_percentage: number;
  workplans: {
    active: number;
    completed: number;
    archived: number;
  };
}

export interface ProjectWorkplan {
  id: string;
  name: string;
  description: string;
  status: string;
  tags: string[];
  created_at: string;
  total_tasks: number;
  completed_percentage: number;
}

export interface BacklogTask {
  id: string;
  title: string;
  status: string;
  labels: string[];
  created_at: string;
}

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => apiGet<PaginatedResponse<Project>>('/v1/projects/'),
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project', projectId],
    queryFn: () => apiGet<Project>(`/v1/projects/${projectId}/`),
    enabled: !!projectId,
  });
}

export function useProjectStats(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-stats', projectId],
    queryFn: () => apiGet<ProjectStats>(`/v1/projects/${projectId}/stats/`),
    enabled: !!projectId,
  });
}

export function useProjectWorkplans(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-workplans', projectId],
    queryFn: () => apiGetPaginated<ProjectWorkplan>(`/v1/projects/${projectId}/workplans/`),
    enabled: !!projectId,
  });
}

export function useProjectBacklog(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-backlog', projectId],
    queryFn: () => apiGetPaginated<BacklogTask>(`/v1/projects/${projectId}/backlog/`),
    enabled: !!projectId,
  });
}