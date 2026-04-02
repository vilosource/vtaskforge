import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useUsers, useCreateServiceAccount } from '../api/users';

const TYPE_BADGE: Record<string, string> = {
  human: 'bg-blue-100 text-blue-700',
  agent: 'bg-purple-100 text-purple-700',
  service: 'bg-amber-100 text-amber-700',
};

export function AdminUsersPage() {
  const { isStaff } = useAuth();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const { data, isLoading } = useUsers(search || undefined, typeFilter || undefined);
  const createSA = useCreateServiceAccount();

  const [showSAForm, setShowSAForm] = useState(false);
  const [saName, setSaName] = useState('');
  const [createdToken, setCreatedToken] = useState('');

  if (!isStaff) return <Navigate to="/" replace />;

  const users = data?.results ?? [];

  function handleCreateSA(e: React.FormEvent) {
    e.preventDefault();
    if (!saName) return;
    createSA.mutate(saName, {
      onSuccess: (result) => {
        setCreatedToken(result.token);
        setSaName('');
      },
    });
  }

  return (
    <div className="pt-8 px-8 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface">Users</h1>
          <p className="text-sm text-on-surface-variant mt-1">Manage human and synthetic identities.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">search</span>
            <input
              type="text"
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg w-56 focus:ring-2 focus:ring-primary"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg"
          >
            <option value="">All Types</option>
            <option value="human">Human</option>
            <option value="agent">Agent</option>
            <option value="service">Service</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-surface-container-high rounded animate-pulse" />
            ))}
          </div>
        ) : users.length === 0 ? (
          <div className="p-10 text-center">
            <span className="material-symbols-outlined text-on-surface-variant text-3xl mb-2">person_off</span>
            <p className="text-sm text-on-surface-variant">No users found.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant border-b border-surface-container">
                <th className="text-left px-6 py-3">Username</th>
                <th className="text-left px-6 py-3">Type</th>
                <th className="text-left px-6 py-3">Staff</th>
                <th className="text-left px-6 py-3">Last Login</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-surface-container-low/40 transition-colors cursor-pointer">
                  <td className="px-6 py-3">
                    <Link to={`/admin/users/${u.id}`} className="font-semibold text-on-surface hover:text-primary">
                      {u.username}
                    </Link>
                  </td>
                  <td className="px-6 py-3">
                    <span className={`inline-block px-2.5 py-0.5 rounded text-[11px] font-bold ${TYPE_BADGE[u.user_type] || ''}`}>
                      {u.user_type}
                    </span>
                  </td>
                  <td className="px-6 py-3">
                    {u.is_staff ? (
                      <span className="material-symbols-outlined text-tertiary text-lg">check_circle</span>
                    ) : (
                      <span className="text-on-surface-variant">--</span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-on-surface-variant">
                    {u.last_login ? new Date(u.last_login).toLocaleDateString() : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Service Account */}
      <div className="mt-6">
        {createdToken && (
          <div className="mb-4 p-4 bg-tertiary-fixed rounded-lg">
            <div className="text-sm font-bold text-on-tertiary-fixed mb-1">Service account created</div>
            <div className="text-xs font-mono bg-surface-container-lowest p-2 rounded select-all">{createdToken}</div>
            <div className="text-xs text-on-tertiary-fixed-variant mt-1">Save this token — it cannot be retrieved later.</div>
            <button onClick={() => setCreatedToken('')} className="text-xs text-on-tertiary-fixed font-bold mt-2 hover:underline">Dismiss</button>
          </div>
        )}
        {showSAForm ? (
          <form onSubmit={handleCreateSA} className="flex items-center gap-3">
            <input
              placeholder="Account name (e.g. ci-bot)"
              value={saName}
              onChange={(e) => setSaName(e.target.value)}
              className="px-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg w-64"
              required
            />
            <button type="submit" className="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold" disabled={createSA.isPending}>
              Create
            </button>
            <button type="button" onClick={() => setShowSAForm(false)} className="text-sm text-on-surface-variant hover:text-on-surface">
              Cancel
            </button>
          </form>
        ) : (
          <button
            onClick={() => setShowSAForm(true)}
            className="flex items-center gap-1 text-sm font-bold text-primary hover:underline"
          >
            <span className="material-symbols-outlined text-base">add</span>
            Create Service Account
          </button>
        )}
      </div>
    </div>
  );
}
