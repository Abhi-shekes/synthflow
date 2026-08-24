"use client";

import type { ReactNode } from "react";

import { NebulaScene } from "@/components/auth/nebula-scene";
import { useSpotlight } from "@/lib/motion";

/**
 * The backdrop the two logged-out auth pages share: a domain-warped nebula
 * with a field of motes drifting through it, both coloured by the same
 * field-type scale that colours a schema everywhere else in the product.
 * It lives behind the same dynamic-import boundary flow-field.tsx already
 * established, so `three` still never reaches the authenticated bundle.
 */
export function AuthScene({ children }: { children: ReactNode }) {
  const { ref, spotProps } = useSpotlight<HTMLDivElement>();

  return (
    <div
      ref={ref}
      {...spotProps}
      className="relative flex flex-1 items-center justify-center overflow-hidden px-4 py-12"
    >
      <NebulaScene className="absolute inset-0" />

      {/* No vignette layer here: the shader already resolves its own frame to
          --ground, and stacking a second falloff on top of that one only
          flattens the gas it is meant to be framing. */}

      {/* Cursor-tracked highlight, in the brand hue — a light on the glass in
          front of the scene, not a light source inside it. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(420px circle at var(--sf-spot-x, 50%) var(--sf-spot-y, 38%), color-mix(in srgb, var(--brand) 7%, transparent), transparent 65%)",
        }}
      />

      <div className="relative z-10 w-full max-w-sm">{children}</div>
    </div>
  );
}
