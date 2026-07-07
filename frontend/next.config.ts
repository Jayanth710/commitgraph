// import type { NextConfig } from "next";

// const nextConfig: NextConfig = {
//   /* config options here */
// };

// export default nextConfig;

import type { NextConfig } from "next";

// The proxy TARGET: the real backend URL. This is a SERVER-SIDE value and is
// intentionally NOT the browser's API base (which must be same-origin "" so the
// auth cookie stays first-party). One variable cannot be both, so the backend
// URL is hardcoded here (it is public, not a secret) with a localhost fallback
// for dev. BACKEND_ORIGIN can override it if the backend URL ever changes.
const BACKEND_ORIGIN =
  process.env.BACKEND_ORIGIN ||
  (process.env.NODE_ENV === "production"
    ? "https://commitgraph-api-929144091055.us-central1.run.app"
    : "http://localhost:8000");

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // Plain array = "afterFiles": runs AFTER filesystem routes, so the
    // frontend's own /auth/callback page still wins over these proxy rules.
    return [
      { source: "/auth/:path*", destination: `${BACKEND_ORIGIN}/auth/:path*` },
      { source: "/api/:path*", destination: `${BACKEND_ORIGIN}/api/:path*` },
      { source: "/gmail/:path*", destination: `${BACKEND_ORIGIN}/gmail/:path*` },
    ];
  },
};

export default nextConfig;