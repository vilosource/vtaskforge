import { Link } from 'react-router-dom';
import { useWorkplans, useWorkplanStats, type Workplan } from '../api/workplans';
import { useMilestones } from '../api/milestones';

const STATUS_BADGE_CLASSES: Record<string, string> = {
  active: 'bg-blue-50 text-blue-700 border border-blue-200',
  draft: 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40',
  archived: 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40',
  completed: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
};

function WorkplanRow({ wp }: { wp: Workplan }) {
  const { data: stats } = useWorkplanStats(wp.id);
  const { data: milestones } = useMilestones(wp.id);

  return (
    <tr className="hover:bg-surface-container-low/40 transition-colors">
      <td className="px-6 py-3 text-sm font-semibold text-on-surface">
        <Link to={`/workplans/${wp.id}`} className="text-primary hover:underline">{wp.name}</Link>
      </td>
      <td className="px-6 py-3">
        <span className={`inline-flex items-center text-[11px] font-semibold leading-none px-2 py-1 rounded whitespace-nowrap uppercase tracking-wide ${STATUS_BADGE_CLASSES[wp.status] ?? 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40'}`}>
          {wp.status}
        </span>
      </td>
      <td className="px-6 py-3 text-sm text-on-surface">{milestones?.length ?? '\u2014'}</td>
      <td className="px-6 py-3 text-sm text-on-surface">{stats?.total_tasks ?? '\u2014'}</td>
      <td className="px-6 py-3">
        {stats ? (
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 rounded-full bg-surface-container-high overflow-hidden">
              <div
                className="h-full rounded-full bg-tertiary transition-all"
                style={{ width: `${stats.completed_percentage}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-on-surface-variant">{stats.completed_percentage}%</span>
          </div>
        ) : '\u2014'}
      </td>
      <td className="px-6 py-3">
        <div className="flex gap-1 flex-wrap">
          {wp.tags.map((tag) => (
            <span key={tag} className="bg-secondary-container text-on-secondary-container text-[11px] font-semibold px-2 py-0.5 rounded-full">{tag}</span>
          ))}
        </div>
      </td>
    </tr>
  );
}

export function WorkplanList() {
  const { data, isLoading, error, refetch } = useWorkplans();

  if (isLoading) {
    return <div className="flex items-center justify-center p-12 text-on-surface-variant">Loading workplans...</div>;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center p-12 text-error">
        Failed to load workplans.{' '}
        <button onClick={() => refetch()} className="ml-2 text-primary underline cursor-pointer border-0 bg-transparent">Retry</button>
      </div>
    );
  }

  const workplans = data?.results ?? [];

  if (workplans.length === 0) {
    return <div className="flex items-center justify-center p-12 text-on-surface-variant text-sm">No workplans yet.</div>;
  }

  return (
    <div className="px-8 pb-12 pt-6">
      <h1 className="text-xl font-headline font-bold text-on-surface mb-6">Workplans</h1>
      <div className="bg-surface-container-lowest rounded-xl shadow overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-surface-container-low/20">
              <th className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4">Name</th>
              <th className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4">Status</th>
              <th className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4">Milestones</th>
              <th className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4">Tasks</th>
              <th className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4">Progress</th>
              <th className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-6 py-4">Tags</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-container">
            {workplans.map((wp) => (
              <WorkplanRow key={wp.id} wp={wp} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
