import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ========================================
  // API 代理配置 - 开发时转发到后端
  // ========================================
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },

  // ========================================
  // 图片配置
  // ========================================
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
      },
    ],
  },

  // ========================================
  // React 严格模式
  // ========================================
  reactStrictMode: true,

  // ========================================
  // TypeScript 配置
  // ========================================
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
