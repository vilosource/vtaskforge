import { useQuery } from '@tanstack/react-query';
import { apiGet, PaginatedResponse } from './client';
import type { Workplan } from './workplans';

export interface Task {
  id: string;
  title: string;
  status: string;
  milestone: string;
  workplan: string;
  project: string;
  labels: string[];
  claimed_by: string | null;
  claimed_at: string | null;
  assigned_to: string | null;
  requires: string[];
  description: string;
  acceptance_criteria: string[];
  notes: string[];
  spec: string;
  agent_model: string;
  test_command: Record<string, string>;
  judge: boolean;
  isolation: string;
  created_at: string;
  updated_at: string;
}

export interface TaskEvent {
  id: string;
  event_type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface TaskReview {
  id: string;
  decision: string;
  reason: string | null;
  reviewer_id: string;
  reviewer_type: string;
  created_at: string;
}

export interface TaskNote {
  id: string;
  text: string;
  actor_id: string;
  created_at: string;
}

export interface TaskLink {
  id: string;
  source_type: string;
  source_id: string;
  source_title: string | null;
  target_type: string;
  target_id: string;
  target_title: string | null;
  link_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export function useDownstreamLinks(taskId: string | null) {
  return useQuery({
    queryKey: ['links', 'downstream', taskId],
    queryFn: () => apiGet<{ results: TaskLink[] }>(`/v1/links/?target_id=${taskId}&link_type=depends_on`),
    enabled: !!taskId,
  });
}

export interface TaskDetail extends Omit<Task, 'notes'> {
  links: TaskLink[];
  reviews: TaskReview[];
  events: TaskEvent[];
  notes: TaskNote[];
}

export function useTasksByWorkplan(workplanId: string) {
  return useQuery({
    queryKey: ['tasks', 'workplan', workplanId],
    queryFn: () => apiGet<PaginatedResponse<Task>>(`/v1/tasks/?workplan=${workplanId}`),
    enabled: !!workplanId,
  });
}

export function useTasksByMilestone(milestoneId: string) {
  return useQuery({
    queryKey: ['tasks', 'milestone', milestoneId],
    queryFn: () => apiGet<PaginatedResponse<Task>>(`/v1/tasks/?milestone=${milestoneId}`),
    enabled: !!milestoneId,
  });
}

export function useBacklogTasks(projectId: string) {
  return useQuery({
    queryKey: ['tasks', 'backlog', projectId],
    queryFn: () => apiGet<PaginatedResponse<Task>>(`/v1/tasks/?project=${projectId}&workplan__isnull=true`),
    enabled: !!projectId,
  });
}

export function useOrphanTasks(workplanId: string) {
  return useQuery({
    queryKey: ['tasks', 'orphan', workplanId],
    queryFn: () =>
      apiGet<PaginatedResponse<Task>>(`/v1/tasks/?workplan=${workplanId}&milestone__isnull=true`),
    enabled: !!workplanId,
  });
}

export function useTaskDetail(taskId: string | null) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () =>
      apiGet<TaskDetail>(`/v1/tasks/${taskId}/?expand=links,reviews,events`),
    enabled: !!taskId,
  });
}

export function useWorkplan(id: string) {
  return useQuery({
    queryKey: ['workplans', id],
    queryFn: () => apiGet<Workplan>(`/v1/workplans/${id}`),
    enabled: !!id,
  });
}
