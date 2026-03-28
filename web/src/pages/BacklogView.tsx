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
    return <div className="p-6 text-error font-semibold">Invalid project ID.</div>;
  }

  return (
    <div>
      <div className="px-6">
        <Breadcrumb segments={[
          { label: project?.name ?? 'Project', to: `/projects/${projectId}` },
          { label: 'Backlog' }
        ]} />
      </div>

      {/* Label filter pills */}
      {availableLabels.length > 0 && (
        <div className="px-6 py-3 flex items-center gap-2 flex-wrap border-b border-outline-variant/30">
          <span className="text-sm text-on-surface-variant mr-2">
            Filter by label:
          </span>
          <button
            onClick={handleClearFilters}
            className={`px-3 py-1.5 rounded-full text-xs font-bold border-0 cursor-pointer transition-colors ${
              labelFilters.length === 0
                ? 'bg-primary text-on-primary'
                : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
            }`}
          >
            All
          </button>
          {availableLabels.map((label) => (
            <button
              key={label}
              onClick={() => handleLabelToggle(label)}
              className={`px-3 py-1.5 rounded-full text-xs font-bold border-0 cursor-pointer transition-colors ${
                labelFilters.includes(label)
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div className="px-6 pb-6">
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
