"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

/** Whether the viewer has asked for reduced motion. Re-reads on change, so a
 * user toggling the OS setting doesn't have to reload. */
export function useReducedMotion(): boolean {
  // A media query is an external store, so it is read through the primitive
  // built for one. Subscribing in an effect and seeding state from it would
  // render once with the wrong answer before correcting itself, which for a
  // motion preference means a frame of the animation the viewer opted out of.
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia("(prefers-reduced-motion: reduce)");
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    },
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    // Assume no preference on the server: the markup is identical either way,
    // and only the client can know.
    () => false
  );
}

/**
 * Pointer-driven tilt, capped.
 *
 * The 3D budget from the design plan lives here rather than in each call site:
 * `max` defaults to 6 degrees and callers are not expected to raise it. Past
 * roughly that angle the effect stops reading as "this surface is material" and
 * starts reading as a gimmick, and text rendering on the far edge visibly
 * degrades.
 *
 * Writes CSS custom properties instead of setting `transform` directly, so the
 * element keeps whatever transform its own stylesheet wants (a hover lift, a
 * layout translate) and composes the tilt on top.
 */
export function useTilt<T extends HTMLElement>(max = 6) {
  const ref = useRef<T | null>(null);
  const reduced = useReducedMotion();
  const frame = useRef<number | null>(null);

  const onPointerMove = useCallback(
    (event: React.PointerEvent<T>) => {
      if (reduced) return;
      const node = ref.current;
      if (!node) return;
      // Coalesce to one write per frame: pointermove fires far more often than
      // the compositor can use, and each write invalidates style.
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      const { clientX, clientY } = event;
      frame.current = requestAnimationFrame(() => {
        const box = node.getBoundingClientRect();
        const px = (clientX - box.left) / box.width - 0.5;
        const py = (clientY - box.top) / box.height - 0.5;
        node.style.setProperty("--sf-tilt-y", `${(px * max * 2).toFixed(2)}deg`);
        node.style.setProperty("--sf-tilt-x", `${(-py * max * 2).toFixed(2)}deg`);
      });
    },
    [max, reduced]
  );

  const onPointerLeave = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    const node = ref.current;
    if (!node) return;
    node.style.setProperty("--sf-tilt-y", "0deg");
    node.style.setProperty("--sf-tilt-x", "0deg");
  }, []);

  useEffect(
    () => () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    },
    []
  );

  return {
    ref,
    tiltProps: reduced
      ? {}
      : {
          onPointerMove,
          onPointerLeave,
          style: {
            transform:
              "perspective(900px) rotateX(var(--sf-tilt-x, 0deg)) rotateY(var(--sf-tilt-y, 0deg))",
            transformStyle: "preserve-3d" as const,
          },
        },
  };
}

/**
 * Debounced value, for the Strata Inspector's live specimen.
 *
 * Every edit regenerates rows, and that is real backend load the old
 * configure-then-scroll-down design never created. Debouncing is the price of
 * admission for the pinned specimen being live at all.
 */
export function useDebounced<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

/**
 * How far the viewport has scrolled through an element, 0 → 1.
 *
 * Used by the Distortion stratum, where scroll progress drives how corrupted
 * the specimen rows look. Kept in JS rather than a CSS scroll timeline because
 * the value has to reach React state to pick *which* rows to damage — the
 * purely visual scroll work (the depth rail) stays in CSS.
 */
export function useScrollProgress<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [progress, setProgress] = useState(0);
  const reduced = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    // Under reduced motion the value simply stays at its initial 0 — there is
    // nothing to reset, because nothing ever moved it.
    if (reduced || !node) return;

    let frame: number | null = null;
    const measure = () => {
      frame = null;
      const box = node.getBoundingClientRect();
      const height = window.innerHeight || 1;
      // 0 when the top edge is at the bottom of the viewport, 1 once the
      // element's top has travelled to the top of it.
      const raw = (height - box.top) / (height + box.height);
      setProgress(Math.min(1, Math.max(0, raw)));
    };
    const onScroll = () => {
      if (frame === null) frame = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      if (frame !== null) cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reduced]);

  return { ref, progress };
}
