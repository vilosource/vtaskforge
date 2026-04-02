import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useChannelMappings, useCreateMapping, useDeleteMapping } from '../api/users';

export function AdminChannelMappingsPage() {
  const { isStaff } = useAuth();
  const { data, isLoading } = useChannelMappings();
  const createMutation = useCreateMapping();
  const deleteMutation = useDeleteMapping();

  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState('');
  const [channelId, setChannelId] = useState('');
  const [channelName, setChannelName] = useState('');
  const [projectId, setProjectId] = useState('');

  if (!isStaff) return <Navigate to="/" replace />;

  const mappings = data?.results ?? [];

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!provider || !channelId || !projectId) return;
    createMutation.mutate(
      { provider, channel_id: channelId, project_id: projectId, channel_name: channelName || undefined },
      {
        onSuccess: () => {
          setShowForm(false);
          setProvider('');
          setChannelId('');
          setChannelName('');
          setProjectId('');
        },
      },
    );
  }

  return (
    <div className="pt-8 px-8 pb-12">
      <div className="mb-6">
        <h1 className="text-3xl font-headline font-extrabold text-on-surface">Channel Mappings</h1>
        <p className="text-sm text-on-surface-variant mt-1">Map external channels to projects.</p>
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-surface-container-high rounded animate-pulse" />
            ))}
          </div>
        ) : mappings.length === 0 ? (
          <div className="p-10 text-center">
            <span className="material-symbols-outlined text-on-surface-variant text-3xl mb-2">cable</span>
            <p className="text-sm text-on-surface-variant">No channel mappings configured.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant border-b border-surface-container">
                <th className="text-left px-6 py-3">Provider</th>
                <th className="text-left px-6 py-3">Channel ID</th>
                <th className="text-left px-6 py-3">Name</th>
                <th className="text-left px-6 py-3">Project</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {mappings.map((m) => (
                <tr key={m.id} className="hover:bg-surface-container-low/40 transition-colors">
                  <td className="px-6 py-3">
                    <span className="inline-block px-2.5 py-0.5 rounded text-[11px] font-bold bg-secondary-container text-on-secondary-container">
                      {m.provider}
                    </span>
                  </td>
                  <td className="px-6 py-3 font-mono text-xs">{m.channel_id}</td>
                  <td className="px-6 py-3 text-on-surface">{m.channel_name || '--'}</td>
                  <td className="px-6 py-3 font-medium text-on-surface">{m.project_id}</td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() => deleteMutation.mutate(m.id)}
                      className="text-xs font-bold text-error hover:underline"
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Add Mapping */}
      <div className="mt-6">
        {showForm ? (
          <form onSubmit={handleCreate} className="p-4 bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)]">
            <div className="grid grid-cols-4 gap-3 mb-3">
              <input placeholder="Provider" value={provider} onChange={(e) => setProvider(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-low border border-outline-variant rounded-lg" required />
              <input placeholder="Channel ID" value={channelId} onChange={(e) => setChannelId(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-low border border-outline-variant rounded-lg" required />
              <input placeholder="Display Name" value={channelName} onChange={(e) => setChannelName(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-low border border-outline-variant rounded-lg" />
              <input placeholder="Project ID" value={projectId} onChange={(e) => setProjectId(e.target.value)}
                className="px-3 py-2 text-sm bg-surface-container-low border border-outline-variant rounded-lg" required />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold" disabled={createMutation.isPending}>
                Save
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-on-surface-variant hover:text-on-surface">
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button onClick={() => setShowForm(true)} className="flex items-center gap-1 text-sm font-bold text-primary hover:underline">
            <span className="material-symbols-outlined text-base">add</span>
            Add Mapping
          </button>
        )}
      </div>
    </div>
  );
}
