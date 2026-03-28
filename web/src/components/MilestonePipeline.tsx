import { Link } from 'react-router-dom';
import { useMilestoneStats } from '../api/milestones';
import type { Milestone } from '../api/milestones';

interface MilestonePipelineProps {
  milestones: Milestone[];
  projectId: string;
  workplanId: string;
}

const MILESTONES_PER_ROW = 4;

const STATUS_STYLES: Record<string, { card: string; bar: string }> = {
  completed: { card: 'bg-tertiary/10 border-tertiary text-tertiary', bar: 'bg-tertiary' },
  active: { card: 'bg-primary/10 border-primary text-primary', bar: 'bg-primary' },
  pending: { card: 'bg-surface-container-high border-outline-variant text-on-surface-variant', bar: 'bg-outline-variant' },
};

function PipelineNode({ milestone, projectId, workplanId }: { milestone: Milestone; projectId: string; workplanId: string }) {
  const { data: stats } = useMilestoneStats(milestone.id);
  const total = stats?.total_tasks ?? 0;
  const done = stats?.by_status?.done ?? 0;
  const pct = stats?.completed_percentage ?? 0;
  const styles = STATUS_STYLES[milestone.status] ?? STATUS_STYLES.pending;

  return (
    <Link
      to={`/projects/${projectId}/workplans/${workplanId}/milestones/${milestone.id}`}
      className="no-underline flex-1 min-w-0"
    >
      <div className={`px-3 py-2.5 border-2 rounded-lg text-center cursor-pointer transition-shadow hover:shadow-md ${styles.card}`}>
        <div className="font-semibold text-[13px] whitespace-nowrap overflow-hidden text-ellipsis">
          {milestone.name}
        </div>
        <div className="text-[11px] text-on-surface-variant mt-0.5">
          {done}/{total}
        </div>
        <div className="mt-1 h-[3px] bg-surface-container-highest rounded-sm overflow-hidden">
          <div className={`h-full rounded-sm ${styles.bar}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    </Link>
  );
}

function HArrow({ reverse }: { reverse?: boolean }) {
  return (
    <div className="flex items-center px-0.5 text-outline-variant text-base flex-shrink-0">
      {reverse ? '\u2190' : '\u2192'}
    </div>
  );
}

function VConnector({ side }: { side: 'right' | 'left' }) {
  return (
    <div className={`flex ${side === 'right' ? 'justify-end pr-6' : 'justify-start pl-6'}`}>
      <div className="w-0.5 h-5 bg-outline-variant relative">
        {/* Down arrow */}
        <div className="absolute -bottom-1.5 -left-1 w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[6px] border-t-outline-variant" />
      </div>
    </div>
  );
}

export function MilestonePipeline({ milestones, projectId, workplanId }: MilestonePipelineProps) {
  if (milestones.length === 0) {
    return <div className="py-10 text-center text-on-surface-variant">No milestones yet.</div>;
  }

  // Split milestones into rows
  const rows: Milestone[][] = [];
  for (let i = 0; i < milestones.length; i += MILESTONES_PER_ROW) {
    rows.push(milestones.slice(i, i + MILESTONES_PER_ROW));
  }

  return (
    <div className="py-2">
      {rows.map((row, rowIndex) => {
        const isReversed = rowIndex % 2 === 1;
        const displayRow = isReversed ? [...row].reverse() : row;
        const isLastRow = rowIndex === rows.length - 1;

        return (
          <div key={rowIndex}>
            {/* Milestone row */}
            <div className="flex items-center">
              {displayRow.map((milestone, i) => (
                <div key={milestone.id} className="flex items-center flex-1 min-w-0">
                  <PipelineNode milestone={milestone} projectId={projectId} workplanId={workplanId} />
                  {i < displayRow.length - 1 && <HArrow reverse={isReversed} />}
                </div>
              ))}
            </div>

            {/* Vertical connector to next row */}
            {!isLastRow && (
              <VConnector side={isReversed ? 'left' : 'right'} />
            )}
          </div>
        );
      })}
    </div>
  );
}
