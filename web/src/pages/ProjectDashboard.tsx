import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useProject, useProjectStats, useProjectWorkplans } from '../api/projects';
import { useBacklogTasks, type Task } from '../api/tasks';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';
import { TaskListTable, BACKLOG_COLUMNS } from '../components/TaskListTable';
import { Breadcrumb } from '../components/Breadcrumb';
import { useSetActiveProject } from '../contexts/ActiveProjectContext';

function WorkplanCard({ workplan, projectId }: {
  workplan: { id: string; name: string; description: string; status: string; total_tasks: number; completed_percentage: number };
  projectId: string;
}) {
  const statusColor = workplan.status === 'completed' ? 'var(--color-done)'
    : workplan.status === 'active' ? 'var(--color-doing)'
    : 'var(--color-draft)';

  return (
    <Link
      to={`/projects/${projectId}/workplans/${workplan.id}`}
      className="project-workplan-card"
      style={{ borderLeftColor: statusColor }}
    >
      <div className="project-workplan-card-header">
        <div className="project-workplan-card-title">{workplan.name}</div>
        <span
          className={`badge ${
            workplan.status === 'completed' ? 'badge-completed' :
            workplan.status === 'active' ? 'badge-active' :
            'badge-draft'
          }`}
        >
          {workplan.status}
        </span>
      </div>
      {workplan.description && (
        <div className="project-workplan-card-desc">{workplan.description}</div>
      )}
      <div className="project-workplan-card-footer">
        <span className="project-workplan-card-stats">{workplan.total_tasks} tasks</span>
        <div className="project-workplan-card-progress">
          <div className="project-workplan-card-progress-bar">
            <div className="project-workplan-card-progress-fill" style={{ width: `${workplan.completed_percentage}%`, background: statusColor }} />
          </div>
          <span className="project-workplan-card-progress-text">{workplan.completed_percentage}%</span>
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
    <div className="project-workplan-group">
      <button
        className="project-workplan-group-header"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          width="12" height="12" viewBox="0 0 12 12"
          style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
        >
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="project-workplan-group-title">{title}</span>
        <span className="project-workplan-group-count">{workplans.length}</span>
      </button>
      {!collapsed && (
        <div className="project-workplan-group-grid">
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
  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?project=${id}`,
    onEvent: () => {},
    enabled: !!id,
  });

  if (projectLoading || workplansLoading) return <div className="loading">Loading...</div>;

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
    <div className="project-dashboard">
      <Breadcrumb segments={[
        { label: 'Projects', to: '/' },
        { label: project?.name ?? '' },
      ]} />
      {/* Project info header */}
      <div className="project-dashboard-header">
        <div className="project-dashboard-header-top">
          <div>
            <h1 className="project-dashboard-title">{project?.name || 'Project'}</h1>
            {project?.description && (
              <p className="project-dashboard-desc">{project.description}</p>
            )}
          </div>
          <LiveIndicator status={sseStatus} />
        </div>

        <div className="project-dashboard-stats">
          <div className="project-stat">
            <span className="project-stat-value">{totalTasks}</span>
            <span className="project-stat-label">Tasks</span>
          </div>
          <div className="project-stat">
            <span className="project-stat-value">{doneTasks}</span>
            <span className="project-stat-label">Done</span>
          </div>
          <div className="project-stat">
            <span className="project-stat-value">{doingTasks}</span>
            <span className="project-stat-label">In Progress</span>
          </div>
          <div className="project-stat">
            <span className="project-stat-value">{todoTasks}</span>
            <span className="project-stat-label">Ready</span>
          </div>
          <div className="project-stat">
            <div className="project-stat-progress">
              <div className="project-stat-progress-bar">
                <div className="project-stat-progress-fill" style={{ width: `${overallPct}%` }} />
              </div>
              <span className="project-stat-value">{overallPct}%</span>
            </div>
            <span className="project-stat-label">Overall</span>
          </div>
          {project?.repo_url && (
            <div className="project-repo">
              <a href={project.repo_url} target="_blank" rel="noopener noreferrer" className="project-repo-link">
                Repository
              </a>
            </div>
          )}
          {project?.tags && project.tags.length > 0 && (
            <div className="project-tags">
              {project.tags.map((tag) => (
                <span key={tag} className="project-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="project-dashboard-content">
        {/* Workplans section */}
        <div className="project-dashboard-section">
          <div className="project-dashboard-section-header">
            <h2 className="project-dashboard-section-title">Workplans</h2>
            <span className="project-dashboard-section-count">{workplans?.length ?? 0}</span>
          </div>

          <div className="project-workplans">
            <WorkplanGroup title="Active" workplans={activeWorkplans} projectId={id!} />
            <WorkplanGroup title="Pending" workplans={pendingWorkplans} projectId={id!} />
            <WorkplanGroup title="Completed" workplans={completedWorkplans} projectId={id!} defaultCollapsed />
          </div>
        </div>

        {/* Backlog section */}
        <div className="project-dashboard-section">
          <div className="project-dashboard-section-header">
            <h2 className="project-dashboard-section-title">
              <Link to={`/projects/${id}/backlog`} className="project-backlog-link">
                Backlog
              </Link>
            </h2>
            <span className="project-dashboard-section-count">{backlogCount}</span>
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
                <div style={{ textAlign: 'center', padding: '8px 0' }}>
                  <Link
                    to={`/projects/${id}/backlog`}
                    style={{ fontSize: '0.8125rem', color: 'var(--color-primary)' }}
                  >
                    View all {backlogCount} backlog tasks
                  </Link>
                </div>
              )}
            </>
          ) : (
            <div className="project-dashboard-empty">
              No backlog tasks
            </div>
          )}
        </div>
      </div>
    </div>
  );
}