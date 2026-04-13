import { describe, it, expect } from 'vitest';
import type {
  ChatMessage,
  ToolUse,
  BridgeStreamEvent,
  BridgeLockResponse,
} from '../chat';

describe('Chat types', () => {
  it('ChatMessage has required fields', () => {
    const msg: ChatMessage = {
      id: '1',
      role: 'user',
      content: 'hello',
      timestamp: Date.now(),
    };
    expect(msg.role).toBe('user');
    expect(msg.content).toBe('hello');
  });

  it('BridgeStreamEvent discriminated union narrows correctly', () => {
    const events: BridgeStreamEvent[] = [
      { type: 'session_start', session_id: 's1' },
      { type: 'text_delta', text: 'hi' },
      { type: 'tool_use', tool: 'bash', status: 'started' },
      { type: 'agent_event' },
      { type: 'result' },
      { type: 'error', message: 'fail' },
    ];

    // Verify discriminant narrows correctly
    for (const event of events) {
      switch (event.type) {
        case 'session_start':
          expect(event.session_id).toBe('s1');
          break;
        case 'text_delta':
          expect(event.text).toBe('hi');
          break;
        case 'tool_use':
          expect(event.tool).toBe('bash');
          break;
        case 'error':
          expect(event.message).toBe('fail');
          break;
        default:
          // agent_event and result — no required fields to check
          break;
      }
    }
  });

  it('BridgeLockResponse has session_id', () => {
    const lock: BridgeLockResponse = { session_id: 'sess-abc' };
    expect(lock.session_id).toBe('sess-abc');
  });

  it('ToolUse has correct shape', () => {
    const tu: ToolUse = { tool: 'bash', status: 'completed' };
    expect(tu.tool).toBe('bash');
    expect(tu.status).toBe('completed');
  });
});
