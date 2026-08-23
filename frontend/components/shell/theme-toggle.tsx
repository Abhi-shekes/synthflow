"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
] as const;

/**
 * Three-state theme control.
 *
 * A segmented control rather than a single toggle, because "system" is a real
 * third state and a two-way toggle silently drops it — you can end up pinned to
 * light on a machine set to dark with no way back to following the OS.
 *
 * Renders a fixed-size placeholder until mounted: the resolved theme isn't
 * knowable on the server, and rendering the wrong segment as active for one
 * frame is worse than rendering none.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  // False on the server and during hydration, true afterwards — without an
  // effect that sets state on mount, which cascades a render for every viewer.
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );

  return (
    <div
      role="group"
      aria-label="Colour theme"
      className="flex items-center gap-0.5 rounded-lg border border-line bg-surface-2 p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            aria-label={label}
            aria-pressed={active}
            onClick={() => setTheme(value)}
            className={cn(
              "flex size-6 items-center justify-center rounded-md transition-colors",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              active
                ? "bg-surface text-ink shadow-sm"
                : "text-ink-faint hover:text-ink-dim"
            )}
          >
            <Icon className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}
