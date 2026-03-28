import { useState } from 'react';
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

function getInitials(name: string): string {
  return name
    .split(/[\s-_]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

const SUMMARY_CARDS = [
  { key: 'total', label: 'Total Agents', icon: 'groups', iconBg: 'bg-primary-fixed text-on-primary-fixed' },
  { key: 'online', label: 'Online', icon: 'sensors', iconBg: 'bg-tertiary-container text-on-tertiary-container' },
  { key: 'busy', label: 'Busy', icon: 'memory', iconBg: 'bg-blue-100 text-blue-700' },
  { key: 'stale', label: 'Stale', icon: 'history', iconBg: 'bg-secondary-fixed text-on-secondary-fixed' },
  { key: 'offline', label: 'Offline', icon: 'sensors_off', iconBg: 'bg-error-container text-error' },
] as const;

type FilterTab = 'all' | 'online' | 'busy' | 'stale' | 'offline';

function FleetSummary({ agents }: { agents: Agent[] }) {
  const counts: Record<string, number> = {
    total: agents.length,
    online: agents.filter((a) => a.effective_status === 'online').length,
    busy: agents.filter((a) => a.effective_status === 'busy').length,
    stale: agents.filter((a) => a.effective_status === 'stale').length,
    offline: agents.filter((a) => a.effective_status === 'offline').length,
  };

  return (
    <div className="grid grid-cols-5 gap-6 mb-8">
      {SUMMARY_CARDS.map((c) => (
        <div key={c.key} className="bg-surface-container-lowest p-6 rounded-xl shadow flex flex-col gap-4">
          <span className={`${c.iconBg} w-10 h-10 rounded-[50%] inline-flex items-center justify-center`}>
            <span className="material-symbols-outlined text-xl">{c.icon}</span>
          </span>
          <div>
            <div className="text-3xl font-headline font-extrabold text-on-surface">{counts[c.key]}</div>
            <div className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mt-1">{c.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function AgentRow({ agent }: { agent: Agent }) {
  const es = agent.effective_status;
  const pillClass = STATUS_PILL[es] ?? 'bg-surface-container text-on-surface-variant';
  const dotClass = STATUS_DOT[es] ?? 'bg-outline';

  return (
    <tr className="border-b border-outline-variant/40 hover:bg-surface-container-low/50 transition-colors">
      {/* Name + avatar */}
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[50%] bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-sm font-headline font-bold shrink-0">
            {getInitials(agent.name)}
          </div>
          <div className="min-w-0">
            <Link to={`/agents/${agent.id}`} className="text-sm font-semibold text-on-surface hover:text-primary transition-colors block truncate">
              {agent.name}
            </Link>
            <span className="text-[10px] text-on-surface-variant font-mono truncate block">{agent.id}</span>
          </div>
        </div>
      </td>
      {/* Status pill */}
      <td className="py-3 px-4">
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[999px] text-xs font-semibold ${pillClass}`}>
          <span className={`w-1.5 h-1.5 rounded-[50%] ${dotClass} ${es === 'online' ? 'animate-pulse' : ''}`} />
          {es}
        </span>
      </td>
      {/* Tags */}
      <td className="py-3 px-4">
        <div className="flex flex-wrap gap-1.5">
          {agent.tags.length > 0
            ? agent.tags.map((t) => (
                <span key={t} className="inline-block bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded-[999px] text-[11px] font-medium">
                  {t}
                </span>
              ))
            : <span className="text-on-surface-variant text-sm">{'\u2014'}</span>}
        </div>
      </td>
      {/* Current task */}
      <td className="py-3 px-4">
        {agent.current_task ? (
          <Link to={`/tasks/${agent.current_task.id}`} className="text-sm text-primary hover:underline truncate block max-w-[220px]">
            {agent.current_task.title}
          </Link>
        ) : (
          <span className="text-sm text-on-surface-variant italic">idle</span>
        )}
      </td>
      {/* Stats */}
      <td className="py-3 px-4">
        <div className="flex items-center gap-1.5 text-sm">
          <span className="text-tertiary font-semibold">{agent.tasks_completed}</span>
          <span className="text-outline-variant">/</span>
          <span className={agent.tasks_failed > 0 ? 'text-error font-semibold' : 'text-on-surface-variant'}>{agent.tasks_failed}</span>
        </div>
      </td>
      {/* Heartbeat */}
      <td className="py-3 px-4">
        <span className={`text-sm ${agent.last_heartbeat ? 'text-on-surface' : 'text-on-surface-variant italic'}`}>
          {relativeTime(agent.last_heartbeat)}
        </span>
      </td>
      {/* Actions */}
      <td className="py-3 px-4">
        <Link to={`/agents/${agent.id}`} className="text-on-surface-variant hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-xl">more_horiz</span>
        </Link>
      </td>
    </tr>
  );
}

export function AgentList() {
  const { data, isLoading, error, refetch } = useAgents();
  const [filter, setFilter] = useState<FilterTab>('all');

  if (isLoading) {
    return (
      <div className="px-8 pb-12 pt-6">
        <div className="flex items-center justify-center py-20 text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin mr-3 text-2xl">progress_activity</span>
          Loading agents...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-8 pb-12 pt-6">
        <div className="bg-error-container text-on-error-container p-4 rounded-xl flex items-center gap-3">
          <span className="material-symbols-outlined">error</span>
          Failed to load agents.
          <button onClick={() => refetch()} className="ml-auto px-4 py-1.5 bg-error text-on-error rounded-lg text-sm font-medium hover:opacity-90 transition-opacity">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const agents = data?.results ?? [];
  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'online', label: 'Online' },
    { key: 'busy', label: 'Busy' },
    { key: 'stale', label: 'Stale' },
    { key: 'offline', label: 'Offline' },
  ];
  const filtered = filter === 'all' ? agents : agents.filter((a) => a.effective_status === filter);

  return (
    <div className="px-8 pb-12 pt-6">
      <Breadcrumb segments={[{ label: 'Agents' }]} />

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-headline font-extrabold tracking-tight text-on-surface">Agent Fleet</h1>
        <p className="text-on-surface-variant mt-1">Registered agents and their current status</p>
      </div>

      {agents.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-xl shadow p-12 text-center">
          <span className="material-symbols-outlined text-5xl text-outline-variant mb-4 block">smart_toy</span>
          <p className="text-on-surface-variant text-lg">No agents registered.</p>
        </div>
      ) : (
        <>
          <FleetSummary agents={agents} />

          {/* Table card */}
          <div className="bg-surface-container-lowest rounded-xl shadow">
            {/* Filter tabs */}
            <div className="flex items-center gap-1 px-4 pt-4 pb-2 border-b border-outline-variant/30">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                    filter === tab.key
                      ? 'bg-primary text-on-primary'
                      : 'text-on-surface-variant hover:bg-surface-container-high'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
              <span className="ml-auto text-xs text-on-surface-variant">{filtered.length} agent{filtered.length !== 1 ? 's' : ''}</span>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-outline-variant/30">
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4">Agent</th>
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4">Status</th>
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4">Tags</th>
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4">Current Task</th>
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4">Done / Fail</th>
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4">Heartbeat</th>
                    <th className="text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant py-3 px-4 w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((agent) => (
                    <AgentRow key={agent.id} agent={agent} />
                  ))}
                </tbody>
              </table>
            </div>

            {filtered.length === 0 && (
              <div className="py-8 text-center text-on-surface-variant text-sm">
                No {filter} agents.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
