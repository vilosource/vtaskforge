import { useCallback, useRef, useState } from 'react';
import { useChatWidget } from '../contexts/ChatWidgetContext';
import { ChatTitleBar } from './ChatTitleBar';
import { ChatWindow } from './ChatWindow';
import { ChatCloseDialog } from './ChatCloseDialog';
import { ResizeDivider } from './ResizeDivider';

const MIN_WIDTH = 360;
const MIN_HEIGHT = 300;

export function ChatWidget() {
  const {
    isOpen,
    layout,
    project,
    position,
    size,
    dockWidth,
    lockStatus,
    messages,
    isStreaming,
    close,
    releaseAndClose,
    keepAliveAndMinimize,
    minimize,
    restore,
    dock,
    float,
    setPosition,
    setSize,
    setDockWidth,
    sendMessage,
  } = useChatWidget();

  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const resizeStart = useRef({ x: 0, y: 0, w: 0, h: 0 });

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

  const handleCloseClick = useCallback(() => {
    if (lockStatus === 'connected') {
      setShowCloseDialog(true);
    } else {
      close();
    }
  }, [lockStatus, close]);

  const handleRelease = useCallback(async () => {
    setShowCloseDialog(false);
    await releaseAndClose();
  }, [releaseAndClose]);

  const handleKeepAlive = useCallback(() => {
    setShowCloseDialog(false);
    keepAliveAndMinimize();
  }, [keepAliveAndMinimize]);

  const handleCancelClose = useCallback(() => {
    setShowCloseDialog(false);
  }, []);

  if (!isOpen || !project) return null;

  const closeDialog = showCloseDialog ? (
    <ChatCloseDialog
      onRelease={handleRelease}
      onKeepAlive={handleKeepAlive}
      onCancel={handleCancelClose}
    />
  ) : null;

  // ---- Floating mode ----
  if (layout === 'floating') {
    return (
      <div
        data-testid="chat-widget"
        className="fixed z-[55] rounded-xl shadow-2xl overflow-hidden flex flex-col bg-surface-container-lowest/80 backdrop-blur-xl border border-white/30"
        style={{
          left: position.x,
          top: position.y,
          width: size.width,
          height: size.height,
          minWidth: MIN_WIDTH,
          minHeight: MIN_HEIGHT,
        }}
      >
        <ChatTitleBar
          project={project}
          lockStatus={lockStatus}
          layout={layout}
          onDock={dock}
          onFloat={float}
          onMinimize={minimize}
          onClose={handleCloseClick}
          onPointerDown={handleDragStart}
        />
        <div
          className="flex-1 min-h-0 flex flex-col"
          onPointerMove={handleDragMove}
          onPointerUp={handleDragEnd}
        >
          <ChatWindow
            messages={messages}
            isStreaming={isStreaming}
            lockStatus={lockStatus}
            onSendMessage={sendMessage}
          />
        </div>

        {/* Resize handle */}
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
        {closeDialog}
      </div>
    );
  }

  // ---- Docked mode ----
  if (layout === 'docked') {
    return (
      <div
        data-testid="chat-widget"
        className="fixed right-0 top-0 h-screen z-[55] flex flex-col bg-surface-container-lowest border-l border-outline-variant shadow-2xl"
        style={{ width: dockWidth }}
      >
        <ResizeDivider onResize={handleDockResize} />
        <ChatTitleBar
          project={project}
          lockStatus={lockStatus}
          layout={layout}
          onDock={dock}
          onFloat={float}
          onMinimize={minimize}
          onClose={handleCloseClick}
        />
        <ChatWindow
          messages={messages}
          isStreaming={isStreaming}
          lockStatus={lockStatus}
          onSendMessage={sendMessage}
        />
        {closeDialog}
      </div>
    );
  }

  // ---- Minimized mode ----
  if (layout === 'minimized') {
    return (
      <div data-testid="chat-widget">
        <div
          data-testid="chat-minimized-bar"
          onClick={restore}
          className="fixed bottom-4 right-4 z-[55] flex items-center gap-2 px-4 py-2 rounded-full bg-primary text-on-primary shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <span className="material-symbols-outlined text-lg">chat</span>
          <span className="text-sm font-medium">Chat &mdash; {project}</span>
          <span className={`w-2 h-2 rounded-full ${
            lockStatus === 'connected' ? 'bg-green-300' : 'bg-gray-300'
          }`} />
        </div>
      </div>
    );
  }

  return null;
}
