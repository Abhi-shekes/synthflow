"use client";

import { useEffect, useRef, useState } from "react";

export interface TargetRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export type TourTargetState =
  | { status: "waiting" }
  | { status: "found"; rect: TargetRect; el: Element }
  | { status: "not-found" };

const REQUERY_MS = 100;
const TIMEOUT_MS = 6000;

function isVisible(el: Element): boolean {
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const style = getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none";
}

function findVisible(selector: string): Element | null {
  const matches = document.querySelectorAll(selector);
  for (const el of matches) {
    if (isVisible(el)) return el;
  }
  return null;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Resolves a tour step's selector to a live, continuously-tracked rect.
 *
 * Two things make this more than a `querySelector` call: it *waits* for the
 * element (a fresh page navigation, an async fetch populating the list, a
 * panel that hasn't expanded yet), and once found it re-measures every frame
 * so the spotlight follows scroll, resize, and layout shifts without a
 * separate `ResizeObserver` wire-up. If nothing visible ever matches within
 * 6s — no entities yet, a stratum that's already expanded and has no
 * collapsed trigger to click, the specimen panel hidden below `xl` — it
 * reports `"not-found"` so the caller can skip the step instead of hanging.
 *
 * Selects the first *visible* match on purpose: the same `data-tour`
 * attribute is deliberately present on both the desktop rail and the mobile
 * phone-strip nav (same array, same items, two render paths) — whichever one
 * is actually on screen at the current viewport width wins, with no
 * viewport-width branching in the step data itself.
 */
export function useTourTarget(selector: string | null): TourTargetState {
  const [state, setState] = useState<TourTargetState>({ status: "waiting" });
  const scrolledRef = useRef(false);

  useEffect(() => {
    if (!selector) {
      setState({ status: "waiting" });
      return;
    }

    scrolledRef.current = false;
    setState({ status: "waiting" });

    let cancelled = false;
    let rafId: number;
    let lastQueryAt = 0;
    let el: Element | null = null;
    const startedAt = Date.now();

    const tick = () => {
      if (cancelled) return;
      const now = Date.now();

      if (!el || !el.isConnected || !isVisible(el)) {
        if (now - lastQueryAt >= REQUERY_MS) {
          lastQueryAt = now;
          el = findVisible(selector);
        } else {
          el = null;
        }
      }

      if (el) {
        if (!scrolledRef.current) {
          scrolledRef.current = true;
          el.scrollIntoView({
            block: "center",
            behavior: prefersReducedMotion() ? "auto" : "smooth",
          });
        }
        const r = el.getBoundingClientRect();
        setState({
          status: "found",
          rect: { top: r.top, left: r.left, width: r.width, height: r.height },
          el,
        });
      } else if (now - startedAt > TIMEOUT_MS) {
        setState({ status: "not-found" });
        return;
      } else {
        setState((prev) => (prev.status === "waiting" ? prev : { status: "waiting" }));
      }

      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(rafId);
    };
  }, [selector]);

  return state;
}
