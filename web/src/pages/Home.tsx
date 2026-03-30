import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { useAuth } from '../App';
import { useProjects, type ProjectStats, type ProjectWorkplan } from '../api/projects';
import { useAgents, type Agent } from '../api/agents';
import { apiGet, apiGetPaginated } from '../api/client';
import { useConsoleWidget } from '../contexts/ConsoleWidgetContext';

/* ---------- helpers ---------- */

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse bg-surface-container-high rounded ${className ?? ''}`} />;
}

/* ---------- sub-components ---------- */

function StatCard({
  icon, iconColor, iconBg, value, label, valueColor, badge,
}: {
  icon: string; iconColor: string; iconBg: string;
  value: string | number; label: string; valueColor?: string; badge?: React.ReactNode;
}) {
  return (
    <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] transition-transform hover:-translate-y-1">
      <div className="flex justify-between items-start mb-4">
        <span className={`material-symbols-outlined ${iconColor} ${iconBg} p-2 rounded-lg`}>{icon}</span>
        {badge}
      </div>
      <div className={`text-3xl font-headline font-extrabold ${valueColor ?? 'text-on-surface'}`}>{value}</div>
      <div className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mt-1">{label}</div>
    </div>
  );
}

function NeedsAttentionRow({
  icon, iconBg, iconColor, title, meta, linkTo,
}: {
  icon: string; iconBg: string; iconColor: string;
  title: string; meta: React.ReactNode; linkTo?: string;
}) {
  const inner = (
    <div className="px-8 py-4 flex items-center gap-4 hover:bg-surface-container-low/40 transition-colors cursor-pointer">
      <div className={`w-10 h-10 rounded-[999px] ${iconBg} flex items-center justify-center flex-shrink-0`}>
        <span className={`material-symbols-outlined ${iconColor} text-lg`}>{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-on-surface truncate">{title}</div>
        <div className="text-[10px] text-on-surface-variant mt-0.5">{meta}</div>
      </div>
    </div>
  );
  return linkTo ? <Link to={linkTo} className="block">{inner}</Link> : inner;
}

function WorkplanCard({
  workplan, projectName, projectId,
}: {
  workplan: ProjectWorkplan; projectName: string; projectId: string;
}) {
  const pct = workplan.completed_percentage ?? 0;
  const done = workplan.total_tasks > 0 ? Math.round((pct / 100) * workplan.total_tasks) : 0;

  return (
    <Link
      to={`/projects/${projectId}/workplans/${workplan.id}`}
      className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] transition-all hover:shadow-lg hover:-translate-y-1 cursor-pointer block"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="px-2 py-0.5 bg-secondary-container text-on-secondary-container rounded text-[10px] font-medium">{projectName}</span>
        <span className="px-2.5 py-0.5 rounded-[999px] bg-blue-100 text-blue-700 text-[10px] font-bold uppercase">Active</span>
      </div>
      <h3 className="font-headline font-bold text-on-surface mb-1">{workplan.name}</h3>
      {workplan.description && (
        <p className="text-xs text-on-surface-variant mb-4 leading-relaxed line-clamp-2">{workplan.description}</p>
      )}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Progress</span>
        <span className="text-sm font-bold text-primary">{pct}%</span>
      </div>
      <div className="w-full h-1.5 bg-surface-container-high rounded-[999px] overflow-hidden">
        <div className="h-full bg-primary rounded-[999px]" style={{ width: `${pct}%` }} />
      </div>
      <div className="flex items-center justify-between mt-3 text-[10px] text-on-surface-variant">
        <span>{workplan.total_tasks} tasks &middot; {done} done</span>
      </div>
    </Link>
  );
}

/* ---------- main component ---------- */

export function Home() {
  const { username } = useAuth();
  const { data: projectData, isLoading: projectsLoading } = useProjects();
  const { data: agentData, isLoading: agentsLoading } = useAgents();

  const projects = projectData?.results ?? [];
  const agents = agentData?.results ?? [];

  // Fetch stats for all projects using useQueries (safe with dynamic count)
  const statsQueries = useQueries({
    queries: projects.map((p) => ({
      queryKey: ['project-stats', p.id],
      queryFn: () => apiGet<ProjectStats>(`/v1/projects/${p.id}/stats/`),
    })),
  });
  const statsLoaded = !projectsLoading && statsQueries.every((q) => !q.isLoading);
  const allStats = statsQueries.map((q) => q.data).filter((s): s is ProjectStats => !!s);

  // Fetch workplans for all projects using useQueries
  const workplanQueries = useQueries({
    queries: projects.map((p) => ({
      queryKey: ['project-workplans', p.id],
      queryFn: () => apiGetPaginated<ProjectWorkplan>(`/v1/projects/${p.id}/workplans/`),
    })),
  });
  const workplansLoaded = !projectsLoading && workplanQueries.every((q) => !q.isLoading);

  // Aggregate stats
  const totalTasks = allStats.reduce((sum, s) => sum + s.total_tasks, 0);
  const completedTasks = allStats.reduce((sum, s) => sum + (s.by_status?.['done'] ?? 0), 0);
  const overallProgress = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  // Attention items from stats
  const attentionStatuses = ['blocked', 'needs_attention', 'pending_completion_review', 'pending_start_review'];
  const attentionTasks = allStats.flatMap((s) =>
    attentionStatuses
      .filter((status) => (s.by_status?.[status] ?? 0) > 0)
      .map((status) => ({ projectId: s.project_id, status, count: s.by_status[status] })),
  );

  // Active workplans across projects
  const activeWorkplans = useMemo(() =>
    workplanQueries.flatMap((wq, i) => {
      const wps = wq.data ?? [];
      return wps
        .filter((w) => w.status === 'active')
        .map((w) => ({ ...w, projectId: projects[i]?.id ?? '', projectName: projects[i]?.name ?? '' }));
    }),
    [workplanQueries, projects],
  );

  const onlineAgents = useMemo(
    () => agents.filter((a: Agent) => a.effective_status === 'online' || a.effective_status === 'busy'),
    [agents],
  );
  const problemAgents = useMemo(
    () => agents.filter((a: Agent) => a.effective_status === 'stale' || a.effective_status === 'offline'),
    [agents],
  );
  const projectNameById = useMemo(() => {
    const map: Record<string, string> = {};
    projects.forEach((p) => { map[p.id] = p.name; });
    return map;
  }, [projects]);

  const { open: openConsoleWidget } = useConsoleWidget();
  const greeting = getGreeting();
  const displayName = username || 'there';
  const isLoading = projectsLoading || agentsLoading;
  const attentionCount = attentionTasks.reduce((sum, a) => sum + a.count, 0) + problemAgents.length;

  return (
    <div className="pt-8 px-8 pb-12">
      {/* Welcome header */}
      <div className="mb-10">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-on-surface-variant text-sm">{greeting},</span>
        </div>
        <h1 className="text-4xl font-headline font-extrabold text-on-surface tracking-tight">
          Welcome back, {displayName}
        </h1>
        <p className="text-on-surface-variant mt-2">Here&apos;s what&apos;s happening across your fleet today.</p>
      </div>

      {/* Fleet-wide stats */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-12">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)]">
              <Skeleton className="w-10 h-10 mb-4" />
              <Skeleton className="w-16 h-8 mb-2" />
              <Skeleton className="w-24 h-3" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-12">
          <StatCard icon="folder_open" iconColor="text-primary" iconBg="bg-primary-fixed" value={projects.length} label="Projects" />
          <StatCard icon="task_alt" iconColor="text-blue-600" iconBg="bg-blue-100" value={statsLoaded ? totalTasks : '...'} label="Total Tasks" />
          <StatCard icon="check_circle" iconColor="text-tertiary" iconBg="bg-tertiary-container" value={statsLoaded ? completedTasks : '...'} label="Completed" valueColor="text-tertiary" />
          <StatCard
            icon="smart_toy" iconColor="text-secondary" iconBg="bg-secondary-fixed"
            value={onlineAgents.length} label="Agents Online"
            badge={onlineAgents.length > 0 ? (
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-[999px] bg-tertiary animate-pulse" />
                <span className="text-[10px] font-bold text-tertiary uppercase">Live</span>
              </div>
            ) : undefined}
          />
          <StatCard icon="trending_up" iconColor="text-primary" iconBg="bg-primary-fixed" value={statsLoaded ? `${overallProgress}%` : '...'} label="Overall Progress" valueColor="text-primary" />
        </div>
      )}

      {/* Needs Attention + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] overflow-hidden">
          <div className="px-8 py-5 flex items-center justify-between border-b border-outline-variant/20">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-error">warning</span>
              <h2 className="text-lg font-headline font-bold text-on-surface">Needs Attention</h2>
            </div>
            {attentionCount > 0 && (
              <span className="bg-error-container text-on-error-container text-[10px] font-bold px-2.5 py-1 rounded-[999px]">
                {attentionCount} {attentionCount === 1 ? 'item' : 'items'}
              </span>
            )}
          </div>
          <div className="divide-y divide-surface-container">
            {!statsLoaded ? (
              <div className="px-8 py-6 space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="w-10 h-10 rounded-full" />
                    <div className="flex-1 space-y-2"><Skeleton className="w-3/4 h-4" /><Skeleton className="w-1/2 h-3" /></div>
                  </div>
                ))}
              </div>
            ) : attentionCount === 0 ? (
              <div className="px-8 py-10 text-center">
                <span className="material-symbols-outlined text-tertiary text-3xl mb-2">check_circle</span>
                <p className="text-sm text-on-surface-variant">Nothing needs attention right now. All clear!</p>
              </div>
            ) : (
              <>
                {attentionTasks.map((item) => {
                  const statusLabel =
                    item.status === 'blocked' ? 'Blocked' :
                    item.status === 'needs_attention' ? 'Needs attention' :
                    item.status === 'pending_completion_review' ? 'Pending review' :
                    'Pending start review';
                  const isError = item.status === 'blocked' || item.status === 'needs_attention';
                  return (
                    <NeedsAttentionRow
                      key={`${item.projectId}-${item.status}`}
                      icon={isError ? 'block' : 'rate_review'}
                      iconBg={isError ? 'bg-error-container' : 'bg-yellow-100'}
                      iconColor={isError ? 'text-error' : 'text-yellow-700'}
                      title={`${item.count} ${statusLabel.toLowerCase()} task${item.count !== 1 ? 's' : ''}`}
                      linkTo={`/projects/${item.projectId}`}
                      meta={<><span className={`font-bold ${isError ? 'text-error' : 'text-yellow-700'}`}>{statusLabel}</span> &middot; {projectNameById[item.projectId] ?? 'Unknown project'}</>}
                    />
                  );
                })}
                {problemAgents.map((agent) => (
                  <NeedsAttentionRow
                    key={agent.id}
                    icon="sensors_off" iconBg="bg-error-container" iconColor="text-error"
                    title={`${agent.name} is ${agent.effective_status}`}
                    linkTo={`/agents/${agent.id}`}
                    meta={<><span className="font-bold text-error">Last heartbeat: {agent.last_heartbeat ? new Date(agent.last_heartbeat).toLocaleDateString() : 'Never'}</span> &middot; {agent.current_task ? `Running: ${agent.current_task.title}` : 'No tasks running'}</>}
                  />
                ))}
              </>
            )}
          </div>
        </div>

        <div className="bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] overflow-hidden">
          <div className="px-6 py-5 flex items-center justify-between border-b border-outline-variant/20">
            <h2 className="text-lg font-headline font-bold text-on-surface">Recent Activity</h2>
          </div>
          <div className="px-6 py-8 text-center">
            <span className="material-symbols-outlined text-on-surface-variant text-3xl mb-2">history</span>
            <p className="text-sm text-on-surface-variant">Coming soon</p>
            <p className="text-xs text-on-surface-variant mt-1">Activity feed will show task and agent events here.</p>
          </div>
        </div>
      </div>

      {/* Active Workplans */}
      <div className="mb-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-headline font-bold text-on-surface">Active Workplans</h2>
          <Link to="/projects" className="text-sm font-bold text-primary hover:underline">View all projects</Link>
        </div>
        {!workplansLoaded ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)]">
                <Skeleton className="w-24 h-4 mb-3" /><Skeleton className="w-3/4 h-5 mb-2" /><Skeleton className="w-full h-3 mb-4" /><Skeleton className="w-full h-1.5 mb-2" />
              </div>
            ))}
          </div>
        ) : activeWorkplans.length === 0 ? (
          <div className="bg-surface-container-lowest rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)] p-10 text-center">
            <span className="material-symbols-outlined text-on-surface-variant text-3xl mb-2">assignment</span>
            <p className="text-sm text-on-surface-variant">No active workplans across projects.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {activeWorkplans.map((wp) => (
              <WorkplanCard key={wp.id} workplan={wp} projectName={wp.projectName} projectId={wp.projectId} />
            ))}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-headline font-bold text-on-surface mb-6">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button className="bg-surface-container-lowest p-5 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 flex flex-col items-center gap-3 cursor-pointer border border-outline-variant/20">
            <span className="material-symbols-outlined text-primary text-2xl">add_circle</span>
            <span className="text-xs font-bold text-on-surface">New Project</span>
          </button>
          <button className="bg-surface-container-lowest p-5 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 flex flex-col items-center gap-3 cursor-pointer border border-outline-variant/20">
            <span className="material-symbols-outlined text-tertiary text-2xl">rocket_launch</span>
            <span className="text-xs font-bold text-on-surface">Deploy Agent</span>
          </button>
          <button className="bg-surface-container-lowest p-5 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 flex flex-col items-center gap-3 cursor-pointer border border-outline-variant/20">
            <span className="material-symbols-outlined text-secondary text-2xl">upload_file</span>
            <span className="text-xs font-bold text-on-surface">Import Workplan</span>
          </button>
          <button className="bg-surface-container-lowest p-5 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 flex flex-col items-center gap-3 cursor-pointer border border-outline-variant/20">
            <span className="material-symbols-outlined text-on-surface-variant text-2xl">monitoring</span>
            <span className="text-xs font-bold text-on-surface">Fleet Status</span>
          </button>
          <button
            onClick={() => openConsoleWidget({ role: 'architect' })}
            className="bg-surface-container-lowest p-5 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 flex flex-col items-center gap-3 cursor-pointer border border-outline-variant/20"
          >
            <span className="material-symbols-outlined text-primary text-2xl">terminal</span>
            <span className="text-xs font-bold text-on-surface">Consult Architect</span>
          </button>
        </div>
      </div>
    </div>
  );
}
