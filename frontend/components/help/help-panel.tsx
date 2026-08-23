"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { GLOSSARY } from "@/lib/glossary";
import { helpTopicFor } from "@/components/help/help-content";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The context help panel — a "?" in the header opens a slide-over reading
 * the current route. Static, route-keyed
 * content from `help-content.ts`; no backend call, so it ships in one phase.
 */
export function HelpPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const topic = helpTopicFor(pathname);

  if (!open) return null;

  return (
    <>
      <div
        aria-hidden
        className="fixed inset-0 z-40 bg-black/20"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-label="Help"
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col gap-4 overflow-y-auto",
          "border-l border-line bg-surface p-5 shadow-[var(--shadow-panel)]"
        )}
      >
        <div className="flex items-center justify-between">
          <p className="eyebrow">Help</p>
          <Button variant="ghost" size="icon-sm" aria-label="Close help" onClick={onClose}>
            <X />
          </Button>
        </div>

        {topic ? (
          <>
            <div>
              <h2 className="font-display text-lg font-bold tracking-tight">{topic.title}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-dim">{topic.what}</p>
            </div>

            {topic.actions.length > 0 && (
              <div>
                <p className="eyebrow mb-1.5">What people usually do here</p>
                <ul className="flex flex-col gap-1.5">
                  {topic.actions.map((action, i) => (
                    <li key={i} className="text-xs leading-relaxed text-ink-dim">
                      · {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {topic.glossary && topic.glossary.length > 0 && (
              <div>
                <p className="eyebrow mb-1.5">Terms on this page</p>
                <ul className="flex flex-col gap-2">
                  {topic.glossary.map((id) => (
                    <li key={id} className="rounded-md border border-line-soft bg-surface-2 p-2">
                      <p className="font-mono text-xs font-medium text-ink">
                        {GLOSSARY[id].term}
                      </p>
                      <p className="mt-0.5 text-[13px] leading-relaxed text-ink-dim">
                        {GLOSSARY[id].plain}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm leading-relaxed text-ink-dim">
            No specific help for this page yet — the Learn page below covers SynthFlow&apos;s
            concepts in general.
          </p>
        )}

        <Link
          href="/learn"
          className="mt-auto text-xs font-medium text-brand underline-offset-2 hover:underline"
          onClick={onClose}
        >
          Read the Learn page →
        </Link>
      </aside>
    </>
  );
}
