import '@testing-library/jest-dom';

// Polyfill IntersectionObserver for jsdom (used by ChatWindow smart scroll)
if (typeof IntersectionObserver === 'undefined') {
  class MockIntersectionObserver {
    callback: IntersectionObserverCallback;
    constructor(callback: IntersectionObserverCallback) {
      this.callback = callback;
    }
    observe() {
      // Immediately report as intersecting (at bottom)
      this.callback(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        this as unknown as IntersectionObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  }
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = MockIntersectionObserver;
}
