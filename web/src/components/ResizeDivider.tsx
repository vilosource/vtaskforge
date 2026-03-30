import { useCallback, useRef, useState } from 'react';

interface ResizeDividerProps {
  onResize: (deltaX: number) => void;
}

export function ResizeDivider({ onResize }: ResizeDividerProps) {
  const [isDragging, setIsDragging] = useState(false);
  const lastX = useRef(0);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    setIsDragging(true);
    lastX.current = e.clientX;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  }, []);

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging) return;
      const delta = lastX.current - e.clientX;
      lastX.current = e.clientX;
      onResize(delta);
    },
    [isDragging, onResize],
  );

  const handlePointerUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  return (
    <div
      className={`absolute left-0 top-0 h-full w-1 cursor-col-resize z-10 transition-colors ${
        isDragging ? 'bg-primary' : 'hover:bg-primary/50'
      }`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      data-testid="resize-divider"
    />
  );
}
