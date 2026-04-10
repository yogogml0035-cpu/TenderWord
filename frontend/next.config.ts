import type { NextConfig } from 'next';
import { parseApiBaseUrlCandidates, resolveApiBaseUrl } from './lib/apiBaseUrl';

const isProduction = process.env.NODE_ENV === 'production';
const allowedDevOrigins = Array.from(
  new Set(
    ['localhost', '127.0.0.1', ...parseApiBaseUrlCandidates(process.env.NEXT_PUBLIC_API_URL)]
      .map((candidate) => {
        try {
          return candidate.includes('://') ? new URL(candidate).hostname : candidate;
        } catch {
          return null;
        }
      })
      .filter((hostname): hostname is string => Boolean(hostname))
  )
);

const nextConfig: NextConfig = {
  // Reuse configured LAN/local API hosts so dev-only assets such as HMR can load via IP.
  allowedDevOrigins,

  // ========================================
  // API 代理配置 - 开发时转发到后端
  // ========================================
  async rewrites() {
    const apiUrl = resolveApiBaseUrl({
      raw: process.env.NEXT_PUBLIC_API_URL,
      location: null,
    });
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },

  async headers() {
    if (!isProduction) {
      return [];
    }

    return [
      {
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        source: '/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store, max-age=0',
          },
        ],
      },
    ];
  },

  // ========================================
  // 图片配置
  // ========================================
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
      },
    ],
  },

  // ========================================
  // React 严格模式
  // ========================================
  reactStrictMode: true,

  devIndicators: false,

  // ========================================
  // TypeScript 配置
  // ========================================
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
