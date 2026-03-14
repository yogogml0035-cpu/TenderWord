/**
 * MSW Server Setup for Jest
 * Configures the mock service worker server for unit tests
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Export the server instance for use in tests
export const server = setupServer(...handlers);

// Re-export handlers for custom test scenarios
export { handlers, errorHandlers, taskNotFoundHandler } from './handlers';
