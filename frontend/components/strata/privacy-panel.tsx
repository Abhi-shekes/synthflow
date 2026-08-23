"use client";

import { useMutation } from "@tanstack/react-query";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Term } from "@/components/help/term";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { fieldFill, isPiiPreset } from "@/lib/field-visual";
import { useAuthStore } from "@/lib/store";
import type { Entity, PrivacyReport } from "@/lib/types";
import { cn } from "@/lib/utils";

const NONE = "__none__";

/**
 * k-anonymity and l-diversity on generated rows.
 *
 * Phase 10 shipped this endpoint and the frontend never gained so much as a
 * client method for it, so the entire privacy story was invisible in the
 * product it shipped in.
 *
 * Two things this deliberately does not do. It does not guess the
 * quasi-identifiers — which columns an attacker already knows is a claim about
 * a threat model, not a property of the data, and a wrong guess here produces a
 * confident pass that means nothing. And it never rewrites the data to reach a
 * threshold: suppressing or generalising rows would silently change the
 * distribution the project was configured to produce.
 */
export function PrivacyPanel({
  projectId,
  entity,
}: {
  projectId: string;
  entity: Entity;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [selected, setSelected] = useState<string[]>([]);
  const [sensitive, setSensitive] = useState<string>(NONE);
  const [count, setCount] = useState(1000);
  const [k, setK] = useState(5);
  const [l, setL] = useState(2);
  const [report, setReport] = useState<PrivacyReport | null>(null);

  const run = useMutation({
    mutationFn: () =>
      api.privacyReport(accessToken!, projectId, entity.id, {
        count,
        quasi_identifiers: selected,
        sensitive_field: sensitive === NONE ? null : sensitive,
        k_threshold: k,
        l_threshold: l,
      }),
    onSuccess: setReport,
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not measure that"),
  });

  const toggle = (name: string) =>
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );

  // A sensible starting point rather than a silent default: fields already
  // marked as personal data are the ones most likely to be known.
  const suggested = entity.fields.filter((f) => isPiiPreset(f.preset)).map((f) => f.name);

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle>Re-identification risk</PanelTitle>
        {report && (
          <span
            className={cn(
              "flex items-center gap-1.5 rounded px-2 py-0.5 font-mono text-xs",
              report.passes
                ? "bg-sev-ok/10 text-sev-ok"
                : "bg-sev-crit/10 text-sev-crit"
            )}
          >
            {report.passes ? <ShieldCheck className="size-3" /> : <ShieldAlert className="size-3" />}
            {report.passes ? "passes" : "fails"}
          </span>
        )}
      </PanelHeader>
      <PanelBody className="flex flex-col gap-3.5">
        <p className="text-xs leading-relaxed text-ink-dim">
          Generates rows and measures how many share each combination of the columns an attacker
          is assumed to already know. Reports only — nothing is altered to make it pass.
        </p>

        <div className="flex flex-col gap-1.5">
          <Label className="eyebrow">
            <Term id="quasi_identifier">Quasi-identifiers</Term> — what an attacker already knows
          </Label>
          <div className="flex flex-wrap gap-1.5">
            {entity.fields.map((field) => {
              const on = selected.includes(field.name);
              return (
                <button
                  key={field.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(field.name)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-xs transition-colors",
                    "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    on
                      ? "border-brand bg-brand-soft text-ink"
                      : "border-line-soft bg-surface-2 text-ink-dim hover:border-ink-faint"
                  )}
                >
                  <span
                    aria-hidden
                    className="size-2 rounded-[2px]"
                    style={{ background: fieldFill(field.field_type, field.preset) }}
                  />
                  {field.name}
                </button>
              );
            })}
          </div>
          {selected.length === 0 && suggested.length > 0 && (
            <button
              type="button"
              onClick={() => setSelected(suggested)}
              className="self-start font-mono text-xs text-brand underline-offset-2 hover:underline"
            >
              use the {suggested.length} field{suggested.length === 1 ? "" : "s"} marked as
              personal data
            </button>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <div className="flex flex-col gap-1 sm:col-span-2">
            <Label className="eyebrow">Sensitive field — what they must not learn</Label>
            <Select value={sensitive} onValueChange={(v) => setSensitive(v ?? NONE)}>
              <SelectTrigger className="h-7 w-full text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>none — measure k only</SelectItem>
                {entity.fields.map((field) => (
                  <SelectItem key={field.id} value={field.name}>
                    {field.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field label="Rows" value={count} onChange={setCount} min={1} />
          <Field label={<Term id="k_anonymity">k ≥</Term>} value={k} onChange={setK} min={1} />
        </div>

        <div className="flex flex-wrap items-end gap-3">
          {sensitive !== NONE && (
            <Field label={<Term id="l_diversity">l ≥</Term>} value={l} onChange={setL} min={1} />
          )}
          <Button
            size="sm"
            disabled={selected.length === 0 || run.isPending}
            onClick={() => run.mutate()}
          >
            {run.isPending ? "Measuring…" : "Measure"}
          </Button>
          {selected.length === 0 && (
            <span className="text-xs text-ink-faint">
              Choose at least one quasi-identifier.
            </span>
          )}
        </div>

        {report && <Report report={report} />}
      </PanelBody>
    </Panel>
  );
}

function Report({ report }: { report: PrivacyReport }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line-soft bg-surface-2 p-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="k"
          value={String(report.k)}
          hint={`threshold ${report.k_threshold}`}
          bad={!report.k_passes}
        />
        <Metric
          label="l"
          value={report.l === null ? "—" : String(report.l)}
          hint={report.l === null ? "no sensitive field" : `threshold ${report.l_threshold}`}
          bad={!report.l_passes}
        />
        <Metric label="Groups" value={String(report.groups)} hint="distinct combinations" />
        <Metric
          label="Rows below k"
          value={String(report.rows_below_k)}
          hint={`${(report.unique_row_share * 100).toFixed(1)}% of rows`}
          bad={report.rows_below_k > 0}
        />
      </div>

      <p className="text-xs leading-relaxed text-ink-dim">{report.summary}</p>

      {report.smallest_groups.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="eyebrow">Smallest groups — where re-identification starts</p>
          <ul className="flex flex-col gap-1">
            {report.smallest_groups.map((group, index) => (
              <li
                key={index}
                className="flex flex-wrap items-baseline gap-2 rounded border border-line-soft bg-surface px-2 py-1 font-mono text-[13px]"
              >
                <span
                  className={cn(
                    "shrink-0 font-medium",
                    group.rows < report.k_threshold ? "text-sev-crit" : "text-ink-dim"
                  )}
                >
                  {group.rows} row{group.rows === 1 ? "" : "s"}
                </span>
                <span className="text-ink-faint">
                  {Object.entries(group.values)
                    .map(([key, value]) => `${key}=${String(value)}`)
                    .join(" · ")}
                </span>
                {group.distinct_sensitive_values !== undefined && (
                  <span className="ml-auto text-ink-faint">
                    {group.distinct_sensitive_values} distinct sensitive
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  bad,
}: {
  label: string;
  value: string;
  hint: string;
  bad?: boolean;
}) {
  return (
    <div>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "font-display text-xl font-bold tabular-nums",
          bad ? "text-sev-crit" : "text-ink"
        )}
      >
        {value}
      </p>
      <p className="font-mono text-xs text-ink-faint">{hint}</p>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  min,
}: {
  label: React.ReactNode;
  value: number;
  onChange: (next: number) => void;
  min: number;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="eyebrow">{label}</Label>
      <Input
        type="number"
        min={min}
        className="h-7 text-xs"
        value={value}
        onChange={(e) => onChange(Math.max(min, Number(e.target.value) || min))}
      />
    </div>
  );
}
