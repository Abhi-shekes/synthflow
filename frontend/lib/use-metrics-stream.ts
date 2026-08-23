"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { MetricsSummary } from "@/lib/types";

/** Generation sources, in the order the backend declares them. Fixed rather
 * than derived from a response so a series keeps its colour when a source that
 * has never been used drops out of a sample. */
export const SOURCES = [
  "api",
  "rest",
  "websocket",
  "kafka",
  "mqtt",
  "plugin",
  "database_push",
] as const;

export type Source = (typeof SOURCES)[number];

export const SOURCE_LABEL: Record<Source, string> = {
  api: "API",
  rest: "REST",
  websocket: "WebSocket",
  kafka: "Kafka",
  mqtt: "MQTT",
  plugin: "Plugin",
  database_push: "DB push",
};

export interface RateSample {
  /** Milliseconds, for the x axis. */
  t: number;
  clock: string;
  rowsPerSecond: Record<Source, number>;
  totalRowsPerSecond: number;
  errorsPerSecond: number;
}

const WINDOW = 60;

/**
 * Polls `/metrics/summary` and turns cumulative counters into rates.
 *
 * The endpoint is deliberately stateless — it returns totals plus the server's
 * `captured_at` and nothing else — so the differencing has to happen somewhere,
 * and here is the only place with two samples and the elapsed time between
 * them.
 *
 * Two details that matter:
 *
 * - Elapsed time comes from the *server's* `captured_at`, never the browser
 *   clock. A tab that was throttled or a machine whose clock drifted would
 *   otherwise produce rates that are confidently wrong rather than obviously
 *   missing.
 * - Counters can go backwards, when the backend restarts and its counters reset
 *   to zero. A negative delta is dropped rather than rendered, because a spike
 *   of minus four million rows/sec is worse than a one-tick gap.
 */
export function useMetricsStream(token: string | null | undefined, intervalMs = 2000) {
  const [latest, setLatest] = useState<MetricsSummary | null>(null);
  const [history, setHistory] = useState<RateSample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const previous = useRef<MetricsSummary | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      // Nobody is looking at a hidden tab, and polling one keeps a laptop
      // awake for a chart no one can see.
      if (document.hidden) {
        timer = setTimeout(tick, intervalMs);
        return;
      }
      try {
        const sample = await api.metricsSummary(token);
        if (cancelled) return;
        setError(null);
        setLatest(sample);

        const before = previous.current;
        if (before) {
          const elapsed = sample.captured_at - before.captured_at;
          if (elapsed > 0) {
            const rowsPerSecond = {} as Record<Source, number>;
            let total = 0;
            for (const source of SOURCES) {
              const now = sample.generation[source]?.rows ?? 0;
              const then = before.generation[source]?.rows ?? 0;
              const rate = (now - then) / elapsed;
              // Backend restart: counters reset, delta goes negative.
              const clean = rate < 0 ? 0 : rate;
              rowsPerSecond[source] = clean;
              total += clean;
            }
            const errorDelta = (sample.errors_total - before.errors_total) / elapsed;
            setHistory((prev) =>
              [
                ...prev,
                {
                  t: sample.captured_at * 1000,
                  clock: new Date(sample.captured_at * 1000).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  }),
                  rowsPerSecond,
                  totalRowsPerSecond: total,
                  errorsPerSecond: errorDelta < 0 ? 0 : errorDelta,
                },
              ].slice(-WINDOW)
            );
          }
        }
        previous.current = sample;
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Lost the monitor");
      }
      if (!cancelled) timer = setTimeout(tick, intervalMs);
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [token, intervalMs]);

  return { latest, history, error };
}
