import { useParams, Link } from 'react-router-dom';
import { useAgent, useAgentTasks } from '../api/agents';
import { Breadcrumb } from '../components/Breadcrumb';

const STATUS_COLORS: Record<string, string> = {
  online: '#4caf50',
  offline: '#9e9e9e',
  busy: '#ff9800',
  stale: '#f44336',
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

export function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: agent, isLoading, error } = useAgent(id);
  const { data: tasksData } = useAgentTasks(id);
  const tasks = tasksData?.results ?? [];

  if (isLoading) {
    return <div className="loading">Loading agent...</div>;
  }

  if (error || !agent) {
    return <div className="error">Agent not found.</div>;
  }

  const effectiveStatus = agent.effective_status;

  return (
    <div className="workplan-detail">
      <Breadcrumb segments={[
        { label: 'Agents', to: '/agents' },
        { label: agent.name },
      ]} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span
          style={{
            display: 'inline-block',
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: STATUS_COLORS[effectiveStatus] ?? '#9e9e9e',
          }}
        />
        <h1 style={{ margin: 0 }}>{agent.name}</h1>
        <span className={`badge badge-${effectiveStatus}`}>{effectiveStatus}</span>
      </div>

      <div style={{ display: 'flex', gap: 32, marginBottom: 24, flexWrap: 'wrap' }}>
        <div>
          <strong>Tags:</strong>{' '}
          {agent.tags.length > 0
            ? agent.tags.map((t) => <span key={t} className="badge" style={{ marginRight: 4 }}>{t}</span>)
            : 'None'}
        </div>
        <div><strong>Last Heartbeat:</strong> {relativeTime(agent.last_heartbeat)}</div>
        <div><strong>Registered:</strong> {relativeTime(agent.registered_at)}</div>
        <div><strong>Completed:</strong> {agent.tasks_completed}</div>
        <div><strong>Failed:</strong> {agent.tasks_failed}</div>
      </div>

      {agent.current_task && (
        <div style={{ marginBottom: 24, padding: 12, background: 'var(--color-surface, #f5f5f5)', borderRadius: 6 }}>
          <strong>Current Task: </strong>
          <Link to={`/tasks/${agent.current_task.id}`}>{agent.current_task.title}</Link>
          <span className={`badge badge-${agent.current_task.status}`} style={{ marginLeft: 8 }}>
            {agent.current_task.status}
          </span>
        </div>
      )}

      <h2>Task History</h2>
      {tasks.length === 0 ? (
        <div className="empty">No tasks claimed by this agent.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id}>
                <td><Link to={`/tasks/${task.id}`}>{task.title}</Link></td>
                <td><span className={`badge badge-${task.status}`}>{task.status}</span></td>
                <td>{relativeTime(task.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
