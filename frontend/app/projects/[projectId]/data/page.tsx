"use client";

import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ConnectionsPanel, PushPanel } from "@/components/data/connections-panel";
import { LearnSourcePanel } from "@/components/data/learn-source-panel";
import { LookupsPanel } from "@/components/data/lookups-panel";
import { JobsCard } from "@/components/jobs-card";
import { RecordStoresCard } from "@/components/record-stores-card";
import { SectionHeader } from "@/components/section-header";
import { Eyebrow, Panel, PanelBody, PanelEmpty } from "@/components/ui/panel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";

/**
 * Everything about data that isn't the schema.
 *
 * Jobs, record stores, reference tables and connections all used to be cards on
 * the project or entity page, mixed in with schema editing. They are a
 * different activity — you come here to run something or to look at what a run
 * produced, not to design.
 */
export default function DataPage() {
  const accessToken = useRequireAuth();
  const { projectId } = useParams<{ projectId: string }>();
  const [storeEntityId, setStoreEntityId] = useState("");

  const entitiesQuery = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => api.listEntities(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const entities = entitiesQuery.data ?? [];
  // Record stores are per-entity, so this page needs a subject. Defaulting to
  // the first entity beats an empty panel that looks broken until you notice
  // the picker.
  const selectedId = storeEntityId || entities[0]?.id || "";
  const selected = entities.find((entity) => entity.id === selectedId);

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <SectionHeader
          icon={Database}
          color={SECTION_COLOR.data}
          eyebrow="Data"
          title="Data & jobs"
          description="Queue and schedule generation runs, keep records between calls, and manage the reference tables and connections the project draws on."
        />

        <JobsCard projectId={projectId} entities={entities} accent={SECTION_COLOR.data} />

        <section className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <Eyebrow>Record stores</Eyebrow>
              <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-dim">
                A store is what makes two generation calls related — the same customer exists
                tomorrow, and can receive new orders.
              </p>
            </div>
            {entities.length > 0 && (
              <Select value={selectedId} onValueChange={(v) => setStoreEntityId(v ?? "")}>
                <SelectTrigger className="w-56">
                  <SelectValue placeholder="Choose an entity" />
                </SelectTrigger>
                <SelectContent>
                  {entities.map((entity) => (
                    <SelectItem key={entity.id} value={entity.id}>
                      {entity.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {selected ? (
            <RecordStoresCard projectId={projectId} entity={selected} />
          ) : (
            <Panel>
              <PanelBody>
                <PanelEmpty>
                  This project has no entities yet. Add one on the system map, then come back
                  to give it a record store.
                </PanelEmpty>
              </PanelBody>
            </Panel>
          )}
        </section>

        <LookupsPanel projectId={projectId} />
        <ConnectionsPanel projectId={projectId} />
        <PushPanel projectId={projectId} entities={entities} />
        <LearnSourcePanel projectId={projectId} />
      </div>
    </AppShell>
  );
}
