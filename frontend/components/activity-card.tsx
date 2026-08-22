"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
export function ActivityCard({ projectId }: { projectId: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);

  const events = useQuery({
    queryKey: ["audit", projectId],
    queryFn: () => api.listAuditEvents(accessToken!, { projectId, limit: 100 }),
    enabled: !!accessToken,
  });

  const rows = events.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Activity</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Every change to this project, and whether it came from a browser
          session or an API key. Reads are not recorded — only things that
          changed something.
        </p>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing recorded yet.
          </p>
        ) : (
          <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto text-sm">
            {rows.map((event) => (
              <li
                key={event.id}
                className="flex flex-wrap items-baseline gap-2 rounded border px-2 py-1"
              >
                <span className="w-32 shrink-0 text-xs text-muted-foreground">
                  {event.created_at.slice(0, 16).replace("T", " ")}
                </span>
                {event.status_code >= 400 && (
                  <span className="rounded bg-destructive/10 px-1.5 text-xs font-medium text-destructive">
                    refused {event.status_code}
                  </span>
                )}
                <span>{describe(event)}</span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {event.actor_kind === "api_key"
                    ? `key sfk_${event.api_key_prefix}…`
                    : (event.actor_email ?? "a deleted user")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
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
};

function describe(event: AuditEvent): string {
  const phrase = PHRASES[event.route]?.[event.method];
  if (phrase) return phrase;
  // The honest fallback: say exactly what the request was.
  return `${event.method} ${event.route}`;
}
