/* eslint-disable @typescript-eslint/no-require-imports */
require('@testing-library/jest-dom');

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

Object.defineProperty(window, 'scrollTo', {
  value: jest.fn(),
  writable: true,
});

HTMLCanvasElement.prototype.getContext = jest.fn();

if (typeof globalThis.BroadcastChannel === 'undefined') {
  class BroadcastChannelMock {
    constructor(name) {
      this.name = name;
      this.onmessage = null;
      this.onmessageerror = null;
    }

    postMessage(_message) {
      void _message;
    }

    close() {}

    addEventListener() {}

    removeEventListener() {}

    dispatchEvent() {
      return true;
    }
  }

  globalThis.BroadcastChannel = BroadcastChannelMock;
}

const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render is no longer supported')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
