/**
 * Global type augmentation for @testing-library/jest-dom matchers.
 *
 * The matcher implementations are registered at runtime via
 * `jest.setup.js` (`require('@testing-library/jest-dom')`). This declaration
 * loads the matching TypeScript types globally so test files can use matchers
 * such as `toBeInTheDocument` without each test importing jest-dom.
 */
import '@testing-library/jest-dom';
