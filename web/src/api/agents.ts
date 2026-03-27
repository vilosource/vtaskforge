import { useQuery } from '@tanstack/react-query';
import { apiGet, PaginatedResponse } from './client';
import type { Task } from './tasks';

export interface AgentCurrentTask {
  id: string;
  title: string;
  status: string;
}

export interface Agent {
  id: string;
  name: string;
  tags: string[];
  status: string;
  effective_status: string;
  last_heartbeat: string | null;
  registered_at: string;
  created_at: string;
  updated_at: string;
  current_task: AgentCurrentTask | null;
  tasks_completed: number;
  tasks_failed: number;
}

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => apiGet<PaginatedResponse<Agent>>('/v1/agents/'),
  });
}

export function useAgent(agentId: string | undefined) {
  return useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => apiGet<Agent>(`/v1/agents/${agentId}/`),
    enabled: !!agentId,
  });
}

export function useAgentTasks(agentId: string | undefined) {
  return useQuery({
    queryKey: ['agent-tasks', agentId],
    queryFn: () => apiGet<PaginatedResponse<Task>>(`/v1/agents/${agentId}/tasks/`),
    enabled: !!agentId,
  });
}
