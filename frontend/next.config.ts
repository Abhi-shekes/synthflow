import type { NextConfig } from "next";

// The API is a separate origin in every deployment shape this app ships
// today (see ../docker-compose.yml) — CSP has to name it explicitly, or
// the app's own fetch calls and WebSocket stream previews would be
// blocked by its own Content-Security-Policy. Read at build time, same as
// every other place NEXT_PUBLIC_API_URL is consumed (see lib/api.ts).
//
// A production build (`next build` with NODE_ENV=production, which is
// what `npm run build` sets) refuses to silently fall back to localhost —
// every other place in the app that reads this variable would fall back
// too, and NEXT_PUBLIC_* values are baked into the client bundle at build
// time, so a missing one here isn't a runtime misconfiguration, it's a
// build that produced the wrong app. `docker-compose.prod.yml` already
// requires it as a build arg; this is the same requirement enforced one
// layer down, for a `next build` run outside that Dockerfile.
if (process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL must be set for a production build — it's baked into the " +
      "client bundle at build time, and every fetch call would otherwise silently " +
      "target http://localhost:8001 in whatever environment this gets deployed to."
  );
}
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const apiOrigin = (() => {
  try {
    return new URL(API_URL).origin;
  } catch {
    return "http://localhost:8001";
  }
})();
// components/stream-preview.tsx opens a raw WebSocket to the same host —
// ws(s):// is a distinct CSP scheme from http(s)://, so connect-src needs
// both or a live stream preview fails silently against the policy.
const apiWsOrigin = apiOrigin.replace(/^http/, "ws");

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "object-src 'none'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin} ${apiWsOrigin}`,
  // 'unsafe-inline' on both is a real gap, not an oversight: next-themes'
  // no-flash-of-wrong-theme script (see app/providers.tsx) is inline by
  // design — SSR can't know the visitor's OS theme before hydration — and
  // several UI primitives (Radix, cmdk) set inline `style` for popover
  // positioning. Closing this fully needs a per-request nonce threaded
  // through Next's `<script nonce>` and next-themes' script prop, which is
  // a bigger change than this pass. What CSP still buys in the meantime:
  // no remote script/style host besides 'self' can be loaded at all, no
  // page can frame this app (frame-ancestors), and any injected script
  // still can't exfiltrate to an arbitrary origin — connect-src only
  // allows this app's own API.
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  // Default position (bottom-left) sits directly on top of the app rail's
  // theme toggle (Light/Dark/System, also bottom-left), blocking clicks on
  // it in dev mode. Move the indicator out of the way instead.
  devIndicators: {
    position: "bottom-right",
  },
  // Only affects `next build` (Dockerfile.prod) — `next dev` ignores it,
  // so the bind-mounted dev workflow in docker-compose.yml is untouched.
  // Standalone bundles the minimal server + only the node_modules it
  // actually traces as used, which is what makes the production image a
  // real multi-stage build instead of shipping the full node_modules tree.
  output: "standalone",
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
