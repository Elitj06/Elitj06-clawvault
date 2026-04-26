import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://5.78.198.180:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
