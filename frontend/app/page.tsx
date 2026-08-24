"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { FlowField } from "@/components/landing/flow-field";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import { useAuthReady } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";

const CAPABILITIES = [
  { name: "Stateful entities", detail: "records that move through a state machine, not random rows" },
  { name: "Relationships that hold", detail: "foreign keys drawn from the parent's real rows" },
  { name: "Trends & correlation", detail: "seasonal signals, random walks, coupled columns" },
  { name: "Error injection", detail: "nulls, corruption, duplicates and out-of-order events" },
  { name: "Learn from real data", detail: "fitted distributions, with PII replaced on the way in" },
  { name: "Anywhere it needs to go", detail: "REST, WebSocket, Kafka, MQTT, S3, Postgres" },
];

export default function Home() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const ready = useAuthReady();

  useEffect(() => {
    if (ready && accessToken) router.replace("/projects");
  }, [ready, accessToken, router]);

  return (
    <div className="flex flex-1 flex-col">
      <section className="relative flex min-h-[78vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <FlowField />

        {/* The ground the copy sits on, so the particles never fight the type. */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-ground via-ground/70 to-ground" />

        <div className="relative flex flex-col items-center gap-5">
          <Eyebrow>Open-source synthetic data</Eyebrow>
          <h1 className="max-w-3xl font-display text-4xl leading-[0.98] font-extrabold tracking-tight sm:text-6xl">
            Data that behaves like the real thing
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-ink-dim sm:text-lg">
            Most fake-data tools give you isolated, static records. SynthFlow models the whole
            system — entities with state, relationships that hold together, rules that fire, and
            streams that look like production traffic.
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
            <Button nativeButton={false} render={<Link href="/signup">Get started</Link>} />
            <Button
              nativeButton={false}
              variant="outline"
              render={<Link href="/login">Sign in</Link>}
            />
          </div>
          <p className="font-mono text-[11px] text-ink-faint">
            AI is entirely optional · works offline with zero LLM calls
          </p>
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-6 pb-24">
        <ul className="grid gap-px overflow-hidden rounded-xl border border-line-soft bg-line-soft sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((capability) => (
            <li key={capability.name} className="bg-surface px-4 py-4">
              <p className="font-display text-sm font-semibold tracking-tight">
                {capability.name}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-ink-dim">{capability.detail}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
