import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useWorkplan } from '../api/tasks';
import { useWorkplanStats } from '../api/workplans';
import { useMilestones, useMilestoneStats, useActivateMilestone, useCompleteMilestone } from '../api/milestones';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';
import { MilestonePipeline } from '../components/MilestonePipeline';

function MilestoneCard({ milestone, workplanId }: { milestone: { id: string; name: string; description: string; status: string }; workplanId: string }) {
  const { data: stats } = useMilestoneStats(milestone.id);
  const activateMutation = useActivateMilestone();
  const completeMutation = useCompleteMilestone();
  const total = stats?.total_tasks ?? 0;
  const done = stats?.by_status?.done ?? 0;
  const pct = stats?.completed_percentage ?? 0;

  const statusColor = milestone.status === 'completed' ? 'var(--color-done)'
    : milestone.status === 'active' ? 'var(--color-doing)'
    : 'var(--color-draft)';

  return (
    <Link
      to={`/workplans/${workplanId}/milestones/${milestone.id}`}
      className="milestone-card"
      style={{ borderLeftColor: statusColor }}
    >
      <div className="milestone-card-header">
        <div className="milestone-card-title">{milestone.name}</div>
        <span
          className={`badge ${
            milestone.status === 'completed' ? 'badge-completed' :
            milestone.status === 'active' ? 'badge-active' :
            'badge-draft'
          }`}
        >
          {milestone.status}
        </span>
      </div>
      {milestone.description && (
        <div className="milestone-card-desc">{milestone.description}</div>
      )}
      <div className="milestone-card-footer">
        <span className="milestone-card-stats">{total} tasks &middot; {done} done</span>
        <div className="milestone-card-progress">
          <div className="milestone-card-progress-bar">
            <div className="milestone-card-progress-fill" style={{ width: `${pct}%`, background: statusColor }} />
          </div>
          <span className="milestone-card-progress-text">{pct}%</span>
        </div>
        {milestone.status === 'pending' && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); activateMutation.mutate(milestone.id); }}
            disabled={activateMutation.isPending}
            className="btn btn-primary"
            style={{ padding: '4px 12px', minHeight: 28, fontSize: 12 }}
          >
            {activateMutation.isPending ? 'Activating...' : 'Activate'}
          </button>
        )}
        {milestone.status === 'active' && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); completeMutation.mutate(milestone.id); }}
            disabled={completeMutation.isPending}
            className="btn btn-success"
            style={{ padding: '4px 12px', minHeight: 28, fontSize: 12 }}
          >
            {completeMutation.isPending ? 'Completing...' : 'Complete'}
          </button>
        )}
      </div>
    </Link>
  );
}

function MilestoneGroup({ title, milestones, workplanId, defaultCollapsed = false }: {
  title: string;
  milestones: { id: string; name: string; description: string; status: string }[];
  workplanId: string;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (milestones.length === 0) return null;

  return (
    <div className="milestone-group">
      <button
        className="milestone-group-header"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          width="12" height="12" viewBox="0 0 12 12"
          style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
        >
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="milestone-group-title">{title}</span>
        <span className="milestone-group-count">{milestones.length}</span>
      </button>
      {!collapsed && (
        <div className="milestone-group-grid">
          {milestones.map((milestone) => (
            <MilestoneCard key={milestone.id} milestone={milestone} workplanId={workplanId} />
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkplanDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: workplan, isLoading: wpLoading } = useWorkplan(id!);
  const { data: wpStats } = useWorkplanStats(id!);
  const { data: milestones, isLoading: phLoading } = useMilestones(id!);
  const [viewMode, setViewMode] = useState<'list' | 'pipeline'>('list');
  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?workplan=${id}`,
    onEvent: () => {},
    enabled: !!id,
  });

  if (wpLoading || phLoading) return <div className="loading">Loading...</div>;

  const activeMilestones = (milestones ?? []).filter((p) => p.status === 'active');
  const pendingMilestones = (milestones ?? []).filter((p) => p.status === 'pending');
  const completedMilestones = (milestones ?? []).filter((p) => p.status === 'completed');

  const totalTasks = wpStats?.total_tasks ?? 0;
  const doneTasks = wpStats?.by_status?.done ?? 0;
  const doingTasks = wpStats?.by_status?.doing ?? 0;
  const todoTasks = wpStats?.by_status?.todo ?? 0;
  const overallPct = wpStats?.completed_percentage ?? 0;

  return (
    <div className="workplan-detail">
      {/* Project info header */}
      <div className="workplan-detail-header">
        <div className="workplan-detail-header-top">
          <div>
            <h1 className="workplan-detail-title">{workplan?.name || 'Workplan'}</h1>
            {workplan?.description && (
              <p className="workplan-detail-desc">{workplan.description}</p>
            )}
          </div>
          <LiveIndicator status={sseStatus} />
        </div>

        <div className="workplan-detail-stats">
          <div className="workplan-stat">
            <span className="workplan-stat-value">{totalTasks}</span>
            <span className="workplan-stat-label">Tasks</span>
          </div>
          <div className="workplan-stat">
            <span className="workplan-stat-value">{doneTasks}</span>
            <span className="workplan-stat-label">Done</span>
          </div>
          <div className="workplan-stat">
            <span className="workplan-stat-value">{doingTasks}</span>
            <span className="workplan-stat-label">In Progress</span>
          </div>
          <div className="workplan-stat">
            <span className="workplan-stat-value">{todoTasks}</span>
            <span className="workplan-stat-label">Ready</span>
          </div>
          <div className="workplan-stat">
            <div className="workplan-stat-progress">
              <div className="workplan-stat-progress-bar">
                <div className="workplan-stat-progress-fill" style={{ width: `${overallPct}%` }} />
              </div>
              <span className="workplan-stat-value">{overallPct}%</span>
            </div>
            <span className="workplan-stat-label">Overall</span>
          </div>
          {workplan?.tags && workplan.tags.length > 0 && (
            <div className="workplan-tags">
              {workplan.tags.map((tag) => (
                <span key={tag} className="workplan-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* View toggle */}
      <div className="workplan-detail-toolbar">
        <div className="workplan-view-toggle">
          {(['list', 'pipeline'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`workplan-view-toggle-btn ${viewMode === mode ? 'workplan-view-toggle-btn--active' : ''}`}
            >
              {mode === 'list' ? 'Milestones' : 'Pipeline'}
            </button>
          ))}
        </div>
        <span className="workplan-milestone-count">{milestones?.length ?? 0} milestones</span>
      </div>

      {/* Milestone content */}
      {viewMode === 'list' ? (
        <div className="workplan-milestones">
          <MilestoneGroup title="Active" milestones={activeMilestones} workplanId={id!} />
          <MilestoneGroup title="Pending" milestones={pendingMilestones} workplanId={id!} />
          <MilestoneGroup title="Completed" milestones={completedMilestones} workplanId={id!} defaultCollapsed />
        </div>
      ) : (
        <MilestonePipeline milestones={milestones ?? []} workplanId={id!} />
      )}
    </div>
  );
}
