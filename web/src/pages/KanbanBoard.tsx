import { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTasksByWorkplan, useTasksByPhase, useWorkplan } from '../api/tasks';
import type { Task } from '../api/tasks';
import { KanbanColumn } from '../components/KanbanColumn';
import type { ColumnConfig } from '../components/KanbanColumn';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';
import { TaskDetail } from '../components/TaskDetail';

const COLUMNS: ColumnConfig[] = [
  {
    id: 'draft',
    label: 'Draft',
    statuses: ['draft', 'pending_start_review'],
    color: 'grey',
  },
  { id: 'ready', label: 'Ready', statuses: ['todo'], color: 'blue' },
  { id: 'in-progress', label: 'In Progress', statuses: ['doing', 'pending_completion_review'], color: 'blue-highlight' },
  {
    id: 'attention',
    label: 'Attention',
    statuses: ['changes_requested', 'needs_attention', 'blocked'],
    color: 'red',
  },
  { id: 'done', label: 'Done', statuses: ['done'], color: 'green' },
];

const HIDDEN_STATUSES = ['deferred', 'cancelled'];

function groupTasksByColumn(tasks: Task[], showHidden: boolean): Map<string, Task[]> {
  const map = new Map<string, Task[]>();

  for (const col of COLUMNS) {
    map.set(col.id, []);
  }

  for (const task of tasks) {
    if (!showHidden && HIDDEN_STATUSES.includes(task.status)) {
      continue;
    }

    let placed = false;
    for (const col of COLUMNS) {
      if (col.statuses.includes(task.status)) {
        map.get(col.id)!.push(task);
        placed = true;
        break;
      }
    }

    if (!placed && showHidden) {
      // deferred/cancelled go into a hidden column when toggled on
      // We don't have a column for them in the main layout; skip for now
    }
  }

  return map;
}

interface KanbanBoardProps {
  workplanId: string;
  phaseId?: string;
  title?: string;
  onTaskClick?: (task: Task) => void;
}

export function KanbanBoard({ workplanId, phaseId, title, onTaskClick }: KanbanBoardProps) {
  const [showHidden, setShowHidden] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const handleTaskClick = useCallback(
    (task: Task) => {
      setSelectedTaskId(task.id);
      onTaskClick?.(task);
    },
    [onTaskClick],
  );

  const handleSSEEvent = useCallback(
    (event: MessageEvent) => {
      let data: { task_id?: string } = {};
      try {
        data = JSON.parse(event.data);
      } catch {
        // ignore malformed events
      }
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      if (data.task_id) {
        queryClient.invalidateQueries({ queryKey: ['task', data.task_id] });
      }
    },
    [queryClient, workplanId],
  );

  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?workplan=${workplanId}`,
    onEvent: handleSSEEvent,
    enabled: !!workplanId,
  });

  const {
    data: workplanData,
    isLoading: workplanLoading,
    error: workplanError,
  } = useWorkplan(workplanId);

  const workplanTasks = useTasksByWorkplan(workplanId);
  const phaseTasks = useTasksByPhase(phaseId ?? '');
  const tasksQuery = phaseId ? phaseTasks : workplanTasks;
  const { data: tasksData, isLoading: tasksLoading, error: tasksError, refetch } = tasksQuery;

  const isLoading = workplanLoading || tasksLoading;
  const error = workplanError || tasksError;

  if (isLoading) {
    return <div className="loading">Loading board...</div>;
  }

  if (error) {
    return (
      <div className="error">
        Failed to load board. <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  const tasks = tasksData?.results ?? [];
  const columnTasks = groupTasksByColumn(tasks, showHidden);
  const totalTasks = tasks.filter((t) => !HIDDEN_STATUSES.includes(t.status)).length;

  return (
    <div className="kanban-board">
      <div className="kanban-board-header">
        <div className="kanban-board-title">
          <h1>{title || workplanData?.name || workplanId}</h1>
          <LiveIndicator status={sseStatus} />
        </div>
        <div className="kanban-board-controls">
          <span className="task-count">{totalTasks} tasks</span>
          <label className="show-hidden-toggle">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => setShowHidden(e.target.checked)}
            />
            Show deferred &amp; cancelled
          </label>
        </div>
      </div>
      {tasks.length === 0 ? (
        <div className="kanban-empty">No tasks yet.</div>
      ) : (
        <div className="kanban-columns">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col.id}
              column={col}
              tasks={columnTasks.get(col.id) ?? []}
              onTaskClick={handleTaskClick}
            />
          ))}
        </div>
      )}
      <TaskDetail
        taskId={selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
      />
    </div>
  );
}
