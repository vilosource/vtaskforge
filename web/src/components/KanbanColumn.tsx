import type { Task } from '../api/tasks';
import { TaskCard } from './TaskCard';

export interface ColumnConfig {
  id: string;
  label: string;
  statuses: string[];
  color: string;
}

interface KanbanColumnProps {
  column: ColumnConfig;
  tasks: Task[];
  onTaskClick?: (task: Task) => void;
}

const DOT_COLORS: Record<string, string> = {
  grey: 'bg-outline',
  blue: 'bg-primary',
  'blue-highlight': 'bg-blue-600',
  red: 'bg-error',
  green: 'bg-tertiary',
  yellow: 'bg-yellow-500',
};

export function KanbanColumn({ column, tasks, onTaskClick }: KanbanColumnProps) {
  return (
    <div className="flex-1 min-w-[260px] flex flex-col bg-surface-container-low/50 rounded-xl overflow-hidden" data-column={column.id}>
      <div className="px-4 py-3 flex items-center justify-between border-b border-outline-variant/20 bg-surface-container-lowest/50">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${DOT_COLORS[column.color] ?? 'bg-outline'}`} />
          <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">{column.label}</span>
        </div>
        <span className="bg-surface-container-highest text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded">{tasks.length}</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onClick={onTaskClick} />
        ))}
        {tasks.length === 0 && (
          <div className="text-center text-xs text-on-surface-variant/50 py-8">No tasks</div>
        )}
      </div>
    </div>
  );
}
