import { useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useProject, useProjectStats, useProjectWorkplans } from '../api/projects';
import { useBacklogTasks, type Task } from '../api/tasks';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';
import { TaskListTable, BACKLOG_COLUMNS } from '../components/TaskListTable';
import { Breadcrumb } from '../components/Breadcrumb';
import { useSetActiveProject } from '../contexts/ActiveProjectContext';
import { useConsoleWidget } from '../contexts/ConsoleWidgetContext';
import { useChatWidget } from '../contexts/ChatWidgetContext';

function WorkplanCard({ workplan, projectId }: {
  workplan: { id: string; name: string; description: string; status: string; total_tasks: number; completed_percentage: number };
  projectId: string;
}) {
  const borderColor = workplan.status === 'completed' ? 'border-tertiary'
    : workplan.status === 'active' ? 'border-primary'
    : 'border-outline-variant';

  const progressBg = workplan.status === 'completed' ? 'bg-tertiary'
    : workplan.status === 'active' ? 'bg-primary'
    : 'bg-outline-variant';

  return (
    <Link
      to={`/projects/${projectId}/workplans/${workplan.id}`}
      className={`block bg-surface-container-lowest rounded-xl shadow-sm border-l-[3px] ${borderColor} p-4 hover:shadow-md transition-shadow no-underline`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="font-bold text-sm text-on-surface leading-snug">{workplan.name}</div>
        <span
          className={`shrink-0 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide ${
            workplan.status === 'completed' ? 'bg-tertiary-container text-on-tertiary-container' :
            workplan.status === 'active' ? 'bg-blue-100 text-blue-700' :
            'bg-surface-container-highest text-on-surface-variant'
          }`}
        >
          {workplan.status === 'active' && <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 mr-1 align-middle" />}
          {workplan.status}
        </span>
      </div>
      {workplan.description && (
        <div className="text-xs text-on-surface-variant leading-relaxed mb-3 line-clamp-2">{workplan.description}</div>
      )}
      <div className="flex items-center justify-between text-xs text-on-surface-variant mt-auto">
        <span>{workplan.total_tasks} tasks</span>
        <div className="flex items-center gap-2">
          <div className="w-20 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
            <div className={`h-full rounded-full ${progressBg} transition-all`} style={{ width: `${workplan.completed_percentage}%` }} />
          </div>
          <span className="text-[10px] font-bold text-on-surface-variant tabular-nums">{workplan.completed_percentage}%</span>
        </div>
      </div>
    </Link>
  );
}

function WorkplanGroup({ title, workplans, projectId, defaultCollapsed = false }: {
  title: string;
  workplans: { id: string; name: string; description: string; status: string; total_tasks: number; completed_percentage: number }[];
  projectId: string;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (workplans.length === 0) return null;

  return (
    <div className="mb-4">
      <button
        className="flex items-center gap-2 w-full text-left py-2 group"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          width="12" height="12" viewBox="0 0 12 12"
          className={`text-on-surface-variant transition-transform duration-150 ${collapsed ? '-rotate-90' : ''}`}
        >
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">{title}</span>
        <span className="px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant text-[10px] font-bold">{workplans.length}</span>
      </button>
      {!collapsed && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-2">
          {workplans.map((workplan) => (
            <WorkplanCard key={workplan.id} workplan={workplan} projectId={projectId} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ProjectDashboard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  useSetActiveProject(id);
  const { data: project, isLoading: projectLoading } = useProject(id);
  const { data: stats } = useProjectStats(id);
  const { data: workplans, isLoading: workplansLoading } = useProjectWorkplans(id);
  const { data: backlogData } = useBacklogTasks(id!);
  const { open: openConsoleWidget } = useConsoleWidget();
  const { open: openChatWidget } = useChatWidget();
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
      queryClient.invalidateQueries({ queryKey: ['project-stats'] });
      if (data.task_id) {
        queryClient.invalidateQueries({ queryKey: ['task', data.task_id] });
      }
    },
    [queryClient],
  );

  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?project=${id}`,
    onEvent: handleSSEEvent,
    enabled: !!id,
  });

  if (projectLoading || workplansLoading) return <div className="flex items-center justify-center h-64 text-on-surface-variant">Loading...</div>;

  const activeWorkplans = (workplans ?? []).filter((wp) => wp.status === 'active');
  const pendingWorkplans = (workplans ?? []).filter((wp) => wp.status === 'pending');
  const completedWorkplans = (workplans ?? []).filter((wp) => wp.status === 'completed');

  const totalTasks = stats?.total_tasks ?? 0;
  const doneTasks = stats?.by_status?.done ?? 0;
  const doingTasks = stats?.by_status?.doing ?? 0;
  const todoTasks = stats?.by_status?.todo ?? 0;
  const overallPct = stats?.completed_percentage ?? 0;
  const backlogCount = stats?.backlog_tasks ?? 0;

  const backlogTasks = backlogData?.results ?? [];

  return (
    <div className="px-8 pb-12">
      <Breadcrumb segments={[
        { label: 'Projects', to: '/' },
        { label: project?.name ?? '' },
      ]} />

      {/* Project info header */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow mb-8">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="text-4xl font-headline font-extrabold tracking-tight text-on-surface mb-1">
              {project?.name || 'Project'}
            </h1>
            {project?.description && (
              <p className="text-sm text-on-surface-variant leading-relaxed mt-1">{project.description}</p>
            )}
          </div>
          <LiveIndicator status={sseStatus} />
        </div>

        <div className="flex items-end gap-8 flex-wrap">
          <div className="flex flex-col items-center">
            <span className="text-2xl font-headline font-extrabold text-on-surface tabular-nums">{totalTasks}</span>
            <span className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Tasks</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-2xl font-headline font-extrabold text-on-surface tabular-nums">{doneTasks}</span>
            <span className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Done</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-2xl font-headline font-extrabold text-on-surface tabular-nums">{doingTasks}</span>
            <span className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">In Progress</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-2xl font-headline font-extrabold text-on-surface tabular-nums">{todoTasks}</span>
            <span className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Ready</span>
          </div>
          <div className="flex flex-col items-center">
            <div className="flex items-center gap-2">
              <div className="w-20 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${overallPct}%` }} />
              </div>
              <span className="text-2xl font-headline font-extrabold text-on-surface tabular-nums">{overallPct}%</span>
            </div>
            <span className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Overall</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {project?.id && (
              <>
                <button
                  onClick={() => openConsoleWidget({ role: 'architect', project: project.id })}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-bold hover:bg-primary/20 transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">terminal</span>
                  Plan with Architect
                </button>
                <button
                  onClick={() => openChatWidget(project.name || project.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-bold hover:bg-primary/20 transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">chat</span>
                  Chat with Architect
                </button>
              </>
            )}
            {project?.repo_url && (
              <a
                href={project.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline font-medium"
              >
                Repository
              </a>
            )}
          </div>
          {project?.tags && project.tags.length > 0 && (
            <div className="flex gap-1.5 flex-wrap">
              {project.tags.map((tag) => (
                <span key={tag} className="px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container text-[10px] font-bold">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-8">
        {/* Workplans section */}
        <div className="bg-surface-container-lowest rounded-xl shadow p-6">
          <div className="flex items-center gap-3 mb-5">
            <h2 className="text-xl font-headline font-bold text-on-surface">Workplans</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant text-[10px] font-bold">{workplans?.length ?? 0}</span>
          </div>

          <div>
            <WorkplanGroup title="Active" workplans={activeWorkplans} projectId={id!} />
            <WorkplanGroup title="Pending" workplans={pendingWorkplans} projectId={id!} />
            <WorkplanGroup title="Completed" workplans={completedWorkplans} projectId={id!} defaultCollapsed />
          </div>
        </div>

        {/* Backlog section */}
        <div className="bg-surface-container-lowest rounded-xl shadow p-6">
          <div className="flex items-center gap-3 mb-5">
            <h2 className="text-xl font-headline font-bold text-on-surface">
              <Link to={`/projects/${id}/backlog`} className="text-on-surface hover:text-primary transition-colors no-underline">
                Backlog
              </Link>
            </h2>
            <span className="px-2.5 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant text-[10px] font-bold">{backlogCount}</span>
          </div>

          {backlogTasks.length > 0 ? (
            <>
              <TaskListTable
                tasks={backlogTasks}
                columns={BACKLOG_COLUMNS}
                onTaskClick={(task: Task) => navigate(`/tasks/${task.id}`)}
                pageSize={15}
                emptyMessage="No backlog tasks"
              />
              {backlogCount > backlogTasks.length && (
                <div className="text-center py-2">
                  <Link
                    to={`/projects/${id}/backlog`}
                    className="text-[13px] text-primary hover:underline"
                  >
                    View all {backlogCount} backlog tasks
                  </Link>
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-on-surface-variant py-8 text-center">
              No backlog tasks
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
