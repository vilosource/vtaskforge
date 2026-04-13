import type { LockStatus, ChatWidgetLayout } from '../types/chat';

interface ChatTitleBarProps {
  project: string;
  lockStatus: LockStatus;
  layout: ChatWidgetLayout;
  onDock: () => void;
  onFloat: () => void;
  onMinimize: () => void;
  onClose: () => void;
  onPointerDown?: (e: React.PointerEvent) => void;
}

const STATUS_DOT_COLORS: Record<LockStatus, string> = {
  connected: 'bg-green-500',
  acquiring: 'bg-yellow-500',
  error: 'bg-red-500',
  disconnected: 'bg-gray-400',
};

export function ChatTitleBar({
  project,
  lockStatus,
  layout,
  onDock,
  onFloat,
  onMinimize,
  onClose,
  onPointerDown,
}: ChatTitleBarProps) {
  return (
    <div
      data-testid="chat-title-bar"
      className="flex items-center gap-2 px-3 py-2 bg-surface-container-low select-none cursor-grab active:cursor-grabbing rounded-t-xl"
      onPointerDown={onPointerDown}
    >
      {/* Title + status */}
      <span className="material-symbols-outlined text-lg text-primary">chat</span>
      <span className="text-sm font-semibold text-on-surface flex-1 truncate">
        Chat &mdash; {project}
      </span>
      <span
        data-testid="lock-status-dot"
        className={`w-2 h-2 rounded-full ${STATUS_DOT_COLORS[lockStatus]}`}
      />

      {/* Layout controls */}
      {layout === 'floating' && (
        <button
          title="Dock to side"
          onClick={(e) => { e.stopPropagation(); onDock(); }}
          className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant"
        >
          <span className="material-symbols-outlined text-lg">dock_to_right</span>
        </button>
      )}
      {layout === 'docked' && (
        <button
          title="Float"
          onClick={(e) => { e.stopPropagation(); onFloat(); }}
          className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant"
        >
          <span className="material-symbols-outlined text-lg">open_in_new</span>
        </button>
      )}
      <button
        title="Minimize"
        onClick={(e) => { e.stopPropagation(); onMinimize(); }}
        className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant"
      >
        <span className="material-symbols-outlined text-lg">minimize</span>
      </button>
      <button
        title="Close"
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant"
      >
        <span className="material-symbols-outlined text-lg">close</span>
      </button>
    </div>
  );
}
