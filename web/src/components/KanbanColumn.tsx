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

export function KanbanColumn({ column, tasks, onTaskClick }: KanbanColumnProps) {
  return (
    <div className={`kanban-column kanban-column-${column.color}`} data-column={column.id}>
      <div className="kanban-column-header">
        <span className="kanban-column-label">{column.label}</span>
        <span className="kanban-column-count">{tasks.length}</span>
      </div>
      <div className="kanban-column-body">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onClick={onTaskClick} />
        ))}
        {tasks.length === 0 && (
          <div className="kanban-column-empty">No tasks</div>
        )}
      </div>
    </div>
  );
}
