import { useEffect, useRef, useState } from 'react';
import { buildAuthenticatedConsoleUrl } from '../api/console';
import type { ConsoleUrlParams } from '../contexts/ConsoleWidgetContext';

export type ConsoleStatus = 'loading' | 'ready' | 'connected' | 'disconnected' | 'error';

const CONSOLE_ORIGIN = (import.meta as any).env?.VITE_CONSOLE_URL || 'https://console.dev.viloforge.com';

interface ConsoleIframeProps {
  target: ConsoleUrlParams;
  onStatusChange: (status: ConsoleStatus) => void;
  className?: string;
}

export function ConsoleIframe({ target, onStatusChange, className }: ConsoleIframeProps) {
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<ConsoleStatus>('loading');
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Build authenticated URL when target changes
  useEffect(() => {
    const params = { ...target, embed: true };
    buildAuthenticatedConsoleUrl(params).then(setIframeUrl);
  }, [target]);

  // Listen for postMessage events from the console iframe
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
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
          onStatusChange('ready');
          break;
        case 'connected':
          setStatus('connected');
          onStatusChange('connected');
          break;
        case 'disconnected':
          setStatus('disconnected');
          onStatusChange('disconnected');
          break;
        case 'error':
          setStatus('error');
          onStatusChange('error');
          break;
      }
    }

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onStatusChange]);

  return (
    <div className={`relative w-full h-full ${className ?? ''}`}>
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center text-on-surface-variant z-10">
          Loading console...
        </div>
      )}
      {iframeUrl && (
        <iframe
          ref={iframeRef}
          src={iframeUrl}
          className="w-full h-full border-none"
          allow="clipboard-read; clipboard-write"
          title="Console"
        />
      )}
    </div>
  );
}
