"use client";

import { Gauge } from "lucide-react";
import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/section-header";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";
import { SOURCE_LABEL, SOURCES, useMetricsStream, type Source } from "@/lib/use-metrics-stream";
import { cn } from "@/lib/utils";

/** The validated categorical order, by slot. Colour follows the source, never
 * its rank — a source that goes quiet keeps its hue rather than handing it to
 * whoever is now busiest. */
const SERIES_COLOR: Record<Source, string> = {
  api: "var(--series-1)",
  rest: "var(--series-2)",
  websocket: "var(--series-3)",
  kafka: "var(--series-4)",
  mqtt: "var(--series-5)",
  plugin: "var(--series-6)",
  database_push: "var(--series-7)",
};

/**
 * The live monitor the README has promised since Phase 5.
 *
 * Until now those numbers existed only in Grafana, behind an optional Compose
 * profile — which meant that for a default install they did not exist at all.
 */
export default function MonitorPage() {
  const accessToken = useRequireAuth();
  const { latest, history, error } = useMetricsStream(accessToken);
  const [showTable, setShowTable] = useState(false);

  const current = history[history.length - 1];
  const uptime = latest ? latest.captured_at - latest.process.start_time : 0;

  // Sources that have ever produced a row. Plotting seven lines when five are
  // flat at zero is seven times the ink for the same information.
  const activeSources = SOURCES.filter(
    (source) => (latest?.generation[source]?.rows ?? 0) > 0
  );
  const plotted = activeSources.length > 0 ? activeSources : SOURCES.slice(0, 1);

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <SectionHeader
          icon={Gauge}
          color={SECTION_COLOR.monitor}
          eyebrow="Live monitor"
          title="What the engine is doing"
          description="Process-wide throughput, not per-project — the underlying metrics are deliberately unlabelled by project so that scraping them can never leak a schema."
          action={
            <span
              className={cn(
                "flex items-center gap-1.5 font-mono text-xs",
                error ? "text-sev-crit" : "text-ink-faint"
              )}
            >
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  error ? "bg-sev-crit" : "bg-sev-ok sf-pulse"
                )}
              />
              {error ? "disconnected" : "live · 2s"}
            </span>
          }
        />

        {error && (
          <Panel tone="marked" accent="var(--sev-crit)">
            <PanelBody className="text-sm text-sev-crit">{error}</PanelBody>
          </Panel>
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Rows / second"
            value={current ? current.totalRowsPerSecond.toFixed(1) : "—"}
            hint={latest ? `${format(latest.rows_total)} total` : "measuring…"}
          />
          <Stat
            label="Stream clients"
            value={latest ? String(latest.active_websocket_clients) : "—"}
            hint="WebSocket connections"
          />
          <Stat
            label="Producers"
            value={latest ? String(latest.active_producers_total) : "—"}
            hint="background output tasks"
          />
          <Stat
            label="Errors"
            value={latest ? format(latest.errors_total) : "—"}
            hint={
              current && current.errorsPerSecond > 0
                ? `${current.errorsPerSecond.toFixed(2)}/s now`
                : "none in this window"
            }
            tone={latest && latest.errors_total > 0 ? "warn" : "ok"}
          />
        </div>

        <Panel tone="marked" accent={SECTION_COLOR.monitor}>
          <PanelHeader>
            <PanelTitle>Rows per second, by source</PanelTitle>
            <Button variant="ghost" size="xs" onClick={() => setShowTable((v) => !v)}>
              {showTable ? "Show chart" : "Show table"}
            </Button>
          </PanelHeader>
          <PanelBody>
            {history.length < 2 ? (
              <p className="py-10 text-center text-xs text-ink-faint">
                Collecting the second sample — a rate needs two.
              </p>
            ) : showTable ? (
              <RateTable />
            ) : (
              <>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={history.map((sample) => ({
                        clock: sample.clock,
                        ...Object.fromEntries(
                          SOURCES.map((source) => [source, sample.rowsPerSecond[source]])
                        ),
                      }))}
                      margin={{ top: 8, right: 12, bottom: 0, left: -18 }}
                    >
                      <CartesianGrid
                        stroke="var(--line-soft)"
                        strokeDasharray="2 4"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="clock"
                        tick={{ fontSize: 10, fill: "var(--ink-faint)" }}
                        tickLine={false}
                        axisLine={{ stroke: "var(--line)" }}
                        minTickGap={40}
                      />
                      <YAxis
                        tick={{ fontSize: 10, fill: "var(--ink-faint)" }}
                        tickLine={false}
                        axisLine={false}
                        width={48}
                      />
                      <Tooltip
                        cursor={{ stroke: "var(--ink-faint)", strokeWidth: 1 }}
                        contentStyle={{
                          background: "var(--surface)",
                          border: "1px solid var(--line)",
                          borderRadius: 8,
                          fontSize: 11,
                          fontFamily: "var(--font-mono)",
                        }}
                        labelStyle={{ color: "var(--ink-dim)" }}
                        formatter={(value, name) => [
                          typeof value === "number" ? value.toFixed(2) : String(value ?? "—"),
                          SOURCE_LABEL[name as Source] ?? String(name),
                        ]}
                      />
                      {plotted.map((source) => (
                        <Line
                          key={source}
                          type="monotone"
                          dataKey={source}
                          stroke={SERIES_COLOR[source]}
                          strokeWidth={2}
                          dot={false}
                          isAnimationActive={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Identity is never colour alone: the legend is always present,
                    and three light-mode slots sit below 3:1 against the surface,
                    which obliges these labels and the table view above. */}
                <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
                  {plotted.map((source) => (
                    <li key={source} className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="h-0.5 w-3 rounded-full"
                        style={{ background: SERIES_COLOR[source] }}
                      />
                      <span className="font-mono text-xs text-ink-dim">
                        {SOURCE_LABEL[source]}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </PanelBody>
        </Panel>

        <div className="grid gap-4 xl:grid-cols-2">
          <Panel>
            <PanelHeader>
              <PanelTitle>Generation, cumulative</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="eyebrow">
                    <th className="pb-1.5 font-medium">Source</th>
                    <th className="pb-1.5 text-right font-medium">Rows</th>
                    <th className="pb-1.5 text-right font-medium">Calls</th>
                    <th className="pb-1.5 text-right font-medium">Mean</th>
                    <th className="pb-1.5 text-right font-medium">Errors</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-[13px]">
                  {SOURCES.map((source) => {
                    const row = latest?.generation[source];
                    return (
                      <tr key={source} className="border-t border-line-soft">
                        <td className="py-1.5">
                          <span className="flex items-center gap-1.5">
                            <span
                              aria-hidden
                              className="size-2 rounded-[2px]"
                              style={{ background: SERIES_COLOR[source] }}
                            />
                            <span className="text-ink-dim">{SOURCE_LABEL[source]}</span>
                          </span>
                        </td>
                        <td className="py-1.5 text-right">{format(row?.rows ?? 0)}</td>
                        <td className="py-1.5 text-right text-ink-dim">
                          {format(row?.calls ?? 0)}
                        </td>
                        <td className="py-1.5 text-right text-ink-dim">
                          {row?.calls ? `${(row.mean_seconds * 1000).toFixed(0)}ms` : "—"}
                        </td>
                        <td
                          className={cn(
                            "py-1.5 text-right",
                            (row?.errors ?? 0) > 0 ? "text-sev-crit" : "text-ink-faint"
                          )}
                        >
                          {format(row?.errors ?? 0)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle>Process</PanelTitle>
            </PanelHeader>
            <PanelBody className="grid grid-cols-2 gap-3">
              <Stat
                label="Resident memory"
                value={latest ? `${(latest.process.resident_bytes / 1e6).toFixed(0)} MB` : "—"}
                small
              />
              <Stat
                label="CPU seconds"
                value={latest ? latest.process.cpu_seconds.toFixed(1) : "—"}
                small
              />
              <Stat
                label="Open files"
                value={latest ? String(latest.process.open_fds) : "—"}
                small
              />
              <Stat label="Uptime" value={latest ? duration(uptime) : "—"} small />
            </PanelBody>
          </Panel>
        </div>
      </div>
    </AppShell>
  );

  function RateTable() {
    // The chart's own numbers, for anyone who cannot separate seven lines by
    // colour — newest first, because the last sample is the interesting one.
    const rows = [...history].reverse().slice(0, 20);
    return (
      <div className="max-h-64 overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-surface">
            <tr className="eyebrow">
              <th className="pb-1.5 font-medium">Time</th>
              {plotted.map((source) => (
                <th key={source} className="pb-1.5 text-right font-medium">
                  {SOURCE_LABEL[source]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-mono text-[13px]">
            {rows.map((sample) => (
              <tr key={sample.t} className="border-t border-line-soft">
                <td className="py-1 text-ink-faint">{sample.clock}</td>
                {plotted.map((source) => (
                  <td key={source} className="py-1 text-right">
                    {sample.rowsPerSecond[source].toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
}

function Stat({
  label,
  value,
  hint,
  tone,
  small,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "ok" | "warn";
  small?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-line bg-surface px-3.5 py-3",
        !small && "shadow-[var(--shadow-panel)]"
      )}
    >
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-1 font-display font-bold tabular-nums",
          small ? "text-lg" : "text-2xl",
          tone === "warn" && "text-sev-warn"
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 font-mono text-xs text-ink-faint">{hint}</p>}
    </div>
  );
}

function format(value: number): string {
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}k`;
  return String(Math.round(value));
}

function duration(seconds: number): string {
  if (seconds <= 0) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
