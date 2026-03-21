import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';
import { useProject } from '../api/projects';
import { useBacklogTasks } from '../api/tasks';

export function BacklogView() {
  const { id: projectId } = useParams<{ id: string }>();
  const [labelFilters, setLabelFilters] = useState<string[]>([]);

  const { data: project } = useProject(projectId);
  const { data: backlogData } = useBacklogTasks(projectId!);

  const backlogTasks = backlogData?.results ?? [];

  // Extract unique labels from all backlog tasks
  const availableLabels = useMemo(() => {
    const labelSet = new Set<string>();
    backlogTasks.forEach((task) => {
      task.labels.forEach((label) => {
        labelSet.add(label);
      });
    });
    return Array.from(labelSet).sort();
  }, [backlogTasks]);

  const handleLabelToggle = (label: string) => {
    setLabelFilters((prev) => {
      if (prev.includes(label)) {
        return prev.filter((l) => l !== label);
      } else {
        return [...prev, label];
      }
    });
  };

  const handleClearFilters = () => {
    setLabelFilters([]);
  };

  if (!projectId) {
    return <div className="error">Invalid project ID.</div>;
  }

  return (
    <div>
      <div style={{ padding: '12px 24px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Link
          to={`/projects/${projectId}`}
          style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: 14 }}
        >
          {project?.name ?? 'Project'}
        </Link>
        <span style={{ color: 'var(--color-text-secondary)', fontSize: 14 }}>/</span>
        <span style={{ color: 'var(--color-text)', fontSize: 14 }}>Backlog</span>
      </div>

      {/* Label filter pills */}
      {availableLabels.length > 0 && (
        <div style={{
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          borderBottom: '1px solid var(--color-border)'
        }}>
          <span style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginRight: 8 }}>
            Filter by label:
          </span>
          <button
            onClick={handleClearFilters}
            className={`filter-pill ${labelFilters.length === 0 ? 'filter-pill-active' : ''}`}
            style={{
              padding: '4px 12px',
              border: '1px solid var(--color-border)',
              borderRadius: '16px',
              background: labelFilters.length === 0 ? 'var(--color-primary)' : 'var(--color-bg)',
              color: labelFilters.length === 0 ? 'white' : 'var(--color-text)',
              fontSize: 12,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            All
          </button>
          {availableLabels.map((label) => (
            <button
              key={label}
              onClick={() => handleLabelToggle(label)}
              className={`filter-pill ${labelFilters.includes(label) ? 'filter-pill-active' : ''}`}
              style={{
                padding: '4px 12px',
                border: '1px solid var(--color-border)',
                borderRadius: '16px',
                background: labelFilters.includes(label) ? 'var(--color-primary)' : 'var(--color-bg)',
                color: labelFilters.includes(label) ? 'white' : 'var(--color-text)',
                fontSize: 12,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <KanbanBoard
        projectId={projectId}
        labelFilters={labelFilters}
      />
    </div>
  );
}