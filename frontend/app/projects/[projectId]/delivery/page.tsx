"use client";

import { useQuery } from "@tanstack/react-query";
import { Copy, Radio } from "lucide-react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/section-header";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelEmpty, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { OUTPUT_COLOR, OUTPUT_LABEL, SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";
import type { OutputSummary } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

/**
 * Where does this project's data go?
 *
 * `GET /projects/{id}/outputs` has aggregated every output kind since Phase 3
 * and nothing ever called it — answering this question meant opening each
 * entity in turn and scrolling past seven cards. The endpoint returns a flat
 * list; the grouping by kind is done here because "three Kafka topics and one
 * webhook" is the shape of the answer people actually want.
 */
export default function DeliveryPage() {
  const accessToken = useRequireAuth();
  const { projectId } = useParams<{ projectId: string }>();

  const outputsQuery = useQuery({
    queryKey: ["outputs", projectId],
    queryFn: () => api.listOutputs(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const outputs = outputsQuery.data ?? [];

  // Preserve the backend's ordering of kinds rather than sorting alphabetically:
  // it already emits them roughly pull-then-push, which is the order they make
  // sense to read in.
  const grouped = outputs.reduce<Record<string, OutputSummary[]>>((acc, output) => {
    (acc[output.type] ??= []).push(output);
    return acc;
  }, {});

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <SectionHeader
          icon={Radio}
          color={SECTION_COLOR.delivery}
          eyebrow="Delivery"
          title="Where this data goes"
          description="Every configured output across the project, in one place. Outputs are created on the entity that feeds them — this is the read-only view over all of them."
          action={
            <div className="flex items-baseline gap-1.5">
              <span className="font-display text-3xl font-bold tabular-nums">{outputs.length}</span>
              <span className="eyebrow">configured</span>
            </div>
          }
        />

        {outputsQuery.isPending && (
          <p className="text-sm text-ink-dim">Loading outputs…</p>
        )}

        {outputsQuery.isError && (
          <Panel tone="marked" accent="var(--sev-crit)">
            <PanelBody className="text-sm text-sev-crit">
              {(outputsQuery.error as Error).message || "Could not load outputs."}
            </PanelBody>
          </Panel>
        )}

        {outputsQuery.isSuccess && outputs.length === 0 && (
          <Panel tone="marked" accent={SECTION_COLOR.delivery}>
            <PanelBody>
              <PanelEmpty>
                No outputs yet. Open an entity and add a REST endpoint, a live stream, or a
                broker output — they will all appear here once they exist.
              </PanelEmpty>
            </PanelBody>
          </Panel>
        )}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {Object.entries(grouped).map(([kind, items]) => (
            <Panel key={kind} tone="marked" accent={OUTPUT_COLOR[kind] ?? "var(--brand)"}>
              <PanelHeader>
                <div className="flex items-center gap-2">
                  <Radio className="size-3.5" style={{ color: OUTPUT_COLOR[kind] }} />
                  <PanelTitle>{OUTPUT_LABEL[kind] ?? kind}</PanelTitle>
                </div>
                <span className="eyebrow tabular-nums">{items.length}</span>
              </PanelHeader>
              <PanelBody className="flex flex-col gap-2">
                {items.map((output) => (
                  <OutputRow key={output.id} output={output} />
                ))}
              </PanelBody>
            </Panel>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function OutputRow({ output }: { output: OutputSummary }) {
  // Public output details arrive as a bare path ("Order: /public/rest/<token>").
  // Turning it into a copyable absolute URL is the whole reason someone opens
  // this page — the path alone isn't usable from curl or CI.
  const pathMatch = output.detail.match(/(\/public\/\S+)/);
  const url = pathMatch ? `${API_URL}${pathMatch[1]}` : null;

  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-line-soft bg-surface-2 px-3 py-2">
      <p className="min-w-0 flex-1 font-mono text-[0.72rem] leading-relaxed break-all text-ink-dim">
        {output.detail}
      </p>
      {url && (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Copy URL"
          onClick={() => {
            navigator.clipboard.writeText(url);
            toast.success("URL copied");
          }}
        >
          <Copy />
        </Button>
      )}
    </div>
  );
}
