"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { QualityReport } from "@/lib/types";

/**
 * Generate rows and report on them. Three sections in a deliberate order,
 * strongest claim first: violations (the output contradicts its own field
 * declaration — a defect), findings (what the engine saw happen, which is
 * where silent failures show up), then the user's own assertions.
 *
 * The same report backs `synthflow check`, so what a reviewer sees here and
 * what fails a build are the same numbers rather than two implementations
 * that can disagree.
 */
export function QualityReportDialog({
  projectId,
  entityId,
}: {
  projectId: string;
  entityId: string;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(1000);
  const [assertionText, setAssertionText] = useState("");
  const [report, setReport] = useState<QualityReport | null>(null);

  const run = useMutation({
    mutationFn: () => {
      const assertions = assertionText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      return api.qualityReport(accessToken!, projectId, entityId, count, assertions);
    },
    onSuccess: setReport,
    onError: (error: Error) => toast.error(error.message || "Could not run the report"),
  });

  const violations = report?.observation.violations ?? [];
  const findings = report?.diagnostics.findings ?? [];

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setReport(null);
      }}
    >
      <DialogTrigger render={<Button variant="outline">Quality report</Button>} />
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Quality report</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="quality-count">Rows</Label>
              <Input
                id="quality-count"
                type="number"
                className="w-32"
                value={count}
                onChange={(e) => setCount(Number(e.target.value) || 1)}
              />
            </div>
            <Button onClick={() => run.mutate()} disabled={run.isPending}>
              {run.isPending ? "Generating…" : "Run"}
            </Button>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="quality-assertions">Assertions (one per line, optional)</Label>
            <Textarea
              id="quality-assertions"
              className="min-h-20 font-mono text-xs"
              placeholder={"email.unique\nstatus.share_paid >= 0.6\nage.mean > 30"}
              value={assertionText}
              onChange={(e) => setAssertionText(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Same expression language as rules and formulas, over per-field
              aggregates. Run once to see every name you can reference.
            </p>
          </div>

          {report && (
            <div className="flex flex-col gap-4 border-t pt-4">
              <p className="text-sm">
                <span
                  className={
                    report.passes ? "font-medium text-green-600" : "font-medium text-red-600"
                  }
                >
                  {report.passes ? "PASS" : "FAIL"}
                </span>{" "}
                — {report.rows} rows generated
              </p>

              {violations.length > 0 && (
                <div className="flex flex-col gap-2 rounded-md border p-3">
                  <p className="text-sm font-medium">
                    {violations.length} violation
                    {violations.length === 1 ? "" : "s"} — the output contradicts the
                    field&apos;s own declaration
                  </p>
                  <ul className="flex flex-col gap-1 text-xs">
                    {violations.map((v) => (
                      <li key={`${v.field}-${v.kind}`}>
                        <span className="font-mono">{v.field}</span>: {v.detail}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {findings.length > 0 && (
                <div className="flex flex-col gap-2 rounded-md border border-dashed p-3">
                  <p className="text-sm font-medium">What happened during generation</p>
                  <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-muted-foreground">
                    {findings.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}

              {report.assertions.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium">Assertions</p>
                  {report.assertions.map((a) => (
                    <div key={a.expression} className="flex gap-2 text-xs">
                      <span
                        className={
                          a.error
                            ? "font-mono text-amber-600"
                            : a.passed
                              ? "font-mono text-green-600"
                              : "font-mono text-red-600"
                        }
                      >
                        {a.error ? "ERR " : a.passed ? "PASS" : "FAIL"}
                      </span>
                      <span className="font-mono">{a.expression}</span>
                      {a.error && <span className="text-muted-foreground">— {a.error}</span>}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">Generated columns</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="text-muted-foreground">
                      <tr className="text-left">
                        <th className="py-1 pr-3 font-normal">field</th>
                        <th className="py-1 pr-3 font-normal">type</th>
                        <th className="py-1 pr-3 font-normal">nulls</th>
                        <th className="py-1 pr-3 font-normal">distinct</th>
                        <th className="py-1 pr-3 font-normal">mean</th>
                        <th className="py-1 pr-3 font-normal">looks like</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {report.observation.columns.map((c) => (
                        <tr key={c.name} className="border-t">
                          <td className="py-1 pr-3">{c.name}</td>
                          <td className="py-1 pr-3 opacity-60">{c.observed_type}</td>
                          <td className="py-1 pr-3">{c.nulls}</td>
                          <td className="py-1 pr-3">{c.distinct}</td>
                          <td className="py-1 pr-3">{c.mean ?? "—"}</td>
                          <td className="py-1 pr-3 opacity-60">{c.fitted ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {report.observation.correlations.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium">Correlations</p>
                  {report.observation.correlations.map((c) => (
                    <code key={c.between.join("-")} className="text-xs text-muted-foreground">
                      {c.between[0]} ↔ {c.between[1]} = {c.correlation}
                    </code>
                  ))}
                </div>
              )}

              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer">
                  Names you can use in an assertion ({report.available_names.length})
                </summary>
                <p className="mt-1 font-mono leading-relaxed">
                  {report.available_names.join(", ")}
                </p>
              </details>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
