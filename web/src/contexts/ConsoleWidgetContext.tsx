import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

export type WidgetLayout = 'floating' | 'docked' | 'minimized';

export interface ConsoleUrlParams {
  role?: string;
  project?: string;
  workplan?: string | number;
  pod?: string;
  command?: string;
}

interface ConsoleWidgetState {
  isOpen: boolean;
  layout: WidgetLayout;
  target: ConsoleUrlParams | null;
  position: { x: number; y: number };
  size: { width: number; height: number };
  dockWidth: number;
}

interface ConsoleWidgetActions {
  open: (params: ConsoleUrlParams) => void;
  close: () => void;
  minimize: () => void;
  restore: () => void;
  dock: () => void;
  float: () => void;
  popOut: () => void;
  setPosition: (pos: { x: number; y: number }) => void;
  setSize: (size: { width: number; height: number }) => void;
  setDockWidth: (width: number) => void;
}

type ConsoleWidgetContextValue = ConsoleWidgetState & ConsoleWidgetActions;

const STORAGE_KEY = 'vtf_console_widget';

const DEFAULT_STATE: ConsoleWidgetState = {
  isOpen: false,
  layout: 'floating',
  target: null,
  position: { x: 100, y: 100 },
  size: { width: 840, height: 600 },
  dockWidth: 500,
};

function loadPersistedState(): Partial<ConsoleWidgetState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function persistState(state: Partial<ConsoleWidgetState>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage may be unavailable
  }
}

const ConsoleWidgetContext = createContext<ConsoleWidgetContextValue>({
  ...DEFAULT_STATE,
  open: () => {},
  close: () => {},
  minimize: () => {},
  restore: () => {},
  dock: () => {},
  float: () => {},
  popOut: () => {},
  setPosition: () => {},
  setSize: () => {},
  setDockWidth: () => {},
});

export function ConsoleWidgetProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ConsoleWidgetState>(() => {
    const persisted = loadPersistedState();
    return {
      ...DEFAULT_STATE,
      layout: persisted.layout ?? DEFAULT_STATE.layout,
      position: persisted.position ?? DEFAULT_STATE.position,
      size: persisted.size ?? DEFAULT_STATE.size,
      dockWidth: persisted.dockWidth ?? DEFAULT_STATE.dockWidth,
    };
  });

  // Persist layout preferences when they change
  useEffect(() => {
    persistState({
      layout: state.layout,
      position: state.position,
      size: state.size,
      dockWidth: state.dockWidth,
    });
  }, [state.layout, state.position, state.size, state.dockWidth]);

  const open = useCallback((params: ConsoleUrlParams) => {
    setState((prev) => ({ ...prev, isOpen: true, target: params }));
  }, []);

  const close = useCallback(() => {
    setState((prev) => ({ ...prev, isOpen: false, target: null }));
  }, []);

  const minimize = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'minimized' }));
  }, []);

  const restore = useCallback(() => {
    setState((prev) => ({
      ...prev,
      layout: prev.layout === 'minimized' ? 'floating' : prev.layout,
    }));
  }, []);

  const dock = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'docked' }));
  }, []);

  const float = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'floating' }));
  }, []);

  const popOut = useCallback(() => {
    // Will be handled in the widget component
    setState((prev) => ({ ...prev, isOpen: false, target: null }));
  }, []);

  const setPosition = useCallback((pos: { x: number; y: number }) => {
    setState((prev) => ({ ...prev, position: pos }));
  }, []);

  const setSize = useCallback((size: { width: number; height: number }) => {
    setState((prev) => ({ ...prev, size }));
  }, []);

  const setDockWidth = useCallback((dockWidth: number) => {
    setState((prev) => ({ ...prev, dockWidth }));
  }, []);

  const value: ConsoleWidgetContextValue = {
    ...state,
    open,
    close,
    minimize,
    restore,
    dock,
    float,
    popOut,
    setPosition,
    setSize,
    setDockWidth,
  };

  return (
    <ConsoleWidgetContext.Provider value={value}>
      {children}
    </ConsoleWidgetContext.Provider>
  );
}

export function useConsoleWidget(): ConsoleWidgetContextValue {
  return useContext(ConsoleWidgetContext);
}
