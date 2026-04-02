import { useState } from 'react';
import { useAuth } from '../App';
import {
  useExternalIdentities,
  useLinkIdentity,
  useUnlinkIdentity,
  useSessionHistory,
} from '../api/users';

const TYPE_BADGE: Record<string, string> = {
  human: 'bg-blue-100 text-blue-700',
  agent: 'bg-purple-100 text-purple-700',
  service: 'bg-amber-100 text-amber-700',
};

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-primary text-on-primary',
  member: 'bg-surface-container-high text-on-surface',
  viewer: 'bg-surface-container text-on-surface-variant',
};

export function ProfilePage() {
  const auth = useAuth();
  const { data: identityData, isLoading: idLoading } = useExternalIdentities();
  const { data: sessionData, isLoading: sessLoading } = useSessionHistory();
  const unlinkMutation = useUnlinkIdentity();
  const linkMutation = useLinkIdentity();

  const [showLinkForm, setShowLinkForm] = useState(false);
  const [linkProvider, setLinkProvider] = useState('');
  const [linkExternalId, setLinkExternalId] = useState('');
  const [linkWorkspaceId, setLinkWorkspaceId] = useState('');

  const identities = identityData?.results ?? [];
  const sessions = sessionData?.results ?? [];

  function handleLink(e: React.FormEvent) {
    e.preventDefault();
    if (!linkProvider || !linkExternalId) return;
    linkMutation.mutate(
      { provider: linkProvider, external_id: linkExternalId, workspace_id: linkWorkspaceId || undefined },
      {
        onSuccess: () => {
          setShowLinkForm(false);
          setLinkProvider('');
          setLinkExternalId('');
          setLinkWorkspaceId('');
        },
      },
    );
  }

  return (
    <div className="pt-8 px-8 pb-12 max-w-4xl">
      <h1 className="text-3xl font-headline font-extrabold text-on-surface mb-1">Profile</h1>
      <p className="text-sm text-on-surface-variant mb-8">Your identity and platform access.</p>

      {/* Identity Card */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] mb-6">
        <div className="grid grid-cols-2 gap-y-4 gap-x-8">
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Username</div>
            <div className="text-sm font-semibold text-on-surface">{auth.username}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Account Type</div>
            <span className={`inline-block px-2.5 py-0.5 rounded text-[11px] font-bold ${TYPE_BADGE[auth.userType] || TYPE_BADGE.human}`}>
              {auth.userType || 'human'}
            </span>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Role</div>
            <span className={`inline-block px-2.5 py-0.5 rounded text-[11px] font-bold ${auth.isStaff ? 'bg-tertiary-fixed text-on-tertiary-fixed' : 'bg-surface-container text-on-surface-variant'}`}>
              {auth.isStaff ? 'Staff' : 'User'}
            </span>
          </div>
        </div>
      </div>

      {/* Project Memberships */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] mb-6">
        <h2 className="text-lg font-headline font-bold text-on-surface mb-4">Project Memberships</h2>
        {auth.projects.length === 0 ? (
          <p className="text-sm text-on-surface-variant">Not a member of any projects.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant border-b border-surface-container">
                <th className="text-left pb-2">Project</th>
                <th className="text-left pb-2">Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {auth.projects.map((p) => (
                <tr key={p.project_id}>
                  <td className="py-2.5 font-medium text-on-surface">{p.project_id}</td>
                  <td className="py-2.5">
                    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold ${ROLE_BADGE[p.role] || ROLE_BADGE.member}`}>
                      {p.role}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Linked Accounts */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] mb-6">
        <h2 className="text-lg font-headline font-bold text-on-surface mb-4">Linked Accounts</h2>
        {idLoading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-surface-container-high rounded w-48" />
            <div className="h-4 bg-surface-container-high rounded w-40" />
          </div>
        ) : identities.length === 0 && !showLinkForm ? (
          <p className="text-sm text-on-surface-variant mb-3">No linked accounts.</p>
        ) : (
          <div className="divide-y divide-surface-container mb-3">
            {identities.map((id) => (
              <div key={id.id} className="flex items-center justify-between py-2.5">
                <div>
                  <span className="text-xs font-bold text-on-surface-variant uppercase mr-2">{id.provider}</span>
                  <span className="text-sm text-on-surface font-medium">{id.external_id}</span>
                  {id.workspace_id && (
                    <span className="text-xs text-on-surface-variant ml-2">({id.workspace_id})</span>
                  )}
                </div>
                <button
                  onClick={() => unlinkMutation.mutate(id.id)}
                  className="text-xs text-error hover:underline font-medium"
                  disabled={unlinkMutation.isPending}
                >
                  Unlink
                </button>
              </div>
            ))}
          </div>
        )}
        {showLinkForm ? (
          <form onSubmit={handleLink} className="mt-3 space-y-3 p-4 bg-surface-container-low rounded-lg">
            <div className="grid grid-cols-3 gap-3">
              <input
                placeholder="Provider (e.g. slack)"
                value={linkProvider}
                onChange={(e) => setLinkProvider(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg"
                required
              />
              <input
                placeholder="External ID"
                value={linkExternalId}
                onChange={(e) => setLinkExternalId(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg"
                required
              />
              <input
                placeholder="Workspace ID (optional)"
                value={linkWorkspaceId}
                onChange={(e) => setLinkWorkspaceId(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-lowest border border-outline-variant rounded-lg"
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold" disabled={linkMutation.isPending}>
                Save
              </button>
              <button type="button" onClick={() => setShowLinkForm(false)} className="px-4 py-2 text-sm text-on-surface-variant hover:text-on-surface">
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            onClick={() => setShowLinkForm(true)}
            className="flex items-center gap-1 text-sm font-bold text-primary hover:underline"
          >
            <span className="material-symbols-outlined text-base">add</span>
            Link Account
          </button>
        )}
      </div>

      {/* Session History */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)]">
        <h2 className="text-lg font-headline font-bold text-on-surface mb-4">Session History</h2>
        {sessLoading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-surface-container-high rounded w-64" />
            <div className="h-4 bg-surface-container-high rounded w-56" />
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-on-surface-variant">No session history.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant border-b border-surface-container">
                <th className="text-left pb-2">Project</th>
                <th className="text-left pb-2">Role</th>
                <th className="text-left pb-2">Channel</th>
                <th className="text-left pb-2">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {sessions.slice(0, 20).map((s) => (
                <tr key={s.id}>
                  <td className="py-2.5 font-medium">{s.project_id}</td>
                  <td className="py-2.5">{s.role}</td>
                  <td className="py-2.5">{s.channel || '--'}</td>
                  <td className="py-2.5 text-on-surface-variant">{new Date(s.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
