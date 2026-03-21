import { Link } from 'react-router-dom';
import { useWorkplans, useWorkplanStats, type Workplan } from '../api/workplans';
import { useMilestones } from '../api/milestones';

const STATUS_COLORS: Record<string, string> = {
  active: 'badge-active',
  draft: 'badge-draft',
  archived: 'badge-archived',
  completed: 'badge-completed',
};

function WorkplanRow({ wp }: { wp: Workplan }) {
  const { data: stats } = useWorkplanStats(wp.id);
  const { data: milestones } = useMilestones(wp.id);

  return (
    <tr>
      <td>
        <Link to={`/workplans/${wp.id}`}>{wp.name}</Link>
      </td>
      <td>
        <span className={`badge ${STATUS_COLORS[wp.status] ?? ''}`}>
          {wp.status}
        </span>
      </td>
      <td>{milestones?.length ?? '\u2014'}</td>
      <td>{stats?.total_tasks ?? '\u2014'}</td>
      <td>
        {stats ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 60, height: 6, background: '#e0e0e0', borderRadius: 3 }}>
              <div style={{
                width: `${stats.completed_percentage}%`,
                height: '100%',
                background: '#4caf50',
                borderRadius: 3,
              }} />
            </div>
            <span style={{ fontSize: 12 }}>{stats.completed_percentage}%</span>
          </div>
        ) : '\u2014'}
      </td>
      <td>{wp.tags.join(', ')}</td>
    </tr>
  );
}

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
            <th>Milestones</th>
            <th>Tasks</th>
            <th>Progress</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {workplans.map((wp) => (
            <WorkplanRow key={wp.id} wp={wp} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
