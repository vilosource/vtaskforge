/**
 * ConsoleModal — embeds vafi-console terminal in a modal overlay.
 *
 * Uses an iframe in embedded mode (?embed=true). Listens for postMessage
 * events from the console for lifecycle state (ready, connected, disconnected, error).
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { buildAuthenticatedConsoleUrl } from '../api/console';

interface ConsoleModalProps {
  /** Close the modal */
  onClose: () => void;
  /** Console parameters */
  role?: string;
  project?: string;
  workplan?: string | number;
  pod?: string;
  command?: string;
  /** Title shown in the modal header */
  title?: string;
}

type ConsoleStatus = 'loading' | 'ready' | 'connected' | 'disconnected' | 'error';

const CONSOLE_ORIGIN = (import.meta as any).env?.VITE_CONSOLE_URL || 'https://console.dev.viloforge.com';

export default function ConsoleModal({
  onClose,
  role,
  project,
  workplan,
  pod,
  command,
  title,
}: ConsoleModalProps) {
  const [status, setStatus] = useState<ConsoleStatus>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Build the authenticated iframe URL on mount
  useEffect(() => {
    const params = { role, project, workplan, pod, command, embed: true };
    buildAuthenticatedConsoleUrl(params).then(setIframeUrl);
  }, [role, project, workplan, pod, command]);

  // Listen for postMessage from console iframe
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      // Validate origin
      try {
        const consoleOrigin = new URL(CONSOLE_ORIGIN).origin;
        if (event.origin !== consoleOrigin && !event.origin.includes('localhost')) {
          return;
        }
      } catch {
        return;
      }

      const msg = event.data;
      if (!msg || !msg.type) return;

      switch (msg.type) {
        case 'ready':
          setStatus('ready');
          break;
        case 'connected':
          setStatus('connected');
          break;
        case 'disconnected':
          setStatus('disconnected');
          break;
        case 'error':
          setStatus('error');
          setErrorMsg(msg.message || 'Unknown error');
          break;
      }
    }

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Escape key closes modal
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        // Send disconnect to iframe before closing
        if (iframeRef.current?.contentWindow) {
          iframeRef.current.contentWindow.postMessage({ type: 'disconnect' }, '*');
        }
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleClose = useCallback(() => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.postMessage({ type: 'disconnect' }, '*');
    }
    onClose();
  }, [onClose]);

  const displayTitle = title || (pod ? `Terminal: ${pod}` : `Architect${project ? ` — ${project}` : ''}`);

  const statusColors: Record<ConsoleStatus, string> = {
    loading: 'bg-yellow-500',
    ready: 'bg-yellow-500',
    connected: 'bg-green-500',
    disconnected: 'bg-red-500',
    error: 'bg-red-500',
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-surface-container-lowest rounded-xl shadow-2xl w-full max-w-[1200px] h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary">terminal</span>
            <span className="font-headline font-bold text-on-surface">{displayTitle}</span>
            <span className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
          </div>
          <button
            onClick={handleClose}
            className="text-on-surface-variant hover:text-on-surface p-1 rounded-lg hover:bg-surface-container"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Iframe */}
        <div className="flex-1 relative">
          {status === 'loading' && !iframeUrl && (
            <div className="absolute inset-0 flex items-center justify-center text-on-surface-variant">
              Loading console...
            </div>
          )}
          {status === 'error' && (
            <div className="absolute inset-0 flex items-center justify-center text-error">
              {errorMsg || 'Connection error'}
            </div>
          )}
          {iframeUrl && (
            <iframe
              ref={iframeRef}
              src={iframeUrl}
              className="w-full h-full border-none"
              allow="clipboard-read; clipboard-write"
            />
          )}
        </div>
      </div>
    </div>
  );
}
