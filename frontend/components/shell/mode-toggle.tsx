"use client";

import { Compass, Radar } from "lucide-react";

import { useSetViewMode, useViewMode } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "guided", label: "Guided", Icon: Compass },
  { value: "advanced", label: "Advanced", Icon: Radar },
] as const;

/**
 * Two-state control for Guided vs Advanced (SIMPLICITY_PLAN.md Track A).
 *
 * Nothing is ever deleted or locked behind either state — Guided only
 * defers depth (Behaviour/Distortion/advanced-Delivery, and the less-common
 * nav sections) behind an "Add"/"Advanced" affordance. This toggle is the
 * one place to flip that default; every collapse elsewhere reads the same
 * `user.ui_mode`, so there is exactly one switch to find.
 */
export function ModeToggle() {
  const mode = useViewMode();
  const setMode = useSetViewMode();

  return (
    <div
      role="group"
      aria-label="Guided or advanced view"
      className="flex items-center gap-0.5 rounded-lg border border-line bg-surface-2 p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = mode === value;
        return (
          <button
            key={value}
            type="button"
            title={label}
            aria-label={label}
            aria-pressed={active}
            onClick={() => setMode.mutate(value)}
            className={cn(
              "flex h-7 items-center gap-1.5 rounded-md px-2 font-mono text-xs transition-colors",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              active ? "bg-surface text-ink shadow-sm" : "text-ink-faint hover:text-ink-dim"
            )}
          >
            <Icon className="size-3.5" />
            <span className="hidden lg:inline">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
