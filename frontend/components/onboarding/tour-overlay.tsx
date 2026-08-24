"use client";

import { X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { placeTooltip } from "@/lib/tour/placement";
import { STEPS } from "@/lib/tour/steps";
import { useTourStore } from "@/lib/tour/store";
import { useTourTarget } from "@/lib/tour/use-tour-target";
import { cn } from "@/lib/utils";

const RING_PAD = 8;
const TOOLTIP_WIDTH = 320;

/**
 * The spotlight tour: everything but one real, live element dims and blurs,
 * that element gets a glowing outline, and a tooltip explains it with
 * Back/Next/Skip. Mounted once inside `AppShell`, so it has `activeProjectId`
 * for the auto-start check and survives every per-page remount by keeping all
 * of its state in `useTourStore` (persisted, module-scope) rather than local
 * component state.
 *
 * The "hole" is four independently blurred panels tiling around the target
 * rect, not one full-screen blurred layer with a `mask` cutout — simpler and
 * avoids `backdrop-filter`-plus-`mask` Safari quirks. Nothing covers the
 * target itself, so it stays genuinely clickable, not just visually clear.
 */
export function TourOverlay({ hasProject }: { hasProject: boolean }) {
  const active = useTourStore((s) => s.active);
  const stepIndex = useTourStore((s) => s.stepIndex);
  const hasCompleted = useTourStore((s) => s.hasCompleted);
  const hasSkipped = useTourStore((s) => s.hasSkipped);
  const start = useTourStore((s) => s.start);
  const next = useTourStore((s) => s.next);
  const back = useTourStore((s) => s.back);
  const skip = useTourStore((s) => s.skip);

  // Checked once per mount (i.e. once per page load / navigation), not on
  // every render — start() only needs to fire the first time this app
  // instance sees a signed-in user with a project who hasn't seen the tour.
  const checkedAutoStart = useRef(false);
  useEffect(() => {
    if (checkedAutoStart.current) return;
    checkedAutoStart.current = true;
    if (!active && !hasCompleted && !hasSkipped && hasProject) start();
  }, [active, hasCompleted, hasSkipped, hasProject, start]);

  const step = active ? STEPS[stepIndex] : null;
  const target = useTourTarget(step?.selector ?? null);

  // A target that never showed up (no entities yet, an already-expanded
  // stratum with nothing to click, the specimen panel hidden below `xl`) —
  // skip forward instead of leaving the tour stuck.
  useEffect(() => {
    if (active && target.status === "not-found") next();
  }, [active, target.status, next]);

  // Click-to-advance listens on the real target element, not a synthetic
  // overlay click — the action happens exactly the way a person would
  // trigger it themselves.
  useEffect(() => {
    if (!active || !step || step.advance !== "click" || target.status !== "found") return;
    const el = target.el;
    const handleClick = () => next();
    el.addEventListener("click", handleClick);
    return () => el.removeEventListener("click", handleClick);
  }, [active, step, target, next]);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") skip();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, skip, next, back]);

  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipHeight, setTooltipHeight] = useState(140);
  const nextBtnRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    if (tooltipRef.current) setTooltipHeight(tooltipRef.current.offsetHeight);
  }, [step, target.status]);

  useEffect(() => {
    if (target.status === "found") nextBtnRef.current?.focus();
  }, [stepIndex, target.status]);

  if (!active || !step || target.status !== "found") return null;

  const { rect } = target;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1440;
  const vh = typeof window !== "undefined" ? window.innerHeight : 900;

  const holeTop = Math.max(0, rect.top - RING_PAD);
  const holeBottom = Math.min(vh, rect.top + rect.height + RING_PAD);
  const holeLeft = Math.max(0, rect.left - RING_PAD);
  const holeRight = Math.min(vw, rect.left + rect.width + RING_PAD);

  const { top, left, side } = placeTooltip(
    rect,
    { width: TOOLTIP_WIDTH, height: tooltipHeight },
    { width: vw, height: vh }
  );

  const dim = "backdrop-blur-sm bg-[color-mix(in_srgb,var(--ground)_55%,transparent)]";

  return (
    // pointer-events: none on the wrapper — a `fixed inset-0` container has a
    // hit-testable box covering the whole viewport even where nothing is
    // painted, so without this it swallows every click over the "hole" before
    // it reaches the real element underneath. Each child that should actually
    // intercept (the four dim panels, the tooltip) opts back in with
    // pointer-events: auto; the ring stays none so it never blocks the target.
    <div className="pointer-events-none fixed inset-0 z-[100]" role="dialog" aria-label="Product tour">
      {/* Four blur/dim panels tiling around the hole */}
      <div
        className={cn("pointer-events-auto fixed", dim)}
        style={{ top: 0, left: 0, width: vw, height: holeTop }}
      />
      <div
        className={cn("pointer-events-auto fixed", dim)}
        style={{ top: holeBottom, left: 0, width: vw, height: Math.max(0, vh - holeBottom) }}
      />
      <div
        className={cn("pointer-events-auto fixed", dim)}
        style={{ top: holeTop, left: 0, width: holeLeft, height: holeBottom - holeTop }}
      />
      <div
        className={cn("pointer-events-auto fixed", dim)}
        style={{
          top: holeTop,
          left: holeRight,
          width: Math.max(0, vw - holeRight),
          height: holeBottom - holeTop,
        }}
      />

      {/* Glow ring around the target — no blur, no dim, just an outline */}
      <div
        aria-hidden
        className="fixed rounded-lg border-2 border-[var(--brand)] transition-[top,left,width,height] duration-150 ease-out"
        style={{
          top: holeTop,
          left: holeLeft,
          width: holeRight - holeLeft,
          height: holeBottom - holeTop,
          boxShadow: "0 0 0 4px var(--brand-soft), 0 0 28px var(--brand)",
          pointerEvents: "none",
        }}
      />

      {/* Tooltip card */}
      <div
        ref={tooltipRef}
        className={cn(
          "pointer-events-auto fixed flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-panel)]",
          "transition-[top,left] duration-150 ease-out"
        )}
        style={{ top, left, width: TOOLTIP_WIDTH }}
        data-side={side}
      >
        <div className="flex items-start justify-between gap-3">
          <p className="eyebrow">
            Step {stepIndex + 1} of {STEPS.length}
          </p>
          <Button variant="ghost" size="icon-xs" aria-label="Skip tour" onClick={() => skip()}>
            <X />
          </Button>
        </div>
        <div>
          <h2 className="font-display text-sm font-bold tracking-tight">{step.title}</h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-dim">{step.body}</p>
        </div>
        <div className="flex items-center justify-between gap-2">
          <Button variant="ghost" size="sm" disabled={stepIndex === 0} onClick={() => back()}>
            Back
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => skip()}>
              Skip tour
            </Button>
            {step.advance === "button" && (
              <Button ref={nextBtnRef} size="sm" onClick={() => next()}>
                {stepIndex === STEPS.length - 1 ? "Finish" : "Next"}
              </Button>
            )}
          </div>
        </div>
        {step.advance === "click" && (
          <p className="text-[11px] text-ink-faint">Click the highlighted element to continue.</p>
        )}
      </div>
    </div>
  );
}
