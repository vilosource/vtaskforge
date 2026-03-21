import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useWorkplans, useWorkplanStats, type Workplan } from '../api/workplans';

function WorkplanItem({ wp, isActive }: { wp: Workplan; isActive: boolean }) {
  const { data: stats } = useWorkplanStats(wp.id);
  const pct = stats?.completed_percentage ?? 0;

  const statusDotColor =
    wp.status === 'completed' ? 'var(--color-done)' :
    wp.status === 'active' ? 'var(--color-doing)' :
    wp.status === 'archived' ? 'var(--color-draft)' :
    'var(--color-draft)';

  return (
    <Link
      to={`/workplans/${wp.id}`}
      className={`sidebar-wp-item ${isActive ? 'sidebar-wp-item--active' : ''}`}
    >
      <span
        className="sidebar-wp-dot"
        style={{ background: statusDotColor }}
      />
      <span className="sidebar-wp-name">{wp.name}</span>
      {stats && stats.total_tasks > 0 && (
        <span className="sidebar-wp-pct">{pct}%</span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { id: activeWorkplanId } = useParams<{ id: string }>();
  const { data } = useWorkplans();
  const workplans = data?.results ?? [];

  if (collapsed) {
    return (
      <aside className="sidebar sidebar--collapsed">
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed(false)}
          title="Expand sidebar"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <Link to="/" className="sidebar-brand">VTaskForge</Link>
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed(true)}
          title="Collapse sidebar"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M10 3l-5 5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      <div className="sidebar-section-label">Workplans</div>

      <nav className="sidebar-nav">
        {workplans.map((wp) => (
          <WorkplanItem
            key={wp.id}
            wp={wp}
            isActive={wp.id === activeWorkplanId}
          />
        ))}
        {workplans.length === 0 && (
          <div className="sidebar-empty">No workplans</div>
        )}
      </nav>
    </aside>
  );
}
