import {
  normalizeApiBaseUrl,
  parseApiBaseUrlCandidates,
  resolveApiBaseUrl,
  type ApiBaseUrlLocation,
} from '@/lib/apiBaseUrl';

describe('apiBaseUrl helpers', () => {
  it('normalizes API base URLs by removing trailing slashes', () => {
    expect(normalizeApiBaseUrl('http://localhost:8000///')).toBe('http://localhost:8000');
  });

  it('parses comma separated API base URL candidates', () => {
    expect(
      parseApiBaseUrlCandidates(' http://localhost:8000/ , , http://10.11.11.44:8000 ')
    ).toEqual(['http://localhost:8000', 'http://10.11.11.44:8000']);
  });

  it('prefers the configured candidate that matches the current host', () => {
    const location: ApiBaseUrlLocation = {
      protocol: 'http:',
      hostname: '10.11.11.44',
    };

    expect(
      resolveApiBaseUrl({
        raw: 'http://localhost:8000,http://10.11.11.44:8000',
        location,
      })
    ).toBe('http://10.11.11.44:8000');
  });

  it('falls back to the first configured candidate without browser location', () => {
    expect(
      resolveApiBaseUrl({
        raw: 'http://localhost:8000,http://10.11.11.44:8000',
        location: null,
      })
    ).toBe('http://localhost:8000');
  });
});
