/**
 * Test Utilities
 * Custom render functions and testing utilities
 */

import React from 'react';
import { render, RenderOptions } from '@testing-library/react';

/**
 * Provider wrapper for tests
 * Add any context providers here (e.g., Zustand stores, React Query, etc.)
 */
interface ProvidersProps {
  children: React.ReactNode;
}

function Providers({ children }: ProvidersProps) {
  // Add any providers here as needed:
  // - Zustand store providers
  // - React Query provider
  // - Theme providers
  // - Router providers
  return <>{children}</>;
}

/**
 * Custom render function that includes providers
 * Use this instead of @testing-library/react's render
 */
export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: Providers, ...options });
}

/**
 * Re-export everything from @testing-library/react
 */
export * from '@testing-library/react';

/**
 * Override render with our custom render
 */
export { renderWithProviders as render };

/**
 * Helper to wait for loading states to complete
 */
export async function waitForLoadingToFinish() {
  const { waitForElementToBeRemoved } = await import('@testing-library/react');
  
  // Add any loading indicators here
  // Example:
  // await waitForElementToBeRemoved(() => 
  //   screen.queryByRole('progressbar')
  // );
}

/**
 * Mock local storage for tests
 */
export function mockLocalStorage() {
  const localStorageMock = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn(),
    length: 0,
    key: jest.fn(),
  };

  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });

  return localStorageMock;
}

/**
 * Create a mock function that returns a resolved promise
 */
export function createMockResolvedFunction<T>(value: T) {
  return jest.fn().mockResolvedValue(value);
}

/**
 * Create a mock function that returns a rejected promise
 */
export function createMockRejectedFunction(error: Error) {
  return jest.fn().mockRejectedValue(error);
}

/**
 * Flush all pending promises
 */
export function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/**
 * Wait for a specific amount of time (for async testing)
 */
export function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
