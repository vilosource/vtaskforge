import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ConsoleWidgetProvider, useConsoleWidget } from '../ConsoleWidgetContext';

function wrapper({ children }: { children: React.ReactNode }) {
  return <ConsoleWidgetProvider>{children}</ConsoleWidgetProvider>;
}

describe('ConsoleWidgetContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('initial state is closed', () => {
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    expect(result.current.isOpen).toBe(false);
    expect(result.current.target).toBeNull();
  });

  it('open sets target and shows widget', () => {
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    act(() => {
      result.current.open({ role: 'architect', project: 'my-project' });
    });
    expect(result.current.isOpen).toBe(true);
    expect(result.current.target).toEqual({ role: 'architect', project: 'my-project' });
  });

  it('close clears state', () => {
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    act(() => {
      result.current.open({ role: 'architect' });
    });
    expect(result.current.isOpen).toBe(true);
    act(() => {
      result.current.close();
    });
    expect(result.current.isOpen).toBe(false);
    expect(result.current.target).toBeNull();
  });

  it('open with different target replaces current', () => {
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    act(() => {
      result.current.open({ role: 'architect' });
    });
    expect(result.current.target).toEqual({ role: 'architect' });
    act(() => {
      result.current.open({ pod: 'worker-abc', command: 'bash' });
    });
    expect(result.current.target).toEqual({ pod: 'worker-abc', command: 'bash' });
    expect(result.current.isOpen).toBe(true);
  });

  it('layout defaults to floating', () => {
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    expect(result.current.layout).toBe('floating');
  });

  it('state persists to localStorage', () => {
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    act(() => {
      result.current.dock();
    });
    const stored = JSON.parse(localStorage.getItem('vtf_console_widget') ?? '{}');
    expect(stored.layout).toBe('docked');
  });

  it('state restores from localStorage', () => {
    localStorage.setItem(
      'vtf_console_widget',
      JSON.stringify({ layout: 'docked', dockWidth: 500 }),
    );
    const { result } = renderHook(() => useConsoleWidget(), { wrapper });
    expect(result.current.layout).toBe('docked');
    expect(result.current.dockWidth).toBe(500);
  });
});
