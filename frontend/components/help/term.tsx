"use client";

import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { GLOSSARY, type GlossaryId } from "@/lib/glossary";
import { cn } from "@/lib/utils";

/**
 * Wraps a jargon term with an info affordance explaining it in plain
 * language, sourced from the one glossary (`lib/glossary.ts`) every other
 * help surface reads from.
 *
 * Click-to-toggle rather than hover-only: hover has no equivalent on a
 * touch device, and this way desktop and mobile share one implementation
 * instead of two code paths that can drift.
 */
export function Term({
  id,
  className,
  children,
}: {
  id: GlossaryId;
  className?: string;
  /** Defaults to the glossary's own label; override when the surrounding
   * copy already uses a different word for the same concept. */
  children?: React.ReactNode;
}) {
  const entry = GLOSSARY[id];
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const popoverId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span ref={rootRef} className={cn("relative inline-flex items-center gap-1", className)}>
      {children ?? entry.term}
      <button
        type="button"
        aria-expanded={open}
        aria-describedby={open ? popoverId : undefined}
        aria-label={`What is ${entry.term}?`}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex size-3.5 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors hover:text-brand focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <Info className="size-3.5" />
      </button>

      {open && (
        <span
          id={popoverId}
          role="tooltip"
          className="absolute top-full left-0 z-50 mt-1.5 w-64 rounded-lg border border-line bg-surface p-3 text-left shadow-[var(--shadow-panel)]"
        >
          <span className="block font-display text-xs font-semibold tracking-tight text-ink">
            {entry.term}
          </span>
          <span className="mt-1 block text-[13px] leading-relaxed text-ink-dim">{entry.plain}</span>
          {entry.example && (
            <span className="mt-1.5 block font-mono text-xs leading-relaxed text-ink-faint">
              {entry.example}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
