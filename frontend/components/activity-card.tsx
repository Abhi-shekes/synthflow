"use client";

import { useQuery } from "@tanstack/react-query";

import {
  Panel,
  PanelBody,
  PanelEmpty,
  PanelHeader,
  PanelTitle,
} from "@/components/ui/panel";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { AuditEvent } from "@/lib/types";

/**
 * What has changed in this project, and who changed it.
 *
 * The entries are derived from requests rather than written by the routes,
 * so they arrive as `POST /projects/{id}/entities` rather than "added an
 * entity". `describe` turns that back into a sentence — but only for routes
 * it recognises, falling back to the raw method and template rather than
 * guessing, because a wrong description in an audit log is worse than a
 * terse one.
 */
export function ActivityCard({ projectId }: { projectId?: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);

  const events = useQuery({
    // `projectId` in the key, undefined included: the unscoped feed at
    // /settings/activity and a project's own feed are different results and
    // must not share a cache entry.
    queryKey: ["audit", projectId ?? "all"],
    queryFn: () => api.listAuditEvents(accessToken!, { projectId, limit: 100 }),
    enabled: !!accessToken,
    // Polled rather than invalidated from every mutation on the page.
    // Entries come from middleware over *any* request, including ones made
    // from another tab, a teammate's session or an API key — so there is no
    // set of local mutations that invalidating after would cover. An
    // activity feed is also the one card you expect to move on its own.
    refetchInterval: 10_000,
  });

  const rows = events.data ?? [];

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle>Activity</PanelTitle>
        <span className="eyebrow">live · 10s</span>
      </PanelHeader>
      <PanelBody className="flex flex-col gap-3">
        <p className="text-xs leading-relaxed text-ink-dim">
          Every change {projectId ? "to this project" : "you can see"}, and whether it came from
          a browser session or an API key. Reads are not recorded — only things that changed
          something.
        </p>
        {rows.length === 0 ? (
          <PanelEmpty>Nothing recorded yet.</PanelEmpty>
        ) : (
          <ul className="flex max-h-96 flex-col gap-1 overflow-y-auto text-xs">
            {rows.map((event) => (
              <li
                key={event.id}
                className="flex flex-wrap items-baseline gap-2 rounded-lg border border-line-soft bg-surface-2 px-2.5 py-1.5"
              >
                <span className="w-28 shrink-0 font-mono text-xs text-ink-faint">
                  {event.created_at.slice(0, 16).replace("T", " ")}
                </span>
                {event.status_code >= 400 && (
                  <span className="rounded bg-sev-crit/10 px-1.5 font-mono text-xs font-medium text-sev-crit">
                    refused {event.status_code}
                  </span>
                )}
                <span>{describe(event)}</span>
                <span className="ml-auto font-mono text-xs text-ink-faint">
                  {event.actor_kind === "api_key"
                    ? `key sfk_${event.api_key_prefix}…`
                    : (event.actor_email ?? "a deleted user")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </PanelBody>
    </Panel>
  );
}

/** Route templates this UI can put into words.
 *
 * Deliberately partial. An unrecognised route falls through to its method
 * and template rather than being guessed at — an audit entry that describes
 * the wrong thing is worse than one that is merely terse. */
const PHRASES: Record<string, Record<string, string>> = {
  "/projects/{project_id}": { PATCH: "renamed the project", DELETE: "deleted the project" },
  "/projects/{project_id}/entities": { POST: "added an entity" },
  "/projects/{project_id}/entities/{entity_id}": { DELETE: "deleted an entity" },
  "/projects/{project_id}/entities/{entity_id}/fields": { POST: "added a field" },
  "/projects/{project_id}/entities/{entity_id}/generate": { POST: "generated rows" },
  "/projects/{project_id}/relationships": { POST: "added a relationship" },
  "/projects/{project_id}/database-connections": { POST: "added a database connection" },
  "/projects/{project_id}/database-connections/{connection_id}/push": {
    POST: "pushed rows to a database",
  },
  "/projects/{project_id}/storage-targets": { POST: "added a storage target" },
  "/projects/{project_id}/jobs": { POST: "queued a job" },
  "/projects/{project_id}/versions": { POST: "saved a version" },
  "/projects/{project_id}/versions/{version}": { DELETE: "deleted a version" },
  "/projects/{project_id}/versions/{version}/rollback": { POST: "rolled the project back" },
  "/projects/{project_id}/organization": { PUT: "changed who the project is shared with" },
  "/projects/{project_id}/entities/{entity_id}/record-stores": { POST: "added a record store" },
};

function describe(event: AuditEvent): string {
  const phrase = PHRASES[event.route]?.[event.method];
  if (phrase) return phrase;
  // The honest fallback: say exactly what the request was.
  return `${event.method} ${event.route}`;
}
