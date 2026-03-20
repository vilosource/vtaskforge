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

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  done: { bg: '#e8f5e9', border: '#4caf50', text: '#2e7d32' },
  doing: { bg: '#e3f2fd', border: '#1976d2', text: '#1565c0' },
  todo: { bg: '#e1f5fe', border: '#03a9f4', text: '#0277bd' },
  draft: { bg: '#f5f5f5', border: '#9e9e9e', text: '#616161' },
  blocked: { bg: '#ffebee', border: '#f44336', text: '#c62828' },
  needs_attention: { bg: '#fff3e0', border: '#ff9800', text: '#e65100' },
  cancelled: { bg: '#f5f5f5', border: '#bdbdbd', text: '#9e9e9e' },
};

function getColors(status?: string) {
  return STATUS_COLORS[status ?? ''] ?? STATUS_COLORS.draft;
}

function ChainNodePill({ node }: { node: ChainNode }) {
  const colors = getColors(node.status);
  const truncatedTitle = node.title.length > 30
    ? node.title.slice(0, 28) + '...'
    : node.title;

  const style: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 12,
    lineHeight: 1.4,
    background: colors.bg,
    border: `2px solid ${colors.border}`,
    color: colors.text,
    textDecoration: 'none',
    whiteSpace: 'nowrap',
    fontWeight: node.isCurrent ? 700 : 400,
    boxShadow: node.isCurrent ? `0 0 0 2px ${colors.border}40` : 'none',
  };

  if (node.isCurrent) {
    return <span style={style}>{truncatedTitle}</span>;
  }

  return (
    <Link to={`/tasks/${node.id}`} style={style}>
      {truncatedTitle}
    </Link>
  );
}

function Arrow() {
  return (
    <span style={{ color: '#bdbdbd', fontSize: 16, margin: '0 4px', flexShrink: 0 }}>
      →
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
    <div style={{
      display: 'flex',
      alignItems: 'center',
      overflowX: 'auto',
      padding: '8px 0',
      gap: 0,
      flexWrap: 'nowrap',
    }}>
      {upstreamTruncated && (
        <>
          <span style={{ color: '#999', fontSize: 12, marginRight: 4 }}>
            ...{upstream.length - maxVisible} more
          </span>
          <Arrow />
        </>
      )}
      {visibleUpstream.map((node) => (
        <span key={node.id} style={{ display: 'inline-flex', alignItems: 'center' }}>
          <ChainNodePill node={node} />
          <Arrow />
        </span>
      ))}
      <ChainNodePill node={currentNode} />
      {visibleDownstream.map((node) => (
        <span key={node.id} style={{ display: 'inline-flex', alignItems: 'center' }}>
          <Arrow />
          <ChainNodePill node={node} />
        </span>
      ))}
      {downstreamTruncated && (
        <>
          <Arrow />
          <span style={{ color: '#999', fontSize: 12, marginLeft: 4 }}>
            ...{downstream.length - maxVisible} more
          </span>
        </>
      )}
    </div>
  );
}
