"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { useViewMode } from "@/lib/hooks";
import { cn } from "@/lib/utils";

/**
 * A sub-section that collapses behind a labelled affordance in Guided mode
 * and renders exactly as-is in Advanced mode — no wrapper chrome at all, so
 * an advanced user sees zero difference from before this existed.
 *
 * The finer-grained sibling of `Stratum`'s own collapse (which hides a whole
 * stratum); this is for splitting one stratum into a default-visible part
 * and a deferred part, as Delivery does for its non-REST protocols.
 */
export function AdvancedSection({
  label,
  hasContent,
  children,
}: {
  label: string;
  /** Never collapse when the section already holds configuration. */
  hasContent?: boolean;
  children: React.ReactNode;
}) {
  const mode = useViewMode();
  const [expanded, setExpanded] = useState(false);

  const collapsible = mode === "guided" && !hasContent;
  if (!collapsible || expanded) return <>{children}</>;

  return (
    <button
      type="button"
      onClick={() => setExpanded(true)}
      className={cn(
        "flex w-full items-center gap-2 rounded-lg border border-dashed border-line px-4 py-3 text-left text-xs text-ink-dim transition-colors",
        "hover:border-ink-faint hover:text-ink",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      )}
    >
      <ChevronRight className="size-3.5 shrink-0" />
      {label}
    </button>
  );
}
