import { Link } from 'react-router-dom';
import { useAgents, type Agent } from '../api/agents';
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

function AgentRow({ agent }: { agent: Agent }) {
  const effectiveStatus = agent.effective_status;

  return (
    <tr>
      <td>
        <span
          style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: STATUS_COLORS[effectiveStatus] ?? '#9e9e9e',
            marginRight: 8,
          }}
          title={effectiveStatus}
        />
        <Link to={`/agents/${agent.id}`}>{agent.name}</Link>
      </td>
      <td>
        <span className={`badge badge-${effectiveStatus}`}>
          {effectiveStatus}
        </span>
      </td>
      <td>
        {agent.tags.length > 0
          ? agent.tags.map((t) => (
              <span key={t} className="badge" style={{ marginRight: 4 }}>{t}</span>
            ))
          : '\u2014'}
      </td>
      <td>
        {agent.current_task ? (
          <Link to={`/tasks/${agent.current_task.id}`}>
            {agent.current_task.title}
          </Link>
        ) : '\u2014'}
      </td>
      <td>{relativeTime(agent.last_heartbeat)}</td>
      <td>{agent.tasks_completed}</td>
      <td>{agent.tasks_failed}</td>
    </tr>
  );
}

export function AgentList() {
  const { data, isLoading, error, refetch } = useAgents();

  if (isLoading) {
    return <div className="loading">Loading agents...</div>;
  }

  if (error) {
    return (
      <div className="error">
        Failed to load agents.{' '}
        <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  const agents = data?.results ?? [];

  return (
    <div className="workplan-list">
      <Breadcrumb segments={[{ label: 'Agents' }]} />
      <h1>Agents</h1>

      {agents.length === 0 ? (
        <div className="empty">No agents registered.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Tags</th>
              <th>Current Task</th>
              <th>Last Heartbeat</th>
              <th>Completed</th>
              <th>Failed</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <AgentRow key={agent.id} agent={agent} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
