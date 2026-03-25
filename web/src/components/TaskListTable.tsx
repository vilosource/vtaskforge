import { useState, type ReactNode } from 'react';
import type { Task } from '../api/tasks';
import { Pagination } from './Pagination';

// Reuse the same badge mapping as TaskCard
const STATUS_BADGE_COLORS: Record<string, string> = {
  draft: 'badge-draft',
  pending_start_review: 'badge-review',
  pending_completion_review: 'badge-review',
  todo: 'badge-ready',
  doing: 'badge-in-progress',
  changes_requested: 'badge-attention',
  needs_attention: 'badge-attention',
  blocked: 'badge-attention',
  done: 'badge-done',
  deferred: 'badge-deferred',
  cancelled: 'badge-cancelled',
};

// --- Column definition ---

export interface ColumnDef {
  key: string;
  label: string;
  width?: string;
  render?: (task: Task) => ReactNode;
}

// --- Built-in renderers ---

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function renderStatus(task: Task): ReactNode {
  return (
    <span className={`badge ${STATUS_BADGE_COLORS[task.status] ?? ''}`}>
      {task.status.replace(/_/g, ' ')}
    </span>
  );
}

function renderLabels(task: Task): ReactNode {
  if (!task.labels || task.labels.length === 0) return <span className="task-list-empty">—</span>;
  return (
    <div className="task-list-labels">
      {task.labels.map((label) => (
        <span key={label} className="task-list-label">{label}</span>
      ))}
    </div>
  );
}

function renderClaimedBy(task: Task): ReactNode {
  return task.claimed_by
    ? <span className="task-list-agent">{task.claimed_by}</span>
    : <span className="task-list-empty">—</span>;
}

function renderTime(field: 'created_at' | 'updated_at') {
  return (task: Task) => {
    const value = task[field];
    return value ? <span className="task-list-time">{relativeTime(value)}</span> : <span className="task-list-empty">—</span>;
  };
}

const BUILT_IN_RENDERERS: Record<string, (task: Task) => ReactNode> = {
  status: renderStatus,
  labels: renderLabels,
  claimed_by: renderClaimedBy,
  created_at: renderTime('created_at'),
  updated_at: renderTime('updated_at'),
};

function renderCell(task: Task, col: ColumnDef): ReactNode {
  if (col.render) return col.render(task);
  if (BUILT_IN_RENDERERS[col.key]) return BUILT_IN_RENDERERS[col.key](task);
  // Default: render as text
  const value = (task as unknown as Record<string, unknown>)[col.key];
  if (value == null) return <span className="task-list-empty">—</span>;
  return String(value);
}

// --- Column presets ---

export const BACKLOG_COLUMNS: ColumnDef[] = [
  { key: 'status', label: 'Status', width: '140px' },
  { key: 'title', label: 'Title' },
  { key: 'labels', label: 'Labels', width: '160px' },
  { key: 'updated_at', label: 'Updated', width: '100px' },
];

export const SEARCH_COLUMNS: ColumnDef[] = [
  { key: 'status', label: 'Status', width: '140px' },
  { key: 'title', label: 'Title' },
  { key: 'labels', label: 'Labels', width: '160px' },
  { key: 'claimed_by', label: 'Claimed by', width: '140px' },
  { key: 'updated_at', label: 'Updated', width: '100px' },
];

// --- Component ---

interface TaskListTableProps {
  tasks: Task[];
  columns: ColumnDef[];
  onTaskClick?: (task: Task) => void;
  pageSize?: number;
  emptyMessage?: string;
  loading?: boolean;
}

export function TaskListTable({
  tasks,
  columns,
  onTaskClick,
  pageSize = 10,
  emptyMessage = 'No tasks',
  loading = false,
}: TaskListTableProps) {
  const [page, setPage] = useState(1);
  const total = tasks.length;
  const start = (page - 1) * pageSize;
  const pageTasks = tasks.slice(start, start + pageSize);

  if (loading) return <div className="loading">Loading...</div>;

  if (total === 0) {
    return <div className="task-list-empty-state">{emptyMessage}</div>;
  }

  return (
    <div className="task-list">
      <table className="task-list-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={col.width ? { width: col.width } : undefined}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pageTasks.map((task) => (
            <tr
              key={task.id}
              className="task-list-row"
              onClick={() => onTaskClick?.(task)}
              role={onTaskClick ? 'button' : undefined}
              tabIndex={onTaskClick ? 0 : undefined}
              onKeyDown={(e) => {
                if (onTaskClick && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onTaskClick(task);
                }
              }}
            >
              {columns.map((col) => (
                <td key={col.key} className={`task-list-cell task-list-cell-${col.key}`}>
                  {renderCell(task, col)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {total > pageSize && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
