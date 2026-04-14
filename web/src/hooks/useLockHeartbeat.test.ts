import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useLockHeartbeat } from './useLockHeartbeat';

vi.mock('../api/bridge', () => ({
  checkLock: vi.fn(),
}));

import { checkLock } from '../api/bridge';

const mockCheckLock = vi.mocked(checkLock);

describe('useLockHeartbeat', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const defaultOpts = {
    project: 'proj' as string | null,
    role: 'architect',
    sessionId: 'sess-1' as string | null,
    enabled: true,
    intervalMs: 5000, // 5s for testing
    onExpired: vi.fn(),
    onConflict: vi.fn(),
  };

  it('calls checkLock after interval when enabled', async () => {
    mockCheckLock.mockResolvedValue([
      { session_id: 'sess-1', role: 'architect', project: 'proj', user: 'admin' },
    ]);

    renderHook(() => useLockHeartbeat(defaultOpts));

    expect(mockCheckLock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(5000);
    expect(mockCheckLock).toHaveBeenCalledWith('proj', 'architect');
  });

  it('does not call checkLock when disabled', async () => {
    renderHook(() => useLockHeartbeat({ ...defaultOpts, enabled: false }));

    await vi.advanceTimersByTimeAsync(10000);
    expect(mockCheckLock).not.toHaveBeenCalled();
  });

  it('does not call checkLock when project is null', async () => {
    renderHook(() => useLockHeartbeat({ ...defaultOpts, project: null }));

    await vi.advanceTimersByTimeAsync(10000);
    expect(mockCheckLock).not.toHaveBeenCalled();
  });

  it('calls onExpired when lock is gone', async () => {
    mockCheckLock.mockResolvedValue([]);

    renderHook(() => useLockHeartbeat(defaultOpts));

    await vi.advanceTimersByTimeAsync(5000);
    expect(defaultOpts.onExpired).toHaveBeenCalledOnce();
  });

  it('calls onConflict when lock held by different session', async () => {
    mockCheckLock.mockResolvedValue([
      { session_id: 'sess-other', role: 'architect', project: 'proj', user: 'alice' },
    ]);

    renderHook(() => useLockHeartbeat(defaultOpts));

    await vi.advanceTimersByTimeAsync(5000);
    expect(defaultOpts.onConflict).toHaveBeenCalledWith('alice');
  });

  it('does not call callbacks when lock matches session', async () => {
    mockCheckLock.mockResolvedValue([
      { session_id: 'sess-1', role: 'architect', project: 'proj', user: 'admin' },
    ]);

    renderHook(() => useLockHeartbeat(defaultOpts));

    await vi.advanceTimersByTimeAsync(5000);
    expect(defaultOpts.onExpired).not.toHaveBeenCalled();
    expect(defaultOpts.onConflict).not.toHaveBeenCalled();
  });

  it('clears interval on unmount', async () => {
    mockCheckLock.mockResolvedValue([
      { session_id: 'sess-1', role: 'architect', project: 'proj', user: 'admin' },
    ]);

    const { unmount } = renderHook(() => useLockHeartbeat(defaultOpts));
    unmount();

    await vi.advanceTimersByTimeAsync(10000);
    expect(mockCheckLock).not.toHaveBeenCalled();
  });

  it('does not treat network errors as expiration', async () => {
    mockCheckLock.mockRejectedValue(new Error('Network error'));

    renderHook(() => useLockHeartbeat(defaultOpts));

    await vi.advanceTimersByTimeAsync(5000);
    expect(defaultOpts.onExpired).not.toHaveBeenCalled();
    expect(defaultOpts.onConflict).not.toHaveBeenCalled();
  });
});
