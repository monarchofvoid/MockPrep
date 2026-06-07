import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  /**
   * Development proxy — forwards all API calls to the FastAPI backend.
   *
   * Why two separate source patterns?
   * ────────────────────────────────
   * All requests use /_api as a prefix so they never collide with Next.js
   * page routes (/mocks, /profile, /attempts would serve page HTML instead
   * of being proxied).
   *
   * BUT Next.js 15 App Router has a second conflict: if the PATH AFTER
   * stripping /_api starts with /api/, Next.js treats it as an internal
   * API route and intercepts it before the rewrite proxy fires — even
   * when no file exists at app/api/ or pages/api/.
   *
   * Backend routes affected:
   *   /_api/api/v1/wallet/*      → would resolve to internal /api route
   *   /_api/api/v1/payments/*    → same issue
   *   /_api/api/v1/ai-mock/*     → same issue
   *   /_api/api/v1/ai-jobs/*     → same issue
   *
   * Solution: give those paths a DIFFERENT proxy prefix (/_apiv1/) so the
   * path after stripping the prefix does NOT start with /api/.
   * api.ts uses /_apiv1 as BASE_V1 for all /api/v1/* backend routes.
   *
   * Non-/api/v1 routes (auth, mocks, analytics, etc.) continue to use /_api.
   */
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return []
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    return [
      // ── /api/v1/* backend routes — use /_apiv1 prefix to avoid Next.js
      //    internal /api/* route interception
      {
        source: '/_apiv1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },

      // ── All other backend routes (auth, mocks, analytics, attempts, etc.)
      {
        source: '/_api/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ]
  },

  images: { remotePatterns: [] },
  typescript: { ignoreBuildErrors: false },
  reactStrictMode: true,
}

export default nextConfig