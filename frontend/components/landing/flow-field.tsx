"use client";

import dynamic from "next/dynamic";

/**
 * The landing page's particle field, behind a dynamic boundary.
 *
 * `three` is roughly 600 KB, and it exists for exactly one logged-out screen.
 * Importing it through `next/dynamic` with `ssr: false` puts it in its own
 * chunk, fetched only when someone actually lands on `/` — so nothing an
 * authenticated user loads ever pays for it.
 *
 * `ssr: false` is also a correctness requirement, not just a size one: the
 * scene reaches for `window`, `document` and a WebGL context at module scope on
 * mount, none of which exist while the page is being rendered on the server.
 *
 * The placeholder is the ground colour rather than a spinner. It sits behind
 * the hero copy, which is readable the moment the page paints; flashing a
 * loading state under a headline would draw the eye to the one part of the
 * screen that carries no information.
 */
const FlowFieldGL = dynamic(() => import("@/components/landing/flow-field-gl"), {
  ssr: false,
  loading: () => <div aria-hidden className="absolute inset-0 bg-ground" />,
});

export function FlowField() {
  return <FlowFieldGL />;
}
