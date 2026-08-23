/**
 * The getting-started checklist's per-viewer progress (Track C.4). Backed by
 * `localStorage`, not the account — it's a lightweight nudge, not a record
 * that needs to survive a device change or show up in an audit log.
 */
const STEP_KEYS = {
  entity: "sf-checklist:entity",
  generated: "sf-checklist:generated",
  delivery: "sf-checklist:delivery",
} as const;

export type ChecklistStep = keyof typeof STEP_KEYS;

export function markChecklistStep(step: ChecklistStep) {
  try {
    localStorage.setItem(STEP_KEYS[step], "1");
  } catch {
    // Private browsing or storage disabled — the checklist just won't
    // remember progress this session, which is a fine degrade.
  }
}

export function readChecklistStep(step: ChecklistStep): boolean {
  try {
    return localStorage.getItem(STEP_KEYS[step]) === "1";
  } catch {
    return false;
  }
}

const DISMISSED_KEY = "sf-checklist:dismissed";

export function isChecklistDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function dismissChecklist() {
  try {
    localStorage.setItem(DISMISSED_KEY, "1");
  } catch {
    // ignore
  }
}
