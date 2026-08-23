"use client";

import { X } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { cn } from "@/lib/utils";

const STORAGE_PREFIX = "sf-coachmark-seen:";

function hasSeen(id: string): boolean {
  try {
    return localStorage.getItem(STORAGE_PREFIX + id) === "1";
  } catch {
    return true; // fail closed — never show a broken coach mark forever
  }
}

function markSeen(id: string) {
  try {
    localStorage.setItem(STORAGE_PREFIX + id, "1");
  } catch {
    // ignore
  }
}

/**
 * A one-time, dismissible intro banner for a surface a new user is about to
 * see for the first time (SIMPLICITY_PLAN.md Track C.3) — the System Map and
 * the entity page's four strata. Dismiss is permanent, per `id`.
 *
 * Deliberately not a DOM-anchored spotlight tooltip: the System Map is a
 * pan/zoom canvas and the strata scroll past each other, and pinning a
 * tooltip to a specific element across both would be fragile. An inline
 * banner using the same `Panel` primitive as everything else says the same
 * thing without hijacking scroll or guessing at element positions.
 */
export function CoachMark({
  id,
  className,
  children,
}: {
  id: string;
  className?: string;
  children: React.ReactNode;
}) {
  // localStorage isn't knowable during SSR, and reading it in an effect
  // means calling setState from that effect — a pattern this codebase
  // avoids (see useAuthHydrated in lib/hooks.ts). useSyncExternalStore reads
  // it synchronously during render instead, with no subscription needed
  // since nothing else changes this value out from under the component.
  const seenOnLoad = useSyncExternalStore(
    () => () => {},
    () => hasSeen(id),
    () => true // server snapshot: treat as already seen, so nothing flashes in
  );
  const [dismissedThisRender, setDismissedThisRender] = useState(false);

  if (seenOnLoad || dismissedThisRender) return null;

  return (
    <Panel tone="marked" className={cn("mb-3", className)}>
      <PanelBody className="flex items-start justify-between gap-3">
        <div className="text-xs leading-relaxed text-ink-dim">{children}</div>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Dismiss"
          onClick={() => {
            markSeen(id);
            setDismissedThisRender(true);
          }}
        >
          <X className="size-3.5" />
        </Button>
      </PanelBody>
    </Panel>
  );
}
