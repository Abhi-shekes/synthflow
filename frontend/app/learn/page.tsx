"use client";

import { AppShell } from "@/components/app-shell";
import { allHelpTopics } from "@/components/help/help-content";
import { Eyebrow, Panel, PanelBody } from "@/components/ui/panel";
import { GLOSSARY, type GlossaryId } from "@/lib/glossary";
import { useRequireAuth } from "@/lib/hooks";

const GLOSSARY_ORDER: GlossaryId[] = [
  "rule",
  "formula",
  "trend",
  "event_trigger",
  "workflow",
  "lookup_attachment",
  "geo_route",
  "error_injection",
  "pii",
  "null_rate",
  "quasi_identifier",
  "k_anonymity",
  "l_diversity",
  "rest_output",
  "websocket_output",
  "kafka_output",
  "rabbitmq_output",
  "mqtt_output",
  "webhook_output",
  "plugin_output",
];

/**
 * SynthFlow's feature list (README.md), translated into plain language with
 * one example each (SIMPLICITY_PLAN.md Track C.5). The context help panel
 * and every `<Term>` popover link here for "tell me more" — this page and
 * they both read from the same `lib/glossary.ts` and `help-content.ts`, so
 * a definition changes in one place rather than three.
 */
export default function LearnPage() {
  const accessToken = useRequireAuth();
  if (!accessToken) return null;

  return (
    <AppShell>
      <div className="flex w-full max-w-3xl flex-col gap-8">
        <header>
          <Eyebrow>Reference</Eyebrow>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight">Learn</h1>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-dim">
            SynthFlow generates fake data that behaves like the real thing — records that carry
            state, relate to each other, follow rules, and can be deliberately messy so you can
            test how your own system copes. Everything below is optional depth: a project needs
            only entities and fields to generate its first rows.
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <p className="eyebrow">Pages</p>
          <div className="flex flex-col gap-3">
            {allHelpTopics().map((topic) => (
              <Panel key={topic.title} tone="flat">
                <PanelBody className="flex flex-col gap-1.5">
                  <p className="font-display text-sm font-semibold tracking-tight">
                    {topic.title}
                  </p>
                  <p className="text-xs leading-relaxed text-ink-dim">{topic.what}</p>
                  {topic.actions.length > 0 && (
                    <ul className="mt-1 flex flex-col gap-1">
                      {topic.actions.map((action, i) => (
                        <li key={i} className="text-xs leading-relaxed text-ink-faint">
                          · {action}
                        </li>
                      ))}
                    </ul>
                  )}
                </PanelBody>
              </Panel>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <p className="eyebrow">Terms</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {GLOSSARY_ORDER.map((id) => {
              const entry = GLOSSARY[id];
              return (
                <Panel key={id} tone="flat">
                  <PanelBody className="flex flex-col gap-1">
                    <p className="font-mono text-xs font-medium text-ink">{entry.term}</p>
                    <p className="text-[13px] leading-relaxed text-ink-dim">{entry.plain}</p>
                    {entry.example && (
                      <p className="mt-0.5 font-mono text-xs leading-relaxed text-ink-faint">
                        {entry.example}
                      </p>
                    )}
                  </PanelBody>
                </Panel>
              );
            })}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
