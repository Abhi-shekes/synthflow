"use client";

import dynamic from "next/dynamic";

import { cn } from "@/lib/utils";

/**
 * The nebula, behind the same `next/dynamic({ ssr: false })` boundary as
 * `flow-field.tsx`: `three` reaches for `window`/`document`/WebGL at mount,
 * none of which exist during SSR, and it is ~600KB that only the two
 * logged-out auth pages need.
 *
 * No loading placeholder — the ground colour already sits underneath, and
 * the scene resolves to it at the frame edges anyway, so an empty first
 * paint is indistinguishable from the finished one's border.
 */
const NebulaSceneGL = dynamic(() => import("@/components/auth/nebula-scene-gl"), {
  ssr: false,
  loading: () => null,
});

export function NebulaScene({ className }: { className?: string }) {
  return (
    <div className={cn("relative", className)}>
      <NebulaSceneGL />
    </div>
  );
}
