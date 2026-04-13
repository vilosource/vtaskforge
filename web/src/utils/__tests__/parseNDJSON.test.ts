import { describe, it, expect } from 'vitest';
import { parseNDJSONLine } from '../parseNDJSON';

describe('parseNDJSONLine', () => {
  it('returns null for empty string', () => {
    expect(parseNDJSONLine('')).toBeNull();
  });

  it('returns null for whitespace-only string', () => {
    expect(parseNDJSONLine('   ')).toBeNull();
    expect(parseNDJSONLine('\n')).toBeNull();
    expect(parseNDJSONLine('\t')).toBeNull();
  });

  it('parses session_start event', () => {
    const line = '{"type":"session_start","session_id":"sess-123"}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'session_start', session_id: 'sess-123' });
  });

  it('parses text_delta event', () => {
    const line = '{"type":"text_delta","text":"Hello world"}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'text_delta', text: 'Hello world' });
  });

  it('parses tool_use event with started status', () => {
    const line = '{"type":"tool_use","tool":"bash","status":"started"}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'tool_use', tool: 'bash', status: 'started' });
  });

  it('parses tool_use event with completed status', () => {
    const line = '{"type":"tool_use","tool":"edit","status":"completed"}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'tool_use', tool: 'edit', status: 'completed' });
  });

  it('parses result event', () => {
    const line = '{"type":"result","message":"Done","token_usage":{"input":100,"output":50}}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({
      type: 'result',
      message: 'Done',
      token_usage: { input: 100, output: 50 },
    });
  });

  it('parses error event', () => {
    const line = '{"type":"error","message":"Something went wrong"}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'error', message: 'Something went wrong' });
  });

  it('parses agent_event (passthrough, unknown fields)', () => {
    const line = '{"type":"agent_event","foo":"bar","nested":{"a":1}}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'agent_event', foo: 'bar', nested: { a: 1 } });
  });

  it('throws SyntaxError on malformed JSON', () => {
    expect(() => parseNDJSONLine('{not valid json')).toThrow(SyntaxError);
  });

  it('passes through events with unknown type (OCP — extensible)', () => {
    const line = '{"type":"future_event","data":"something"}';
    const event = parseNDJSONLine(line);
    expect(event).toEqual({ type: 'future_event', data: 'something' });
  });
});
