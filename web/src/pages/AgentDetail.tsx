import { useParams, Link } from 'react-router-dom';
import { useAgent, useAgentTasks } from '../api/agents';
import { Breadcrumb } from '../components/Breadcrumb';

const STATUS_PILL: Record<string, string> = {
  online: 'bg-tertiary-container text-on-tertiary-container',
  busy: 'bg-blue-100 text-blue-700',
  stale: 'bg-error-container text-error',
  offline: 'bg-error-container text-error',
};

const STATUS_DOT: Record<string, string> = {
  online: 'bg-tertiary-container',
  busy: 'bg-blue-400',
  stale: 'bg-error',
  offline: 'bg-error-container',
};

const TASK_STATUS_PILL: Record<string, string> = {
  todo: 'bg-primary-fixed text-on-primary-fixed',
  doing: 'bg-blue-100 text-blue-700',
  done: 'bg-tertiary-container text-on-tertiary-container',
  draft: 'bg-surface-container-high text-on-surface-variant',
  blocked: 'bg-error-container text-error',
  cancelled: 'bg-surface-container-high text-on-surface-variant',
  changes_requested: 'bg-error-container text-error',
  needs_attention: 'bg-error-container text-error',
  pending_start_review: 'bg-secondary-container text-on-secondary-container',
  pending_completion_review: 'bg-secondary-container text-on-secondary-container',
  deferred: 'bg-surface-container-high text-on-surface-variant',
};

function relativeTime(iso: string | null): string {
  if (!iso) return '\u2014';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function getInitials(name: string): string {
  return name
    .split(/[\s-_]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

export function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: agent, isLoading, error } = useAgent(id);
  const { data: tasksData } = useAgentTasks(id);
  const tasks = tasksData?.results ?? [];

  if (isLoading) {
    return (
      <div className="px-8 pb-12 pt-6">
        <div className="flex items-center justify-center py-20 text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin mr-3 text-2xl">progress_activity</span>
          Loading agent...
        </div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="px-8 pb-12 pt-6">
        <div className="bg-error-container text-on-error-container p-4 rounded-xl flex items-center gap-3">
          <span className="material-symbols-outlined">error</span>
          Agent not found.
        </div>
      </div>
    );
  }

  const effectiveStatus = agent.effective_status;
  const pillClass = STATUS_PILL[effectiveStatus] ?? 'bg-surface-container text-on-surface-variant';
  const dotClass = STATUS_DOT[effectiveStatus] ?? 'bg-outline';

  return (
    <div className="px-8 pb-12 pt-6">
      <Breadcrumb segments={[
        { label: 'Agents', to: '/agents' },
        { label: agent.name },
      ]} />

      {/* Agent header */}
      <div className="flex items-center gap-5 mb-8">
        <div className="w-16 h-16 rounded-[50%] bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-xl font-headline font-bold shrink-0">
          {getInitials(agent.name)}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-4xl font-headline font-extrabold tracking-tight text-on-surface m-0">{agent.name}</h1>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-[999px] text-xs font-semibold ${pillClass}`}>
              <span className={`w-1.5 h-1.5 rounded-[50%] ${dotClass} ${effectiveStatus === 'online' ? 'animate-pulse' : ''}`} />
              {effectiveStatus}
            </span>
          </div>
          <p className="text-on-surface-variant text-sm font-mono mt-1">{agent.id}</p>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {/* Tags */}
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
          <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Tags</div>
          <div className="flex flex-wrap gap-1.5">
            {agent.tags.length > 0
              ? agent.tags.map((t) => (
                  <span key={t} className="inline-block bg-secondary-container text-on-secondary-container px-2.5 py-0.5 rounded-[999px] text-xs font-medium">
                    {t}
                  </span>
                ))
              : <span className="text-on-surface-variant text-sm">None</span>}
          </div>
        </div>
        {/* Last Heartbeat */}
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
          <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Last Heartbeat</div>
          <div className="text-2xl font-headline font-extrabold text-on-surface">{relativeTime(agent.last_heartbeat)}</div>
        </div>
        {/* Completed */}
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
          <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Completed</div>
          <div className="text-2xl font-headline font-extrabold text-tertiary">{agent.tasks_completed}</div>
        </div>
        {/* Failed */}
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
          <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Failed</div>
          <div className={`text-2xl font-headline font-extrabold ${agent.tasks_failed > 0 ? 'text-error' : 'text-on-surface'}`}>{agent.tasks_failed}</div>
        </div>
      </div>

      {/* Registered */}
      <div className="text-xs text-on-surface-variant mb-8">
        <span className="material-symbols-outlined text-sm align-middle mr-1">calendar_today</span>
        Registered {relativeTime(agent.registered_at)}
      </div>

      {/* Current task */}
      {agent.current_task && (
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow mb-8">
          <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Current Task</div>
          <div className="flex items-center gap-3 flex-wrap">
            <Link to={`/tasks/${agent.current_task.id}`} className="text-primary font-semibold hover:underline">
              {agent.current_task.title}
            </Link>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-[999px] text-[11px] font-semibold ${TASK_STATUS_PILL[agent.current_task.status] ?? 'bg-surface-container-high text-on-surface-variant'}`}>
              {agent.current_task.status}
            </span>
          </div>
        </div>
      )}

      {/* Task History */}
      <div className="bg-surface-container-lowest rounded-xl shadow">
        <div className="px-6 pt-6 pb-3">
          <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant m-0">Task History</h2>
        </div>
        {tasks.length === 0 ? (
          <div className="px-6 pb-6 text-on-surface-variant text-sm">No tasks claimed by this agent.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-6">Title</th>
                  <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-6">Status</th>
                  <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-6">Updated</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} className="border-b border-outline-variant/40 hover:bg-surface-container-low/50 transition-colors last:border-b-0">
                    <td className="py-3 px-6">
                      <Link to={`/tasks/${task.id}`} className="text-sm text-primary hover:underline">
                        {task.title}
                      </Link>
                    </td>
                    <td className="py-3 px-6">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-[999px] text-[11px] font-semibold ${TASK_STATUS_PILL[task.status] ?? 'bg-surface-container-high text-on-surface-variant'}`}>
                        {task.status}
                      </span>
                    </td>
                    <td className="py-3 px-6 text-sm text-on-surface-variant">
                      {relativeTime(task.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
