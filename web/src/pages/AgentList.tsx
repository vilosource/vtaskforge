import { Link } from 'react-router-dom';
import { useAgents, type Agent } from '../api/agents';
import { Breadcrumb } from '../components/Breadcrumb';

function relativeTime(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    online: 'var(--color-done)',
    busy: 'var(--color-review)',
    stale: 'var(--color-attention)',
    offline: 'var(--color-draft)',
  };
  return (
    <span
      className={status === 'online' ? 'agent-dot agent-dot--pulse' : 'agent-dot'}
      style={{ background: colors[status] ?? 'var(--color-draft)' }}
      title={status}
    />
  );
}

function FleetSummary({ agents }: { agents: Agent[] }) {
  const total = agents.length;
  const online = agents.filter((a) => a.effective_status === 'online').length;
  const busy = agents.filter((a) => a.effective_status === 'busy').length;
  const stale = agents.filter((a) => a.effective_status === 'stale').length;
  const offline = agents.filter((a) => a.effective_status === 'offline').length;

  return (
    <div className="agent-summary">
      <div className="agent-summary-card">
        <div className="agent-summary-value">{total}</div>
        <div className="agent-summary-label">Total</div>
      </div>
      <div className="agent-summary-card agent-summary-card--online">
        <div className="agent-summary-value">{online}</div>
        <div className="agent-summary-label">Online</div>
      </div>
      <div className="agent-summary-card agent-summary-card--busy">
        <div className="agent-summary-value">{busy}</div>
        <div className="agent-summary-label">Busy</div>
      </div>
      <div className="agent-summary-card agent-summary-card--stale">
        <div className="agent-summary-value">{stale}</div>
        <div className="agent-summary-label">Stale</div>
      </div>
      <div className="agent-summary-card agent-summary-card--offline">
        <div className="agent-summary-value">{offline}</div>
        <div className="agent-summary-label">Offline</div>
      </div>
    </div>
  );
}

function AgentRow({ agent }: { agent: Agent }) {
  const es = agent.effective_status;

  return (
    <tr>
      <td>
        <StatusDot status={es} />
        <Link to={`/agents/${agent.id}`}>{agent.name}</Link>
      </td>
      <td>
        <span className={`badge badge-agent-${es}`}>{es}</span>
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
        ) : (
          <span className="agent-idle">idle</span>
        )}
      </td>
      <td>
        <span className={agent.last_heartbeat ? '' : 'agent-idle'}>
          {relativeTime(agent.last_heartbeat)}
        </span>
      </td>
      <td className="agent-stat">{agent.tasks_completed}</td>
      <td className="agent-stat">
        {agent.tasks_failed > 0 ? (
          <span style={{ color: 'var(--color-attention)' }}>{agent.tasks_failed}</span>
        ) : (
          agent.tasks_failed
        )}
      </td>
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
        <>
          <FleetSummary agents={agents} />
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
        </>
      )}
    </div>
  );
}
