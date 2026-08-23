"use client";

import { ScrollText } from "lucide-react";

import { ActivityCard } from "@/components/activity-card";
import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/section-header";
import { SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";

/**
 * Activity across everything you can see, not one project.
 *
 * `GET /audit` has always accepted an absent `project_id` and scoped the result
 * to what the caller is allowed to read; the UI only ever passed a project.
 * That made "did anyone touch anything today?" a question you answered by
 * opening every project in turn.
 */
export default function ActivitySettingsPage() {
  useRequireAuth();

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <SectionHeader
          icon={ScrollText}
          color={SECTION_COLOR.governance}
          eyebrow="Workspace"
          title="Activity"
          description="Every change across the projects you can see — your own and any shared with you through an organization. Entries are derived from the requests themselves, so nothing can be forgotten by a route that neglected to record it."
        />

        <ActivityCard />
      </div>
    </AppShell>
  );
}
