import { useState, type ReactNode } from 'react';
import type { Task } from '../api/tasks';
import { Pagination } from './Pagination';

// Tailwind badge classes for each status
const STATUS_BADGE_CLASSES: Record<string, string> = {
  draft: 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40',
  pending_start_review: 'bg-yellow-50 text-yellow-800 border border-yellow-300',
  pending_completion_review: 'bg-yellow-50 text-yellow-800 border border-yellow-300',
  todo: 'bg-blue-50 text-blue-700 border border-blue-200',
  doing: 'bg-blue-100 text-blue-800 border border-blue-300',
  changes_requested: 'bg-red-50 text-red-700 border border-red-200',
  needs_attention: 'bg-red-50 text-red-700 border border-red-200',
  blocked: 'bg-red-50 text-red-700 border border-red-200',
  done: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  deferred: 'bg-slate-100 text-slate-600 border border-slate-300',
  cancelled: 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40',
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
    <span className={`inline-flex items-center text-[11px] font-semibold leading-none px-2 py-1 rounded whitespace-nowrap uppercase tracking-wide ${STATUS_BADGE_CLASSES[task.status] ?? 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40'}`}>
      {task.status.replace(/_/g, ' ')}
    </span>
  );
}

function renderLabels(task: Task): ReactNode {
  if (!task.labels || task.labels.length === 0) return <span className="text-on-surface-variant/40">—</span>;
  return (
    <div className="flex gap-1 flex-wrap">
      {task.labels.map((label) => (
        <span key={label} className="bg-secondary-container text-on-secondary-container text-[11px] font-semibold px-2 py-0.5 rounded-full">{label}</span>
      ))}
    </div>
  );
}

function renderClaimedBy(task: Task): ReactNode {
  return task.claimed_by
    ? <span className="font-mono text-xs text-on-surface-variant">{task.claimed_by}</span>
    : <span className="text-on-surface-variant/40">—</span>;
}

function renderTime(field: 'created_at' | 'updated_at') {
  return (task: Task) => {
    const value = task[field];
    return value ? <span className="text-xs text-on-surface-variant">{relativeTime(value)}</span> : <span className="text-on-surface-variant/40">—</span>;
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
  if (value == null) return <span className="text-on-surface-variant/40">—</span>;
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

  if (loading) return <div className="flex items-center justify-center p-12 text-on-surface-variant">Loading...</div>;

  if (total === 0) {
    return <div className="flex items-center justify-center p-12 text-on-surface-variant text-sm">{emptyMessage}</div>;
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow overflow-hidden mt-4">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-surface-container-low/20">
            {columns.map((col) => (
              <th
                key={col.key}
                className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4"
                style={col.width ? { width: col.width } : undefined}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-container">
          {pageTasks.map((task) => (
            <tr
              key={task.id}
              className="hover:bg-surface-container-low/40 transition-colors cursor-pointer"
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
                <td
                  key={col.key}
                  className={`px-6 py-3 ${
                    col.key === 'title' ? 'text-sm font-semibold truncate max-w-[400px] text-on-surface' : ''
                  }`}
                >
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
