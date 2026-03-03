/**
 * Test Setup for __tests__ directory
 * Additional setup specific to tests in __tests__
 */

// Import jest-dom for extended matchers
import '@testing-library/jest-dom';

// Mock window.scrollTo
Object.defineProperty(window, 'scrollTo', {
  value: jest.fn(),
  writable: true,
});

// Mock HTMLCanvasElement.getContext
HTMLCanvasElement.prototype.getContext = jest.fn();

// Suppress specific console warnings in tests
const originalWarn = console.warn;
beforeAll(() => {
  console.warn = (...args: unknown[]) => {
    // Suppress specific warnings here
    if (
      typeof args[0] === 'string' &&
      args[0].includes('componentWillReceiveProps')
    ) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.warn = originalWarn;
});

// Global test utilities
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeValidMessage(): R;
      toBeValidConversation(): R;
    }
  }
}

// Custom matchers
expect.extend({
  toBeValidMessage(received: unknown) {
    const { isMessage } = require('@/types/chat');
    const pass = isMessage(received);

    return {
      pass,
      message: () =>
        pass
          ? `expected ${received} not to be a valid Message`
          : `expected ${received} to be a valid Message`,
    };
  },

  toBeValidConversation(received: unknown) {
    const { isConversation } = require('@/types/chat');
    const pass = isConversation(received);

    return {
      pass,
      message: () =>
        pass
          ? `expected ${received} not to be a valid Conversation`
          : `expected ${received} to be a valid Conversation`,
    };
  },
});
