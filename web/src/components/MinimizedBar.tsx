import type { ConsoleUrlParams } from '../contexts/ConsoleWidgetContext';

interface MinimizedBarProps {
  target: ConsoleUrlParams;
  onRestore: () => void;
}

export function MinimizedBar({ target, onRestore }: MinimizedBarProps) {
  const label = target.pod
    ? `Terminal: ${target.pod}`
    : `Architect${target.project ? ` — ${target.project}` : ''}`;

  return (
    <button
      data-testid="minimized-bar"
      onClick={onRestore}
      className="fixed bottom-0 right-4 z-[60] flex items-center gap-2 px-4 py-2 bg-surface-container-lowest border border-b-0 border-outline-variant rounded-t-lg shadow-lg hover:bg-surface-container-low transition-colors cursor-pointer"
    >
      <span className="material-symbols-outlined text-primary text-lg">terminal</span>
      <span className="text-sm font-semibold text-on-surface">{label}</span>
      <span className="material-symbols-outlined text-on-surface-variant text-[18px]">expand_less</span>
    </button>
  );
}
