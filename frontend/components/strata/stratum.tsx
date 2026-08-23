"use client";

import { Plus } from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { Eyebrow } from "@/components/ui/panel";
import { useViewMode } from "@/lib/hooks";
import { cn } from "@/lib/utils";

/**
 * The four strata of an entity, in the order data moves through the engine.
 *
 * This ordering is the whole point of the rebuild. The page it replaces stacked
 * sixteen equally-weighted cards in roughly the order the features were built,
 * so "what shape is this data" and "where does it go" sat side by side with no
 * signal that one is upstream of the other.
 */
export const STRATA = [
  {
    id: "shape",
    name: "Shape",
    color: "var(--t-string)",
    blurb: "What a row is made of — fields, types, presets and how often each is null.",
  },
  {
    id: "behaviour",
    name: "Behaviour",
    color: "var(--t-float)",
    blurb: "How values move and constrain each other over a run.",
  },
  {
    id: "distortion",
    name: "Distortion",
    color: "var(--t-enum)",
    blurb: "Damage introduced on purpose, so downstream systems meet bad data here first.",
  },
  {
    id: "delivery",
    name: "Delivery",
    color: "var(--brand)",
    blurb: "Where the rows go once they exist.",
  },
] as const;

export type StratumId = (typeof STRATA)[number]["id"];

const ActiveStratum = createContext<StratumId>("shape");

export const useActiveStratum = () => useContext(ActiveStratum);

/**
 * Tracks which stratum the reader is in, using one IntersectionObserver over
 * all four sections rather than a scroll handler per section.
 *
 * `rootMargin` biases the trip line to a third of the way down the viewport:
 * marking a stratum active the instant its top pixel appears means the rail
 * runs a screen ahead of what you are reading.
 */
export function StrataProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState<StratumId>("shape");

  useEffect(() => {
    const sections = STRATA.map((stratum) => document.getElementById(stratum.id)).filter(
      (node): node is HTMLElement => node !== null
    );
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id as StratumId);
      },
      { rootMargin: "-33% 0px -50% 0px", threshold: 0 }
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  return <ActiveStratum.Provider value={active}>{children}</ActiveStratum.Provider>;
}

/**
 * The depth rail.
 *
 * Passed strata compress to a 3px band, the current one is named, and the ones
 * below are dim. It is a position indicator that also works as navigation,
 * which is what earns it the fixed column it occupies.
 */
export function DepthRail() {
  const active = useActiveStratum();
  const activeIndex = useMemo(() => STRATA.findIndex((s) => s.id === active), [active]);

  return (
    <nav
      aria-label="Entity strata"
      className="sticky top-24 hidden h-fit w-36 shrink-0 flex-col gap-1 lg:flex"
    >
      {STRATA.map((stratum, index) => {
        const passed = index < activeIndex;
        const current = index === activeIndex;
        return (
          <a
            key={stratum.id}
            href={`#${stratum.id}`}
            aria-current={current ? "true" : undefined}
            className={cn(
              "group block rounded-md transition-all duration-300",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              passed ? "py-0.5" : "py-1"
            )}
          >
            {passed ? (
              // Compressed: it is behind you, so it costs three pixels.
              <span
                className="block h-[3px] w-full rounded-full opacity-60 transition-opacity group-hover:opacity-100"
                style={{ background: stratum.color }}
              />
            ) : (
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    "block w-[3px] shrink-0 rounded-full transition-all",
                    current ? "h-6" : "h-3 opacity-30"
                  )}
                  style={{ background: stratum.color }}
                />
                <span
                  className={cn(
                    "font-mono text-xs tracking-wide transition-colors",
                    current ? "font-medium text-ink" : "text-ink-faint group-hover:text-ink-dim"
                  )}
                >
                  {stratum.name}
                </span>
              </span>
            )}
          </a>
        );
      })}
    </nav>
  );
}

/**
 * One stratum section. `id` is the scroll anchor the rail and ⌘K link to.
 *
 * In Guided mode (SIMPLICITY_PLAN.md Track A.2), every stratum but Shape
 * collapses to a one-line summary with an "Add" affordance instead of its
 * full content — the same section, same data, just not open by default.
 * `hasContent` overrides this: a stratum a user already configured (before
 * or after switching modes) never hides what's already there.
 */
export function Stratum({
  id,
  children,
  action,
  hasContent,
}: {
  id: StratumId;
  children: React.ReactNode;
  action?: React.ReactNode;
  /** Whether this stratum already holds any configuration. When true, it's
   * never collapsed in Guided mode — only genuinely empty depth hides. */
  hasContent?: boolean;
}) {
  const stratum = STRATA.find((s) => s.id === id)!;
  const mode = useViewMode();
  const [expanded, setExpanded] = useState(false);

  const collapsible = mode === "guided" && id !== "shape" && !hasContent;
  const showContent = !collapsible || expanded;

  return (
    <section id={id} className="scroll-mt-24">
      <header className="mb-3 flex flex-wrap items-end justify-between gap-3 border-b border-line-soft pb-2">
        <div>
          <Eyebrow className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block size-1.5 rounded-full"
              style={{ background: stratum.color }}
            />
            {stratum.name}
          </Eyebrow>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-dim">{stratum.blurb}</p>
        </div>
        {showContent && action}
      </header>
      {showContent ? (
        <div className="flex flex-col gap-4">{children}</div>
      ) : (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg border border-dashed border-line px-4 py-3 text-left text-xs text-ink-dim transition-colors",
            "hover:border-ink-faint hover:text-ink",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          )}
        >
          <Plus className="size-3.5 shrink-0" style={{ color: stratum.color }} />
          <span>
            Add {stratum.name.toLowerCase()} —{" "}
            <span className="text-ink-faint">{stratum.blurb}</span>
          </span>
        </button>
      )}
    </section>
  );
}
