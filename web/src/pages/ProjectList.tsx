import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useProjects, useProjectStats, useProjectWorkplans, type Project } from '../api/projects';

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-blue-100 text-blue-700',
  completed: 'bg-tertiary-container text-on-tertiary-container',
  draft: 'bg-surface-container-highest text-on-surface-variant',
  archived: 'bg-surface-container-highest text-on-surface-variant',
};

const STATUS_DOT: Record<string, string> = {
  active: 'bg-blue-500',
  completed: 'bg-tertiary',
  draft: 'bg-on-surface-variant',
  archived: 'bg-on-surface-variant',
};

const AVATAR_COLORS = [
  'bg-primary text-on-primary',
  'bg-tertiary text-on-tertiary',
  'bg-secondary text-on-secondary',
  'bg-error text-on-error',
];

function getInitials(name: string): string {
  return name
    .split(/[\s-_]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

function getAvatarColor(id: string): string {
  let hash = 0;
  for (const ch of id) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

type FilterTab = 'all' | 'active' | 'completed' | 'draft';

function ProjectRow({ project }: { project: Project }) {
  const { data: stats } = useProjectStats(project.id);
  const { data: workplans } = useProjectWorkplans(project.id);

  return (
    <tr className="hover:bg-surface-container-low/40 transition-colors cursor-pointer group">
      {/* Avatar + Name + Description */}
      <td className="px-8 py-4">
        <div className="flex items-center gap-4">
          <div
            className={`w-10 h-10 rounded-[9999px] flex items-center justify-center text-sm font-bold shrink-0 ${getAvatarColor(project.id)}`}
          >
            {getInitials(project.name)}
          </div>
          <div className="min-w-0">
            <Link
              to={`/projects/${project.id}`}
              className="text-sm font-semibold text-on-surface hover:text-primary transition-colors"
            >
              {project.name}
            </Link>
            {project.description && (
              <p className="text-xs text-on-surface-variant truncate max-w-xs mt-0.5">
                {project.description}
              </p>
            )}
          </div>
        </div>
      </td>

      {/* Status badge */}
      <td className="px-4 py-4">
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-[9999px] text-xs font-medium ${STATUS_STYLES[project.status] ?? STATUS_STYLES.draft}`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-[9999px] ${STATUS_DOT[project.status] ?? STATUS_DOT.draft}`}
          />
          {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
        </span>
      </td>

      {/* Workplans count */}
      <td className="px-4 py-4 text-center text-sm text-on-surface">
        {workplans?.length ?? '\u2014'}
      </td>

      {/* Tasks count */}
      <td className="px-4 py-4 text-center text-sm text-on-surface">
        {stats?.total_tasks ?? '\u2014'}
      </td>

      {/* Progress bar */}
      <td className="px-4 py-4">
        {stats ? (
          <div className="flex items-center gap-2">
            <div className="w-20 h-1.5 rounded-[9999px] bg-outline-variant">
              <div
                className="h-full rounded-[9999px] bg-primary transition-all"
                style={{ width: `${stats.completed_percentage}%` }}
              />
            </div>
            <span className="text-xs text-on-surface-variant">{stats.completed_percentage}%</span>
          </div>
        ) : (
          <span className="text-sm text-on-surface-variant">{'\u2014'}</span>
        )}
      </td>

      {/* Tags */}
      <td className="px-4 py-4">
        <div className="flex flex-wrap gap-1">
          {project.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 rounded-[9999px] text-[10px] font-medium bg-secondary-container text-on-secondary-container"
            >
              {tag}
            </span>
          ))}
        </div>
      </td>

      {/* Actions */}
      <td className="px-4 py-4 text-right">
        <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors opacity-0 group-hover:opacity-100">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z" />
          </svg>
        </button>
      </td>
    </tr>
  );
}

export function ProjectList() {
  const { data, isLoading, error, refetch } = useProjects();
  const [activeTab, setActiveTab] = useState<FilterTab>('all');

  if (isLoading) {
    return (
      <div className="pt-24 px-8 pb-12 flex items-center justify-center min-h-[50vh]">
        <p className="text-on-surface-variant text-sm">Loading projects...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pt-24 px-8 pb-12 flex flex-col items-center justify-center min-h-[50vh] gap-3">
        <p className="text-error text-sm">Failed to load projects.</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-on-primary hover:bg-primary/90 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const projects = data?.results ?? [];

  if (projects.length === 0) {
    return (
      <div className="pt-24 px-8 pb-12 flex items-center justify-center min-h-[50vh]">
        <p className="text-on-surface-variant text-sm">No projects yet.</p>
      </div>
    );
  }

  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'active', label: 'Active' },
    { key: 'completed', label: 'Completed' },
    { key: 'draft', label: 'Draft' },
  ];

  const filtered =
    activeTab === 'all' ? projects : projects.filter((p) => p.status === activeTab);

  return (
    <div className="pt-24 px-8 pb-12">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-4xl font-headline font-extrabold tracking-tight text-on-surface">
          Projects
        </h1>
        <p className="mt-1 text-on-surface-variant">
          Manage and track all your projects in one place.
        </p>
      </div>

      {/* Card */}
      <div className="bg-surface-container-lowest rounded-xl shadow overflow-hidden">
        {/* Filter bar */}
        <div className="px-8 py-5 flex items-center gap-4 border-b border-outline-variant/40">
          {/* Filter icon button */}
          <button className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-on-surface-variant border border-outline-variant rounded-lg hover:bg-surface-container-low transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            Filter
          </button>

          {/* Divider */}
          <div className="w-px h-6 bg-outline-variant/60" />

          {/* Tab links */}
          <div className="flex items-center gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  activeTab === tab.key
                    ? 'bg-primary text-on-primary'
                    : 'text-on-surface-variant hover:bg-surface-container-low'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <table className="w-full">
          <thead>
            <tr className="bg-surface-container-low/20">
              <th className="px-8 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Project
              </th>
              <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Status
              </th>
              <th className="px-4 py-3 text-center text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Workplans
              </th>
              <th className="px-4 py-3 text-center text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Tasks
              </th>
              <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Progress
              </th>
              <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Tags
              </th>
              <th className="px-4 py-3 w-12" />
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/30">
            {filtered.map((project) => (
              <ProjectRow key={project.id} project={project} />
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="px-8 py-12 text-center text-sm text-on-surface-variant">
            No {activeTab} projects found.
          </div>
        )}
      </div>
    </div>
  );
}
