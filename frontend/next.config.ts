// import type { NextConfig } from "next";

// const nextConfig: NextConfig = {
//   /* config options here */
// };

// export default nextConfig;

import type { NextConfig } from "next";

// API requests are proxied through this Next app so the auth cookie stays
// first-party. Frontend (vercel.app) and backend (run.app) are different sites,
// so a direct cross-site cookie is blocked as third-party by modern browsers.
// NEXT_PUBLIC_API_URL is server-only: the Cloud Run URL in prod, localhost in dev.
const NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // Plain array = "afterFiles": runs AFTER filesystem routes, so the
    // frontend's own /auth/callback page still wins over these proxy rules.
    return [
      { source: "/auth/:path*", destination: `${NEXT_PUBLIC_API_URL}/auth/:path*` },
      { source: "/api/:path*", destination: `${NEXT_PUBLIC_API_URL}/api/:path*` },
      { source: "/gmail/:path*", destination: `${NEXT_PUBLIC_API_URL}/gmail/:path*` },
    ];
  },
};

export default nextConfig;