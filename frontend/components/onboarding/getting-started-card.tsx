"use client";

import { Check, X } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { dismissChecklist, isChecklistDismissed, readChecklistStep } from "@/lib/checklist";
import { cn } from "@/lib/utils";

const noopSubscribe = () => () => {};

/**
 * A small, honest progress card on /projects (Track C.4) — not a gate, just
 * a nudge. Hides itself once every required step is done or the viewer
 * dismisses it; either way that choice is remembered per-browser.
 */
export function GettingStartedCard({ hasProject }: { hasProject: boolean }) {
  // Read via useSyncExternalStore, not an effect + setState — localStorage
  // isn't knowable on the server, and reading it in an effect means calling
  // setState from inside that effect, a pattern this codebase avoids (see
  // useAuthHydrated in lib/hooks.ts).
  const persistedDismissed = useSyncExternalStore(noopSubscribe, isChecklistDismissed, () => true);
  const entityDone = useSyncExternalStore(noopSubscribe, () => readChecklistStep("entity"), () => false);
  const generatedDone = useSyncExternalStore(noopSubscribe, () => readChecklistStep("generated"), () => false);
  const deliveryDone = useSyncExternalStore(noopSubscribe, () => readChecklistStep("delivery"), () => false);
  const [dismissedThisRender, setDismissedThisRender] = useState(false);

  const requiredDone = hasProject && entityDone && generatedDone;
  if (persistedDismissed || dismissedThisRender || requiredDone) return null;

  const steps = [
    { label: "Create or open a project", done: hasProject },
    { label: "Add or import an entity", done: entityDone },
    { label: "Generate your first sample", done: generatedDone },
    { label: "Connect a delivery target (optional)", done: deliveryDone, optional: true },
  ];

  return (
    <Panel tone="flat">
      <PanelHeader>
        <PanelTitle>Getting started</PanelTitle>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Dismiss checklist"
          onClick={() => {
            dismissChecklist();
            setDismissedThisRender(true);
          }}
        >
          <X className="size-3.5" />
        </Button>
      </PanelHeader>
      <PanelBody>
        <ul className="flex flex-col gap-1.5">
          {steps.map((step) => (
            <li key={step.label} className="flex items-center gap-2 text-xs">
              <span
                aria-hidden
                className={cn(
                  "flex size-4 shrink-0 items-center justify-center rounded-full border",
                  step.done
                    ? "border-sev-ok bg-sev-ok/10 text-sev-ok"
                    : "border-line text-transparent"
                )}
              >
                <Check className="size-2.5" />
              </span>
              <span className={cn(step.done ? "text-ink-faint line-through" : "text-ink-dim")}>
                {step.label}
              </span>
            </li>
          ))}
        </ul>
      </PanelBody>
    </Panel>
  );
}
