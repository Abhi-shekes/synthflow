"use client";

import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { useParams } from "next/navigation";

import { ActivityCard } from "@/components/activity-card";
import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/section-header";
import { ShareProjectCard } from "@/components/share-project-card";
import { VersionHistoryCard } from "@/components/version-history-card";
import { api } from "@/lib/api";
import { SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";

/**
 * Who can see this project, what changed, and how to get back.
 *
 * The three used to sit at the bottom of the project page below seven
 * unrelated cards, which is roughly the worst place for the controls you reach
 * for when something has gone wrong.
 */
export default function GovernancePage() {
  const accessToken = useRequireAuth();
  const currentUser = useAuthStore((s) => s.user);
  const { projectId } = useParams<{ projectId: string }>();

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const project = projectQuery.data;

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <SectionHeader
          icon={ScrollText}
          color={SECTION_COLOR.governance}
          eyebrow="Governance"
          title="History & access"
          description="Snapshots of the design you can compare against and roll back to, who the project is shared with, and a record of every change that has been made to it."
        />

        {project && (
          <ShareProjectCard
            projectId={projectId}
            organizationId={project.organization_id}
            isOwner={!!currentUser && project.owner_id === currentUser.id}
            accent={SECTION_COLOR.governance}
          />
        )}

        <VersionHistoryCard projectId={projectId} />
        <ActivityCard projectId={projectId} />
      </div>
    </AppShell>
  );
}
