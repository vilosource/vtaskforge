import { Link } from 'react-router-dom';
import { useWorkplans } from '../api/workplans';

const STATUS_COLORS: Record<string, string> = {
  active: 'badge-active',
  draft: 'badge-draft',
  archived: 'badge-archived',
  completed: 'badge-completed',
};

export function WorkplanList() {
  const { data, isLoading, error, refetch } = useWorkplans();

  if (isLoading) {
    return <div className="loading">Loading workplans...</div>;
  }

  if (error) {
    return (
      <div className="error">
        Failed to load workplans.{' '}
        <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  const workplans = data?.results ?? [];

  if (workplans.length === 0) {
    return <div className="empty">No workplans yet.</div>;
  }

  return (
    <div className="workplan-list">
      <h1>Workplans</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {workplans.map((wp) => (
            <tr key={wp.id}>
              <td>
                <Link to={`/workplans/${wp.id}`}>{wp.name}</Link>
              </td>
              <td>
                <span className={`badge ${STATUS_COLORS[wp.status] ?? ''}`}>
                  {wp.status}
                </span>
              </td>
              <td>{wp.tags.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
