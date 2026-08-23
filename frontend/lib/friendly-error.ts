/**
 * Translates a handful of common backend failures into plain language for
 * the toasts that surface them (SIMPLICITY_PLAN.md Track B.4). Everything
 * else falls back to the raw message unchanged — this covers the failures
 * people hit often, not an exhaustive dictionary of every 4xx the API can
 * return.
 */
const PATTERNS: { test: RegExp; friendly: string }[] = [
  {
    test: /invalid regex|regex.*(compile|invalid)|bad pattern/i,
    friendly: "That regex doesn't compile — check the pattern.",
  },
  {
    test: /already (registered|exists|in use)|duplicate/i,
    friendly: "That name is already in use — pick another.",
  },
  {
    test: /incorrect email or password/i,
    friendly: "That email or password isn't right.",
  },
  {
    test: /could not connect|connection (refused|failed)|invalid connection string/i,
    friendly: "Couldn't connect — double-check the host, port, and credentials.",
  },
  {
    test: /not found/i,
    friendly: "That couldn't be found — it may have just been deleted or moved.",
  },
  {
    test: /unauthorized|invalid.*(token|credentials)/i,
    friendly: "That session has expired — try signing in again.",
  },
];

/** Returns a plain-language message when the error matches a known shape,
 * otherwise the error's own message (or `undefined` if it has none) — the
 * same value callers already fall back to a generic string with. */
export function friendlyError(error: unknown): string | undefined {
  if (!(error instanceof Error)) return undefined;
  const match = PATTERNS.find(({ test }) => test.test(error.message));
  return match ? match.friendly : error.message || undefined;
}
