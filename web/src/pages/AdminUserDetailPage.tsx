import { useParams, Navigate, Link } from 'react-router-dom';
import { useAuth } from '../App';
import { useUserDetail, useUpdateUserType } from '../api/users';

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

export function AdminUserDetailPage() {
  const { isStaff } = useAuth();
  const { id } = useParams<{ id: string }>();
  const { data: user, isLoading } = useUserDetail(id || '');
  const updateType = useUpdateUserType();

  if (!isStaff) return <Navigate to="/" replace />;

  if (isLoading) {
    return (
      <div className="pt-8 px-8 pb-12 max-w-3xl">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-surface-container-high rounded w-48" />
          <div className="h-40 bg-surface-container-high rounded" />
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="pt-8 px-8 pb-12">
        <p className="text-on-surface-variant">User not found.</p>
      </div>
    );
  }

  return (
    <div className="pt-8 px-8 pb-12 max-w-3xl">
      <Link to="/manage/users" className="text-sm text-primary hover:underline mb-4 inline-block">
        &larr; Back to Users
      </Link>

      <h1 className="text-3xl font-headline font-extrabold text-on-surface mb-6">{user.username}</h1>

      {/* User Info */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] mb-6">
        <div className="grid grid-cols-2 gap-y-4 gap-x-8">
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Username</div>
            <div className="text-sm font-semibold text-on-surface">{user.username}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">User Type</div>
            <div className="flex items-center gap-2">
              <span className={`inline-block px-2.5 py-0.5 rounded text-[11px] font-bold ${TYPE_BADGE[user.user_type] || ''}`}>
                {user.user_type}
              </span>
              <select
                value={user.user_type}
                onChange={(e) => updateType.mutate({ id: user.id, userType: e.target.value })}
                className="text-xs px-2 py-1 border border-outline-variant rounded bg-surface-container-lowest"
                disabled={updateType.isPending}
              >
                <option value="human">human</option>
                <option value="agent">agent</option>
                <option value="service">service</option>
              </select>
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Staff</div>
            <div className="text-sm text-on-surface">{user.is_staff ? 'Yes' : 'No'}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Active</div>
            <div className="text-sm text-on-surface">{user.is_active ? 'Yes' : 'No'}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Joined</div>
            <div className="text-sm text-on-surface-variant">{new Date(user.date_joined).toLocaleDateString()}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1">Last Login</div>
            <div className="text-sm text-on-surface-variant">{user.last_login ? new Date(user.last_login).toLocaleDateString() : '--'}</div>
          </div>
        </div>
      </div>

      {/* Memberships */}
      <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)]">
        <h2 className="text-lg font-headline font-bold text-on-surface mb-4">Project Memberships</h2>
        {user.memberships.length === 0 ? (
          <p className="text-sm text-on-surface-variant">Not a member of any projects.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant border-b border-surface-container">
                <th className="text-left pb-2">Project</th>
                <th className="text-left pb-2">Role</th>
                <th className="text-left pb-2">Since</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {user.memberships.map((m) => (
                <tr key={m.id}>
                  <td className="py-2.5 font-medium text-on-surface">{m.project_id}</td>
                  <td className="py-2.5">
                    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold ${ROLE_BADGE[m.role] || ROLE_BADGE.member}`}>
                      {m.role}
                    </span>
                  </td>
                  <td className="py-2.5 text-on-surface-variant">{new Date(m.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
