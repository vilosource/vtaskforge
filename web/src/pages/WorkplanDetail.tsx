import { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useWorkplan, useOrphanTasks } from '../api/tasks';
import type { Task } from '../api/tasks';
import { useWorkplanStats } from '../api/workplans';
import { useProject } from '../api/projects';
import { useMilestones, useMilestoneStats, useActivateMilestone, useCompleteMilestone } from '../api/milestones';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';
import { MilestonePipeline } from '../components/MilestonePipeline';
import { Breadcrumb } from '../components/Breadcrumb';
import { useSetActiveProject } from '../contexts/ActiveProjectContext';
import { TaskDetail } from '../components/TaskDetail';
import { TaskListTable, BACKLOG_COLUMNS } from '../components/TaskListTable';

const BORDER_COLORS: Record<string, string> = {
  completed: 'border-l-tertiary',
  active: 'border-l-primary',
  pending: 'border-l-outline-variant',
};

function MilestoneCard({ milestone, projectId, workplanId }: { milestone: { id: string; name: string; description: string; status: string }; projectId: string; workplanId: string }) {
  const { data: stats } = useMilestoneStats(milestone.id);
  const activateMutation = useActivateMilestone();
  const completeMutation = useCompleteMilestone();
  const total = stats?.total_tasks ?? 0;
  const done = stats?.by_status?.done ?? 0;
  const pct = stats?.completed_percentage ?? 0;

  const statusColor = milestone.status === 'completed' ? 'bg-tertiary'
    : milestone.status === 'active' ? 'bg-primary'
    : 'bg-outline-variant';

  return (
    <Link
      to={`/projects/${projectId}/workplans/${workplanId}/milestones/${milestone.id}`}
      className={`block bg-surface-container-lowest rounded-xl shadow-sm border-l-[3px] ${BORDER_COLORS[milestone.status] ?? 'border-l-outline-variant'} p-4 hover:shadow-md transition-shadow no-underline`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="text-sm font-headline font-bold text-on-surface truncate">{milestone.name}</div>
        <span
          className={`inline-flex items-center text-[11px] font-semibold leading-none px-2 py-1 rounded-full whitespace-nowrap uppercase tracking-wide ${
            milestone.status === 'completed' ? 'bg-tertiary-container text-on-tertiary-container' :
            milestone.status === 'active' ? 'bg-blue-100 text-blue-700' :
            'bg-surface-container-highest text-on-surface-variant'
          }`}
        >
          {milestone.status}
        </span>
      </div>
      {milestone.description && (
        <div className="text-xs text-on-surface-variant mb-3 line-clamp-2">{milestone.description}</div>
      )}
      <div className="flex items-center gap-3 text-xs text-on-surface-variant">
        <span>{total} tasks &middot; {done} done</span>
        <div className="flex items-center gap-2 flex-1">
          <div className="flex-1 h-1.5 rounded-full bg-surface-container-high overflow-hidden">
            <div className={`h-full rounded-full ${statusColor} transition-all`} style={{ width: `${pct}%` }} />
          </div>
          <span className="text-[11px] font-semibold text-on-surface-variant">{pct}%</span>
        </div>
        {milestone.status === 'pending' && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); activateMutation.mutate(milestone.id); }}
            disabled={activateMutation.isPending}
            className="primary-gradient text-on-primary rounded-full px-3 py-1 text-xs font-semibold min-h-[28px] border-0 cursor-pointer disabled:opacity-55 disabled:cursor-not-allowed"
          >
            {activateMutation.isPending ? 'Activating...' : 'Activate'}
          </button>
        )}
        {milestone.status === 'active' && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); completeMutation.mutate(milestone.id); }}
            disabled={completeMutation.isPending}
            className="bg-tertiary text-on-tertiary rounded-full px-3 py-1 text-xs font-semibold min-h-[28px] border-0 cursor-pointer disabled:opacity-55 disabled:cursor-not-allowed"
          >
            {completeMutation.isPending ? 'Completing...' : 'Complete'}
          </button>
        )}
      </div>
    </Link>
  );
}

function MilestoneGroup({ title, milestones, projectId, workplanId, defaultCollapsed = false }: {
  title: string;
  milestones: { id: string; name: string; description: string; status: string }[];
  projectId: string;
  workplanId: string;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (milestones.length === 0) return null;

  return (
    <div className="mb-6">
      <button
        className="flex items-center gap-2 w-full bg-transparent border-0 cursor-pointer py-2 px-0 text-left"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          width="12" height="12" viewBox="0 0 12 12"
          className="text-on-surface-variant transition-transform duration-150"
          style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}
        >
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant">{title}</span>
        <span className="bg-surface-container-highest text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded">{milestones.length}</span>
      </button>
      {!collapsed && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-2">
          {milestones.map((milestone) => (
            <MilestoneCard key={milestone.id} milestone={milestone} projectId={projectId} workplanId={workplanId} />
          ))}
        </div>
      )}
    </div>
  );
}

function UnassignedTasksSection({
  tasks,
  onTaskClick,
}: {
  tasks: Task[];
  onTaskClick: (task: Task) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);

  if (tasks.length === 0) return null;

  return (
    <div className="mb-6">
      <button
        className="flex items-center gap-2 w-full bg-transparent border-0 cursor-pointer py-2 px-0 text-left"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          width="12" height="12" viewBox="0 0 12 12"
          className="text-on-surface-variant transition-transform duration-150"
          style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}
        >
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant">Unassigned Tasks</span>
        <span className="bg-surface-container-highest text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded">{tasks.length}</span>
      </button>
      {!collapsed && (
        <TaskListTable
          tasks={tasks}
          columns={BACKLOG_COLUMNS}
          onTaskClick={onTaskClick}
          pageSize={10}
          emptyMessage="No unassigned tasks"
        />
      )}
    </div>
  );
}

export function WorkplanDetail() {
  const { id: projectId, wid: workplanId } = useParams<{ id: string; wid: string }>();
  useSetActiveProject(projectId);
  const { data: project } = useProject(projectId);
  const { data: workplan, isLoading: wpLoading } = useWorkplan(workplanId!);
  const { data: wpStats } = useWorkplanStats(workplanId!);
  const { data: milestones, isLoading: phLoading } = useMilestones(workplanId!);
  const { data: orphanData } = useOrphanTasks(workplanId!);
  const orphanTasks = orphanData?.results ?? [];
  const [viewMode, setViewMode] = useState<'list' | 'pipeline'>('list');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const handleSSEEvent = useCallback(
    (event: MessageEvent) => {
      let data: { task_id?: string } = {};
      try {
        data = JSON.parse(event.data);
      } catch {
        // ignore malformed events
      }
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['workplan-stats'] });
      queryClient.invalidateQueries({ queryKey: ['milestone-stats'] });
      if (data.task_id) {
        queryClient.invalidateQueries({ queryKey: ['task', data.task_id] });
      }
    },
    [queryClient],
  );

  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?workplan=${workplanId}`,
    onEvent: handleSSEEvent,
    enabled: !!workplanId,
  });

  if (wpLoading || phLoading) return <div className="flex items-center justify-center p-12 text-on-surface-variant">Loading...</div>;

  const activeMilestones = (milestones ?? []).filter((p) => p.status === 'active');
  const pendingMilestones = (milestones ?? []).filter((p) => p.status === 'pending');
  const completedMilestones = (milestones ?? []).filter((p) => p.status === 'completed');

  const totalTasks = wpStats?.total_tasks ?? 0;
  const doneTasks = wpStats?.by_status?.done ?? 0;
  const doingTasks = wpStats?.by_status?.doing ?? 0;
  const todoTasks = wpStats?.by_status?.todo ?? 0;
  const overallPct = wpStats?.completed_percentage ?? 0;

  return (
    <div className="px-8 pb-12 pt-6">
      {/* Breadcrumbs */}
      <Breadcrumb segments={[
        { label: project?.name ?? 'Project', to: `/projects/${projectId}` },
        { label: workplan?.name ?? 'Workplan' }
      ]} />

      {/* Project info header */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow mb-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-headline font-bold text-on-surface m-0">{workplan?.name || 'Workplan'}</h1>
            {workplan?.description && (
              <p className="text-sm text-on-surface-variant mt-1 mb-0">{workplan.description}</p>
            )}
          </div>
          <LiveIndicator status={sseStatus} />
        </div>

        <div className="flex items-center gap-6 flex-wrap">
          <div className="text-center">
            <span className="block text-2xl font-extrabold text-on-surface">{totalTasks}</span>
            <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-semibold">Tasks</span>
          </div>
          <div className="text-center">
            <span className="block text-2xl font-extrabold text-on-surface">{doneTasks}</span>
            <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-semibold">Done</span>
          </div>
          <div className="text-center">
            <span className="block text-2xl font-extrabold text-on-surface">{doingTasks}</span>
            <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-semibold">In Progress</span>
          </div>
          <div className="text-center">
            <span className="block text-2xl font-extrabold text-on-surface">{todoTasks}</span>
            <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-semibold">Ready</span>
          </div>
          <div className="text-center">
            <div className="flex items-center gap-2 mb-0.5">
              <div className="w-16 h-1.5 rounded-full bg-surface-container-high overflow-hidden">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${overallPct}%` }} />
              </div>
              <span className="text-2xl font-extrabold text-on-surface">{overallPct}%</span>
            </div>
            <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-semibold">Overall</span>
          </div>
          {workplan?.tags && workplan.tags.length > 0 && (
            <div className="flex gap-1.5 flex-wrap ml-auto">
              {workplan.tags.map((tag) => (
                <span key={tag} className="bg-secondary-container text-on-secondary-container text-[11px] font-semibold px-2.5 py-0.5 rounded-full">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* View toggle */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex gap-0.5 bg-surface-container-lowest border border-outline-variant/30 rounded-lg p-0.5">
          {(['list', 'pipeline'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-4 py-1.5 text-xs rounded-md border-0 cursor-pointer transition-colors ${
                viewMode === mode
                  ? 'bg-surface-container-high font-bold text-on-surface'
                  : 'bg-transparent text-on-surface-variant hover:bg-surface-container-low'
              }`}
            >
              {mode === 'list' ? 'Milestones' : 'Pipeline'}
            </button>
          ))}
        </div>
        <span className="text-xs text-on-surface-variant">{milestones?.length ?? 0} milestones</span>
      </div>

      {/* Milestone content */}
      {viewMode === 'list' ? (
        <div>
          <MilestoneGroup title="Active" milestones={activeMilestones} projectId={projectId!} workplanId={workplanId!} />
          <MilestoneGroup title="Pending" milestones={pendingMilestones} projectId={projectId!} workplanId={workplanId!} />
          <MilestoneGroup title="Completed" milestones={completedMilestones} projectId={projectId!} workplanId={workplanId!} defaultCollapsed />
          <UnassignedTasksSection tasks={orphanTasks} onTaskClick={(task) => setSelectedTaskId(task.id)} />
        </div>
      ) : (
        <MilestonePipeline milestones={milestones ?? []} projectId={projectId!} workplanId={workplanId!} />
      )}

      <TaskDetail taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} />
    </div>
  );
}
