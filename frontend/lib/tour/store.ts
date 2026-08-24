import { create } from "zustand";
import { persist } from "zustand/middleware";

import { STEPS } from "@/lib/tour/steps";

interface TourState {
  active: boolean;
  stepIndex: number;
  hasCompleted: boolean;
  hasSkipped: boolean;
  start: () => void;
  next: () => void;
  back: () => void;
  skip: () => void;
  finish: () => void;
}

/** The interactive product tour's own state — separate from `useAuthStore`
 * (an unrelated concern) and persisted the same way the existing coach-mark /
 * getting-started-checklist nudges are: per-browser, not per-account. `active`
 * and `stepIndex` are what a page reload needs to resume mid-tour; they're
 * intentionally persisted alongside the completion flags rather than reset to
 * defaults, so a refresh mid-tour doesn't restart it. */
export const useTourStore = create<TourState>()(
  persist(
    (set, get) => ({
      active: false,
      stepIndex: 0,
      hasCompleted: false,
      hasSkipped: false,
      start: () => set({ active: true, stepIndex: 0, hasSkipped: false }),
      next: () => {
        const { stepIndex } = get();
        if (stepIndex >= STEPS.length - 1) {
          set({ active: false, hasCompleted: true });
        } else {
          set({ stepIndex: stepIndex + 1 });
        }
      },
      back: () => set((s) => ({ stepIndex: Math.max(0, s.stepIndex - 1) })),
      skip: () => set({ active: false, hasSkipped: true }),
      finish: () => set({ active: false, hasCompleted: true }),
    }),
    { name: "synthflow-tour" }
  )
);
