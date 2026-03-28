import { Link } from 'react-router-dom';
import type { TaskLink } from '../api/tasks';

interface ChainNode {
  id: string;
  title: string;
  status?: string;
  isCurrent: boolean;
}

interface DependencyChainProps {
  taskId: string;
  taskTitle: string;
  taskStatus: string;
  /** depends_on links from this task's detail (upstream) */
  upstreamLinks: TaskLink[];
  /** links where this task is the target (downstream / blocked by this) */
  downstreamLinks: TaskLink[];
}

const STATUS_STYLES: Record<string, string> = {
  done: 'bg-tertiary/10 border-tertiary text-tertiary',
  doing: 'bg-primary/10 border-primary text-primary',
  todo: 'bg-primary-fixed/30 border-primary-fixed-dim text-on-primary-fixed',
  draft: 'bg-surface-container-high border-outline-variant text-on-surface-variant',
  blocked: 'bg-error-container border-error text-on-error-container',
  needs_attention: 'bg-error-container/60 border-error/60 text-error',
  cancelled: 'bg-surface-container-high border-outline-variant/50 text-on-surface-variant',
};

function getStyles(status?: string) {
  return STATUS_STYLES[status ?? ''] ?? STATUS_STYLES.draft;
}

function ChainNodePill({ node }: { node: ChainNode }) {
  const styles = getStyles(node.status);
  const truncatedTitle = node.title.length > 30
    ? node.title.slice(0, 28) + '...'
    : node.title;

  const base = `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs leading-snug border-2 whitespace-nowrap no-underline ${styles}`;
  const weight = node.isCurrent ? 'font-bold ring-2 ring-primary/25' : 'font-normal';

  if (node.isCurrent) {
    return <span className={`${base} ${weight}`}>{truncatedTitle}</span>;
  }

  return (
    <Link to={`/tasks/${node.id}`} className={`${base} ${weight} hover:shadow-md transition-shadow`}>
      {truncatedTitle}
    </Link>
  );
}

function Arrow() {
  return (
    <span className="text-outline-variant text-base mx-1 flex-shrink-0">
      &rarr;
    </span>
  );
}

export function DependencyChain({
  taskId,
  taskTitle,
  taskStatus,
  upstreamLinks,
  downstreamLinks,
}: DependencyChainProps) {
  const upstream: ChainNode[] = upstreamLinks
    .filter(l => l.link_type === 'depends_on' && l.target_type === 'task')
    .map(l => ({
      id: l.target_id,
      title: l.target_title ?? l.target_id,
      status: undefined, // We don't have status from links — could be enhanced later
      isCurrent: false,
    }));

  const downstream: ChainNode[] = downstreamLinks
    .filter(l => l.link_type === 'depends_on' && l.source_type === 'task')
    .map(l => ({
      id: l.source_id,
      title: l.source_title ?? l.source_id,
      status: undefined,
      isCurrent: false,
    }));

  const currentNode: ChainNode = {
    id: taskId,
    title: taskTitle,
    status: taskStatus,
    isCurrent: true,
  };

  const hasChain = upstream.length > 0 || downstream.length > 0;
  if (!hasChain) return null;

  // Truncate long chains
  const maxVisible = 3;
  const visibleUpstream = upstream.length > maxVisible
    ? upstream.slice(-maxVisible)
    : upstream;
  const visibleDownstream = downstream.length > maxVisible
    ? downstream.slice(0, maxVisible)
    : downstream;
  const upstreamTruncated = upstream.length > maxVisible;
  const downstreamTruncated = downstream.length > maxVisible;

  return (
    <div className="flex items-center overflow-x-auto py-2 flex-nowrap">
      {upstreamTruncated && (
        <>
          <span className="text-on-surface-variant text-xs mr-1">
            ...{upstream.length - maxVisible} more
          </span>
          <Arrow />
        </>
      )}
      {visibleUpstream.map((node) => (
        <span key={node.id} className="inline-flex items-center">
          <ChainNodePill node={node} />
          <Arrow />
        </span>
      ))}
      <ChainNodePill node={currentNode} />
      {visibleDownstream.map((node) => (
        <span key={node.id} className="inline-flex items-center">
          <Arrow />
          <ChainNodePill node={node} />
        </span>
      ))}
      {downstreamTruncated && (
        <>
          <Arrow />
          <span className="text-on-surface-variant text-xs ml-1">
            ...{downstream.length - maxVisible} more
          </span>
        </>
      )}
    </div>
  );
}
