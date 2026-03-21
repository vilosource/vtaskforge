import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useWorkplan } from '../api/tasks';
import { useWorkplanStats } from '../api/workplans';
import { usePhases, usePhaseStats, useActivatePhase, useCompletePhase } from '../api/phases';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';
import { PhasePipeline } from '../components/PhasePipeline';

function PhaseCard({ phase, workplanId }: { phase: { id: string; name: string; description: string; status: string }; workplanId: string }) {
  const { data: stats } = usePhaseStats(phase.id);
  const activateMutation = useActivatePhase();
  const completeMutation = useCompletePhase();
  const total = stats?.total_tasks ?? 0;
  const done = stats?.by_status?.done ?? 0;
  const pct = stats?.completed_percentage ?? 0;

  const statusColor = phase.status === 'completed' ? 'var(--color-done)'
    : phase.status === 'active' ? 'var(--color-doing)'
    : 'var(--color-draft)';

  return (
    <Link
      to={`/workplans/${workplanId}/phases/${phase.id}`}
      className="phase-card"
      style={{ borderLeftColor: statusColor }}
    >
      <div className="phase-card-header">
        <div className="phase-card-title">{phase.name}</div>
        <span
          className={`badge ${
            phase.status === 'completed' ? 'badge-completed' :
            phase.status === 'active' ? 'badge-active' :
            'badge-draft'
          }`}
        >
          {phase.status}
        </span>
      </div>
      {phase.description && (
        <div className="phase-card-desc">{phase.description}</div>
      )}
      <div className="phase-card-footer">
        <span className="phase-card-stats">{total} tasks &middot; {done} done</span>
        <div className="phase-card-progress">
          <div className="phase-card-progress-bar">
            <div className="phase-card-progress-fill" style={{ width: `${pct}%`, background: statusColor }} />
          </div>
          <span className="phase-card-progress-text">{pct}%</span>
        </div>
        {phase.status === 'pending' && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); activateMutation.mutate(phase.id); }}
            disabled={activateMutation.isPending}
            className="btn btn-primary"
            style={{ padding: '4px 12px', minHeight: 28, fontSize: 12 }}
          >
            {activateMutation.isPending ? 'Activating...' : 'Activate'}
          </button>
        )}
        {phase.status === 'active' && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); completeMutation.mutate(phase.id); }}
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

function PhaseGroup({ title, phases, workplanId, defaultCollapsed = false }: {
  title: string;
  phases: { id: string; name: string; description: string; status: string }[];
  workplanId: string;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (phases.length === 0) return null;

  return (
    <div className="phase-group">
      <button
        className="phase-group-header"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          width="12" height="12" viewBox="0 0 12 12"
          style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
        >
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="phase-group-title">{title}</span>
        <span className="phase-group-count">{phases.length}</span>
      </button>
      {!collapsed && (
        <div className="phase-group-grid">
          {phases.map((phase) => (
            <PhaseCard key={phase.id} phase={phase} workplanId={workplanId} />
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
  const { data: phases, isLoading: phLoading } = usePhases(id!);
  const [viewMode, setViewMode] = useState<'list' | 'pipeline'>('list');
  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?workplan=${id}`,
    onEvent: () => {},
    enabled: !!id,
  });

  if (wpLoading || phLoading) return <div className="loading">Loading...</div>;

  const activePhases = (phases ?? []).filter((p) => p.status === 'active');
  const pendingPhases = (phases ?? []).filter((p) => p.status === 'pending');
  const completedPhases = (phases ?? []).filter((p) => p.status === 'completed');

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
              {mode === 'list' ? 'Phases' : 'Pipeline'}
            </button>
          ))}
        </div>
        <span className="workplan-phase-count">{phases?.length ?? 0} phases</span>
      </div>

      {/* Phase content */}
      {viewMode === 'list' ? (
        <div className="workplan-phases">
          <PhaseGroup title="Active" phases={activePhases} workplanId={id!} />
          <PhaseGroup title="Pending" phases={pendingPhases} workplanId={id!} />
          <PhaseGroup title="Completed" phases={completedPhases} workplanId={id!} defaultCollapsed />
        </div>
      ) : (
        <PhasePipeline phases={phases ?? []} workplanId={id!} />
      )}
    </div>
  );
}
