import { Link } from 'react-router-dom';
import { useProjects, useProjectStats, useProjectWorkplans, type Project } from '../api/projects';

const STATUS_COLORS: Record<string, string> = {
  active: 'badge-active',
  draft: 'badge-draft',
  archived: 'badge-archived',
  completed: 'badge-completed',
};

function ProjectRow({ project }: { project: Project }) {
  const { data: stats } = useProjectStats(project.id);
  const { data: workplans } = useProjectWorkplans(project.id);

  return (
    <tr>
      <td>
        <Link to={`/projects/${project.id}`}>{project.name}</Link>
      </td>
      <td>
        <span className={`badge ${STATUS_COLORS[project.status] ?? ''}`}>
          {project.status}
        </span>
      </td>
      <td>{workplans?.length ?? '\u2014'}</td>
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
      <td>{project.tags.join(', ')}</td>
    </tr>
  );
}

export function ProjectList() {
  const { data, isLoading, error, refetch } = useProjects();

  if (isLoading) {
    return <div className="loading">Loading projects...</div>;
  }

  if (error) {
    return (
      <div className="error">
        Failed to load projects.{' '}
        <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  const projects = data?.results ?? [];

  if (projects.length === 0) {
    return <div className="empty">No projects yet.</div>;
  }

  return (
    <div className="workplan-list">
      <h1>Projects</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Workplans</th>
            <th>Tasks</th>
            <th>Progress</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <ProjectRow key={project.id} project={project} />
          ))}
        </tbody>
      </table>
    </div>
  );
}