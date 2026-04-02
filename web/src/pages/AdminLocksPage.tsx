import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useLocks, useReleaseLock } from '../api/users';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function AdminLocksPage() {
  const { isStaff } = useAuth();
  const [projectFilter, setProjectFilter] = useState('');
  const { data, isLoading } = useLocks(projectFilter || undefined);
  const releaseMutation = useReleaseLock();
  const [confirmId, setConfirmId] = useState<number | null>(null);

  if (!isStaff) return <Navigate to="/" replace />;

  const locks = data?.results ?? [];

  function handleRelease(id: number) {
    releaseMutation.mutate(id, { onSuccess: () => setConfirmId(null) });
  }

  return (
    <div className="pt-8 px-8 pb-12">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface">Agent Locks</h1>
          <p className="text-sm text-on-surface-variant mt-1">Active agent session locks across projects.</p>
        </div>
        <input
          type="text"
          placeholder="Filter by project ID..."
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          className="px-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg w-56 focus:ring-2 focus:ring-primary"
        />
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-surface-container-high rounded animate-pulse" />
            ))}
          </div>
        ) : locks.length === 0 ? (
          <div className="p-10 text-center">
            <span className="material-symbols-outlined text-tertiary text-3xl mb-2">lock_open</span>
            <p className="text-sm text-on-surface-variant">No active agent locks.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant border-b border-surface-container">
                <th className="text-left px-6 py-3">Project</th>
                <th className="text-left px-6 py-3">Role</th>
                <th className="text-left px-6 py-3">Held by</th>
                <th className="text-left px-6 py-3">Since</th>
                <th className="text-left px-6 py-3">Last Activity</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {locks.map((lk) => (
                <tr key={lk.id} className="hover:bg-surface-container-low/40 transition-colors">
                  <td className="px-6 py-3 font-medium text-on-surface">{lk.project_id}</td>
                  <td className="px-6 py-3">{lk.role}</td>
                  <td className="px-6 py-3">
                    <span className="inline-block px-2.5 py-0.5 rounded text-[11px] font-bold bg-purple-100 text-purple-700">
                      {lk.user}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-on-surface-variant">{timeAgo(lk.created_at)}</td>
                  <td className="px-6 py-3 text-on-surface-variant">{timeAgo(lk.last_activity)}</td>
                  <td className="px-6 py-3 text-right">
                    {confirmId === lk.id ? (
                      <span className="flex items-center gap-2 justify-end">
                        <span className="text-xs text-on-surface-variant">Release?</span>
                        <button
                          onClick={() => handleRelease(lk.id)}
                          className="px-2 py-1 text-xs font-bold text-error border border-error rounded hover:bg-error hover:text-on-error transition-colors"
                          disabled={releaseMutation.isPending}
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setConfirmId(null)}
                          className="text-xs text-on-surface-variant hover:text-on-surface"
                        >
                          No
                        </button>
                      </span>
                    ) : (
                      <button
                        onClick={() => setConfirmId(lk.id)}
                        className="flex items-center gap-1 text-xs font-bold text-error hover:underline"
                      >
                        <span className="material-symbols-outlined text-sm">lock_open</span>
                        Force Release
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
