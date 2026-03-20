import '@testing-library/jest-dom';

// jsdom does not implement EventSource. Provide a no-op stub so components that
// use useSSE do not throw "EventSource is not defined" in the test environment.
// Tests that need to exercise SSE behaviour should replace this with their own
// mock via vi.stubGlobal / beforeEach.
if (typeof EventSource === 'undefined') {
  class EventSourceStub {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 2;
    onopen: null = null;
    onerror: null = null;
    readyState = 0;
    constructor(_url: string, _options?: EventSourceInit) {}
    addEventListener() {}
    removeEventListener() {}
    close() {}
  }
  // @ts-expect-error — intentional global stub for jsdom test environment
  globalThis.EventSource = EventSourceStub;
}
