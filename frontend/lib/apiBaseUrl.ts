const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export interface ApiBaseUrlLocation {
  protocol: string;
  hostname: string;
}

export function normalizeApiBaseUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

export function parseApiBaseUrlCandidates(raw: string | undefined): string[] {
  if (!raw) {
    return [];
  }

  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map(normalizeApiBaseUrl);
}

function buildDerivedApiBaseUrl(location: ApiBaseUrlLocation): string {
  return normalizeApiBaseUrl(`${location.protocol}//${location.hostname}:8000`);
}

function getWindowLocation(): ApiBaseUrlLocation | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return {
    protocol: window.location.protocol,
    hostname: window.location.hostname,
  };
}

export function resolveApiBaseUrl(options?: {
  raw?: string;
  location?: ApiBaseUrlLocation | null;
  fallbackUrl?: string;
}): string {
  const configuredCandidates = parseApiBaseUrlCandidates(
    options?.raw ?? process.env.NEXT_PUBLIC_API_URL
  );
  const fallbackUrl = normalizeApiBaseUrl(options?.fallbackUrl ?? DEFAULT_API_BASE_URL);
  const location = options?.location === undefined ? getWindowLocation() : options.location;

  if (!location) {
    return configuredCandidates[0] || fallbackUrl;
  }

  const currentHost = location.hostname.toLowerCase();
  const derived = buildDerivedApiBaseUrl(location);
  const candidates = Array.from(new Set([...configuredCandidates, derived]));

  const hostAliases = new Set([currentHost]);
  if (currentHost === 'localhost' || currentHost === '127.0.0.1') {
    hostAliases.add('localhost');
    hostAliases.add('127.0.0.1');
  }

  for (const candidate of candidates) {
    try {
      const candidateHost = new URL(candidate).hostname.toLowerCase();
      if (hostAliases.has(candidateHost)) {
        return candidate;
      }
    } catch {
      // Ignore malformed candidate and keep searching.
    }
  }

  if (configuredCandidates.length > 0) {
    return configuredCandidates[0];
  }

  return derived || fallbackUrl;
}

export { DEFAULT_API_BASE_URL };
