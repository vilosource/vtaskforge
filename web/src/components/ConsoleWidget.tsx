import { useCallback, useRef, useState } from 'react';
import { useConsoleWidget } from '../contexts/ConsoleWidgetContext';
import { ConsoleIframe, type ConsoleStatus } from './ConsoleIframe';
import { MinimizedBar } from './MinimizedBar';
import { ResizeDivider } from './ResizeDivider';
import { buildAuthenticatedConsoleUrl } from '../api/console';

const MIN_WIDTH = 400;
const MIN_HEIGHT = 300;

export function ConsoleWidget() {
  const {
    isOpen,
    layout,
    target,
    position,
    size,
    dockWidth,
    close,
    minimize,
    dock,
    float,
    setPosition,
    setSize,
    setDockWidth,
    restore,
  } = useConsoleWidget();

  const [status, setStatus] = useState<ConsoleStatus>('loading');
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const resizeStart = useRef({ x: 0, y: 0, w: 0, h: 0 });

  const handleStatusChange = useCallback((newStatus: ConsoleStatus) => {
    setStatus(newStatus);
  }, []);

  const handlePopOut = useCallback(async () => {
    if (!target) return;
    const url = await buildAuthenticatedConsoleUrl({ ...target });
    window.open(url, '_blank', 'noopener,noreferrer');
    close();
  }, [target, close]);

  const handleDragStart = useCallback(
    (e: React.PointerEvent) => {
      if (layout !== 'floating') return;
      setIsDragging(true);
      dragOffset.current = { x: e.clientX - position.x, y: e.clientY - position.y };
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    },
    [layout, position],
  );

  const handleDragMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging) return;
      setPosition({
        x: e.clientX - dragOffset.current.x,
        y: e.clientY - dragOffset.current.y,
      });
    },
    [isDragging, setPosition],
  );

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleResizeStart = useCallback(
    (e: React.PointerEvent) => {
      e.stopPropagation();
      setIsResizing(true);
      resizeStart.current = { x: e.clientX, y: e.clientY, w: size.width, h: size.height };
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    },
    [size],
  );

  const handleResizeMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isResizing) return;
      const dx = e.clientX - resizeStart.current.x;
      const dy = e.clientY - resizeStart.current.y;
      setSize({
        width: Math.max(MIN_WIDTH, resizeStart.current.w + dx),
        height: Math.max(MIN_HEIGHT, resizeStart.current.h + dy),
      });
    },
    [isResizing, setSize],
  );

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
  }, []);

  const handleDockResize = useCallback(
    (deltaX: number) => {
      setDockWidth(Math.max(MIN_WIDTH, dockWidth + deltaX));
    },
    [dockWidth, setDockWidth],
  );

  if (!isOpen || !target) return null;

  const displayTitle = target.pod
    ? `Terminal: ${target.pod}`
    : `Architect${target.project ? ` — ${target.project}` : ''}`;

  const statusColors: Record<ConsoleStatus, string> = {
    loading: 'bg-yellow-500',
    ready: 'bg-yellow-500',
    connected: 'bg-green-500',
    disconnected: 'bg-red-500',
    error: 'bg-red-500',
  };

  // Floating mode styles
  if (layout === 'floating') {
    return (
      <div
        data-testid="console-widget"
        className="fixed z-[60] rounded-xl shadow-2xl overflow-hidden flex flex-col bg-surface-container-lowest border border-outline-variant"
        style={{
          left: position.x,
          top: position.y,
          width: size.width,
          height: size.height,
          minWidth: MIN_WIDTH,
          minHeight: MIN_HEIGHT,
        }}
      >
        {/* Title bar */}
        <div
          className="flex items-center justify-between px-4 py-2 border-b border-outline-variant bg-surface-container cursor-move select-none"
          onPointerDown={handleDragStart}
          onPointerMove={handleDragMove}
          onPointerUp={handleDragEnd}
        >
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg">terminal</span>
            <span className="text-sm font-semibold text-on-surface">{displayTitle}</span>
            <span className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={dock}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Dock to side"
            >
              <span className="material-symbols-outlined text-[18px]">dock_to_right</span>
            </button>
            <button
              onClick={minimize}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Minimize"
            >
              <span className="material-symbols-outlined text-[18px]">minimize</span>
            </button>
            <button
              onClick={handlePopOut}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Open in new tab"
            >
              <span className="material-symbols-outlined text-[18px]">open_in_new</span>
            </button>
            <button
              onClick={close}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Close"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
        </div>

        {/* Iframe content */}
        <div className="flex-1 min-h-0">
          <ConsoleIframe target={target} onStatusChange={handleStatusChange} />
        </div>

        {/* Resize handle (bottom-right corner) */}
        <div
          className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize z-10"
          onPointerDown={handleResizeStart}
          onPointerMove={handleResizeMove}
          onPointerUp={handleResizeEnd}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" className="text-on-surface-variant opacity-50">
            <path d="M14 14H10M14 14V10M14 10H6M14 6V2" stroke="currentColor" strokeWidth="1.5" fill="none" />
          </svg>
        </div>
      </div>
    );
  }

  // Docked mode
  if (layout === 'docked') {
    return (
      <div
        data-testid="console-widget"
        className="fixed right-0 top-0 h-screen z-[60] flex flex-col bg-surface-container-lowest border-l border-outline-variant shadow-2xl"
        style={{ width: dockWidth }}
      >
        <ResizeDivider onResize={handleDockResize} />
        {/* Title bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-outline-variant bg-surface-container select-none">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg">terminal</span>
            <span className="text-sm font-semibold text-on-surface">{displayTitle}</span>
            <span className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={float}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Undock"
            >
              <span className="material-symbols-outlined text-[18px]">float</span>
            </button>
            <button
              onClick={minimize}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Minimize"
            >
              <span className="material-symbols-outlined text-[18px]">minimize</span>
            </button>
            <button
              onClick={handlePopOut}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Open in new tab"
            >
              <span className="material-symbols-outlined text-[18px]">open_in_new</span>
            </button>
            <button
              onClick={close}
              className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              title="Close"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
        </div>

        {/* Iframe content */}
        <div className="flex-1 min-h-0">
          <ConsoleIframe target={target} onStatusChange={handleStatusChange} />
        </div>
      </div>
    );
  }

  // Minimized mode
  if (layout === 'minimized') {
    return (
      <div data-testid="console-widget">
        <MinimizedBar target={target} onRestore={restore} />
        {/* Keep iframe alive but hidden */}
        <div className="w-[1px] h-[1px] overflow-hidden absolute" style={{ left: -9999 }}>
          <ConsoleIframe target={target} onStatusChange={handleStatusChange} />
        </div>
      </div>
    );
  }

  return null;
}
