import type { Config } from 'jest';
import nextJest from 'next/jest.js';

const createJestConfig = nextJest({
  // Provide the path to your Next.js app to load next.config.js and .env files in your test environment
  dir: './',
});

// Add any custom config to be passed to Jest
const config: Config = {
  coverageProvider: 'v8',
  testEnvironment: 'jsdom',
  setupFiles: ['<rootDir>/polyfills.js'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testMatch: ['**/?(*.)+(spec|test).[jt]s?(x)'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
    '^until-async$': '<rootDir>/test-shims/until-async.ts',
    '^msw/node$': '<rootDir>/node_modules/msw/lib/node/index.js',
    '^@mswjs/interceptors/ClientRequest$':
      '<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/ClientRequest/index.cjs',
    '^@mswjs/interceptors/fetch$':
      '<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/fetch/index.cjs',
    '^@mswjs/interceptors/XMLHttpRequest$':
      '<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/XMLHttpRequest/index.cjs',
    '^@mswjs/interceptors$': '<rootDir>/node_modules/@mswjs/interceptors/lib/node/index.cjs',
  },
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/node_modules-wsl/',
    '<rootDir>/.next/',
    '<rootDir>/e2e/',
    '<rootDir>/__tests__/mocks/',
    '<rootDir>/__tests__/utils/',
  ],
  modulePathIgnorePatterns: ['<rootDir>/node_modules-wsl/'],
  collectCoverageFrom: [
    'components/**/*.{js,jsx,ts,tsx}',
    'hooks/**/*.{js,jsx,ts,tsx}',
    'lib/**/*.{js,jsx,ts,tsx}',
    'stores/**/*.{js,jsx,ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
  ],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  transformIgnorePatterns: ['node_modules/(?!(msw|@mswjs|until-async|outvariant|graphql-ws|ws))/'],
  // Exclude mocks directory from coverage
  coveragePathIgnorePatterns: ['<rootDir>/mocks/'],
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
export default createJestConfig(config);
