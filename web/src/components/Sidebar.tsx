import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useProjects, useProjectStats, type Project } from '../api/projects';
import { useActiveProject } from '../contexts/ActiveProjectContext';

function ProjectItem({ project, isActive }: { project: Project; isActive: boolean }) {
  const { data: stats } = useProjectStats(project.id);
  const pct = stats?.completed_percentage ?? 0;

  const statusDotColor =
    project.status === 'completed' ? 'bg-tertiary' :
    project.status === 'active' ? 'bg-primary' :
    'bg-outline';

  return (
    <Link
      to={`/projects/${project.id}`}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 text-sm font-medium
        ${isActive
          ? 'text-blue-600 font-bold bg-white shadow-sm'
          : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200'
        }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusDotColor}`} />
      <span className="truncate flex-1 min-w-0">{project.name}</span>
      {stats && stats.total_tasks > 0 && (
        <span className={`text-[10px] font-bold flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-on-surface-variant'}`}>
          {pct}%
        </span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const activeProjectId = useActiveProject();
  const { data } = useProjects();
  const projects = data?.results ?? [];

  if (collapsed) {
    return (
      <aside className="h-screen w-10 fixed left-0 top-0 flex flex-col items-center pt-4 bg-slate-100 z-50">
        <button
          className="flex items-center justify-center w-6 h-6 rounded text-on-surface-variant hover:bg-slate-200 hover:text-on-surface transition-colors"
          onClick={() => setCollapsed(false)}
          title="Expand sidebar"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 flex flex-col bg-slate-100 z-50">
      <div className="flex flex-col h-full p-6 space-y-8">
        {/* Brand */}
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center text-on-primary">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>deployed_code</span>
            </div>
            <div>
              <div className="text-2xl font-bold tracking-tight text-slate-900 font-headline">VTaskForge</div>
              <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Task Platform</div>
            </div>
          </Link>
          <button
            className="flex items-center justify-center w-6 h-6 rounded text-on-surface-variant hover:bg-slate-200 hover:text-on-surface transition-colors"
            onClick={() => setCollapsed(true)}
            title="Collapse sidebar"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 3l-5 5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold mb-4 px-4">Projects</div>
          {projects.map((project) => (
            <ProjectItem
              key={project.id}
              project={project}
              isActive={project.id === activeProjectId}
            />
          ))}
          {projects.length === 0 && (
            <div className="px-4 py-3 text-sm text-on-surface-variant text-center">No projects</div>
          )}
        </nav>

        {/* Fleet section */}
        <div className="pt-6 border-t border-slate-200 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold mb-2 px-4">Fleet</div>
          <Link
            to="/agents"
            className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:text-slate-900 hover:bg-slate-200 transition-colors duration-200 rounded-lg text-sm font-medium"
          >
            <span className="material-symbols-outlined">smart_toy</span>
            <span>Agents</span>
          </Link>
        </div>
      </div>
    </aside>
  );
}
