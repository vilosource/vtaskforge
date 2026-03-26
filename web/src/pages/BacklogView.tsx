import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TaskListTable, BACKLOG_COLUMNS } from '../components/TaskListTable';
import { useProject } from '../api/projects';
import { useBacklogTasks, type Task } from '../api/tasks';
import { Breadcrumb } from '../components/Breadcrumb';
import { useSetActiveProject } from '../contexts/ActiveProjectContext';

export function BacklogView() {
  const { id: projectId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [labelFilters, setLabelFilters] = useState<string[]>([]);
  useSetActiveProject(projectId);

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

  const filteredTasks = useMemo(() => {
    if (labelFilters.length === 0) return backlogTasks;
    return backlogTasks.filter((task) =>
      task.labels.some((label) => labelFilters.includes(label))
    );
  }, [backlogTasks, labelFilters]);

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
      <div style={{ padding: '0 24px' }}>
        <Breadcrumb segments={[
          { label: project?.name ?? 'Project', to: `/projects/${projectId}` },
          { label: 'Backlog' }
        ]} />
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

      <div style={{ padding: '0 24px 24px' }}>
        <TaskListTable
          tasks={filteredTasks}
          columns={BACKLOG_COLUMNS}
          onTaskClick={(task: Task) => navigate(`/tasks/${task.id}`)}
          emptyMessage="No backlog tasks"
        />
      </div>
    </div>
  );
}