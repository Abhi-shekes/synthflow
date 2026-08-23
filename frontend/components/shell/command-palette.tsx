"use client";

import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import {
  Boxes,
  CornerDownLeft,
  Database,
  FolderOpen,
  Gauge,
  KeyRound,
  LogOut,
  Monitor,
  Moon,
  Radio,
  ScrollText,
  Search,
  Sun,
  Users,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { fieldFill, FIELD_TYPE_ABBR } from "@/lib/field-visual";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { Entity } from "@/lib/types";

/** Fields are the long tail — one project can hold several hundred. They are
 * only rendered once you have typed something, and capped even then, because
 * cmdk keeps every item in the DOM and filters in place. */
const FIELD_LIMIT = 60;
const RESTING_LIMIT = 6;

/**
 * ⌘K over projects, entities, fields and actions.
 *
 * With 135 API operations behind the UI, search is the only navigation that
 * scales — a menu deep enough to reach everything is a menu nobody reads.
 *
 * Fields are searchable, not just entities: "which entity has `customer_id`?"
 * is otherwise answerable only by opening every entity in turn.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const params = useParams<{ projectId?: string }>();
  const accessToken = useAuthStore((s) => s.accessToken);
  const logout = useAuthStore((s) => s.logout);
  const lastProjectId = useAuthStore((s) => s.lastProjectId);
  const { setTheme } = useTheme();

  const projectId = params?.projectId ?? lastProjectId ?? undefined;
  const searching = query.trim().length > 0;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((prev) => {
          if (prev) setQuery("");
          return !prev;
        });
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(accessToken!),
    enabled: !!accessToken && open,
  });

  // Only the open project's entities. Fetching every project's entities to make
  // them all searchable would be N+1 requests on a keystroke, and cross-project
  // entity search is not a thing anyone has asked for.
  const entitiesQuery = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => api.listEntities(accessToken!, projectId!),
    enabled: !!accessToken && !!projectId && open,
  });

  const projects = projectsQuery.data ?? [];
  const entities = useMemo(() => entitiesQuery.data ?? [], [entitiesQuery.data]);

  const fields = useMemo(() => {
    if (!searching) return [];
    const out: { entity: Entity; field: Entity["fields"][number] }[] = [];
    for (const entity of entities) {
      for (const field of entity.fields) {
        out.push({ entity, field });
        if (out.length >= FIELD_LIMIT) return out;
      }
    }
    return out;
  }, [entities, searching]);

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router]
  );

  const run = useCallback((action: () => void) => {
    setOpen(false);
    action();
  }, []);

  const loading = projectsQuery.isLoading || entitiesQuery.isLoading;
  const visibleProjects = searching ? projects : projects.slice(0, RESTING_LIMIT);
  const visibleEntities = searching ? entities : entities.slice(0, RESTING_LIMIT);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-keyshortcuts="Meta+K Control+K"
        className="group flex h-8 items-center gap-2 rounded-lg border border-line bg-surface-2 px-2.5 text-xs text-ink-faint transition-colors hover:border-ink-faint hover:text-ink-dim focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:w-52 lg:w-64"
      >
        <Search className="size-3.5 shrink-0" />
        <span className="hidden flex-1 text-left sm:inline">Search…</span>
        <kbd className="hidden shrink-0 rounded border border-line bg-surface px-1 py-px font-mono text-[10px] text-ink-faint sm:inline">
          ⌘K
        </kbd>
      </button>

      <Command.Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) setQuery("");
        }}
        label="Search SynthFlow"
        shouldFilter
        className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh]"
        overlayClassName="fixed inset-0 z-40 bg-ground"
        contentClassName="relative z-50 flex w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-[0_24px_60px_rgb(0_0_0/45%)]"
      >
        <div className="flex items-center gap-2.5 border-b border-line-soft px-4">
          <Search className="size-4 shrink-0 text-ink-faint" />
          <Command.Input
            value={query}
            onValueChange={setQuery}
            placeholder="Search projects, entities, fields…"
            className="h-12 w-full bg-transparent text-[0.9rem] outline-none placeholder:text-ink-faint"
          />
          {searching && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] text-ink-faint hover:text-ink-dim"
            >
              clear
            </button>
          )}
        </div>

        <Command.List className="max-h-[min(62vh,30rem)] flex-1 overflow-y-auto overscroll-contain p-2">
          {loading && (
            <Command.Loading>
              <p className="px-2 py-6 text-center text-xs text-ink-faint">Loading…</p>
            </Command.Loading>
          )}

          <Command.Empty>
            <div className="flex flex-col items-center gap-1.5 px-3 py-10 text-center">
              <p className="text-sm text-ink-dim">
                No match for <span className="font-mono text-ink">{query}</span>
              </p>
              <p className="max-w-xs text-xs leading-relaxed text-ink-faint">
                Search covers project names, entity names, and the fields of the project you
                have open.
              </p>
            </div>
          </Command.Empty>

          {projectId && (
            <Group heading="Go to" count={5}>
              <Item
                value="system map canvas entities"
                icon={<Boxes />}
                kind="page"
                onSelect={() => go(`/projects/${projectId}`)}
              >
                <Highlight text="System map" query={query} />
              </Item>
              <Item
                value="data jobs record stores lookup tables schedules"
                icon={<Database />}
                kind="page"
                onSelect={() => go(`/projects/${projectId}/data`)}
              >
                <Highlight text="Data & jobs" query={query} />
              </Item>
              <Item
                value="delivery outputs rest websocket kafka mqtt webhook"
                icon={<Radio />}
                kind="page"
                onSelect={() => go(`/projects/${projectId}/delivery`)}
              >
                <Highlight text="Delivery" query={query} />
              </Item>
              <Item
                value="live monitor metrics throughput errors"
                icon={<Gauge />}
                kind="page"
                onSelect={() => go(`/projects/${projectId}/monitor`)}
              >
                <Highlight text="Live monitor" query={query} />
              </Item>
              <Item
                value="governance versions history activity sharing"
                icon={<ScrollText />}
                kind="page"
                onSelect={() => go(`/projects/${projectId}/governance`)}
              >
                <Highlight text="Governance" query={query} />
              </Item>
            </Group>
          )}

          {visibleEntities.length > 0 && (
            <Group
              heading="Entities"
              count={entities.length}
              hint={!searching && entities.length > RESTING_LIMIT ? "type to see all" : undefined}
            >
              {visibleEntities.map((entity) => (
                <Item
                  key={entity.id}
                  value={`entity ${entity.name}`}
                  icon={<Boxes />}
                  kind="entity"
                  meta={`${entity.fields.length} field${entity.fields.length === 1 ? "" : "s"}`}
                  onSelect={() => go(`/projects/${projectId}/entities/${entity.id}`)}
                >
                  <Highlight text={entity.name} query={query} />
                </Item>
              ))}
            </Group>
          )}

          {fields.length > 0 && (
            <Group
              heading="Fields"
              count={fields.length}
              hint={fields.length >= FIELD_LIMIT ? `first ${FIELD_LIMIT}` : undefined}
            >
              {fields.map(({ entity, field }) => (
                <Item
                  key={field.id}
                  value={`field ${field.name} ${entity.name} ${field.field_type}`}
                  kind={FIELD_TYPE_ABBR[field.field_type]}
                  meta={entity.name}
                  icon={
                    <span
                      aria-hidden
                      className="size-2.5 shrink-0 rounded-[2px]"
                      style={{ background: fieldFill(field.field_type, field.preset) }}
                    />
                  }
                  onSelect={() =>
                    go(`/projects/${projectId}/entities/${entity.id}#field-${field.id}`)
                  }
                >
                  <span className="font-mono text-[0.8rem]">
                    <Highlight text={field.name} query={query} />
                  </span>
                </Item>
              ))}
            </Group>
          )}

          {visibleProjects.length > 0 && (
            <Group
              heading="Projects"
              count={projects.length}
              hint={!searching && projects.length > RESTING_LIMIT ? "type to see all" : undefined}
            >
              {visibleProjects.map((project) => (
                <Item
                  key={project.id}
                  value={`project ${project.name}`}
                  icon={<FolderOpen />}
                  kind="project"
                  meta={project.organization_id ? "shared" : "personal"}
                  onSelect={() => go(`/projects/${project.id}`)}
                >
                  <Highlight text={project.name} query={query} />
                </Item>
              ))}
            </Group>
          )}

          <Group heading="Workspace" count={4}>
            <Item
              value="all projects list"
              icon={<FolderOpen />}
              kind="page"
              onSelect={() => go("/projects")}
            >
              <Highlight text="All projects" query={query} />
            </Item>
            <Item
              value="api keys tokens ci machine access"
              icon={<KeyRound />}
              kind="page"
              onSelect={() => go("/settings/api-keys")}
            >
              <Highlight text="API keys" query={query} />
            </Item>
            <Item
              value="organizations teams members roles"
              icon={<Users />}
              kind="page"
              onSelect={() => go("/settings/organizations")}
            >
              <Highlight text="Organizations" query={query} />
            </Item>
            <Item
              value="activity audit log history"
              icon={<ScrollText />}
              kind="page"
              onSelect={() => go("/settings/activity")}
            >
              <Highlight text="Activity" query={query} />
            </Item>
          </Group>

          <Group heading="Actions" count={4}>
            <Item
              value="theme light appearance"
              icon={<Sun />}
              kind="action"
              onSelect={() => run(() => setTheme("light"))}
            >
              Switch to light theme
            </Item>
            <Item
              value="theme dark appearance"
              icon={<Moon />}
              kind="action"
              onSelect={() => run(() => setTheme("dark"))}
            >
              Switch to dark theme
            </Item>
            <Item
              value="theme system appearance"
              icon={<Monitor />}
              kind="action"
              onSelect={() => run(() => setTheme("system"))}
            >
              Follow system theme
            </Item>
            <Item
              value="sign out log out"
              icon={<LogOut />}
              kind="action"
              onSelect={() =>
                run(() => {
                  logout();
                  router.replace("/login");
                })
              }
            >
              Sign out
            </Item>
          </Group>
        </Command.List>

        <footer className="flex items-center gap-3 border-t border-line-soft bg-surface-2 px-4 py-2">
          <Hint keys={["↑", "↓"]}>navigate</Hint>
          <Hint keys={[<CornerDownLeft key="enter" className="size-2.5" />]}>open</Hint>
          <Hint keys={["esc"]}>close</Hint>
          {projectId && entities.length > 0 && (
            <span className="ml-auto hidden font-mono text-[10px] text-ink-faint sm:inline">
              searching {entities.length} entit{entities.length === 1 ? "y" : "ies"}
            </span>
          )}
        </footer>
      </Command.Dialog>
    </>
  );
}

function Group({
  heading,
  count,
  hint,
  children,
}: {
  heading: string;
  count?: number;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <Command.Group
      // The heading is rendered by cmdk, which hides the whole group when every
      // item in it filters out — so the count and hint ride along inside it
      // rather than being drawn separately above.
      heading={
        <span className="flex items-baseline gap-2">
          <span>{heading}</span>
          {count !== undefined && (
            <span className="font-mono text-[9px] tracking-normal normal-case text-ink-faint/70">
              {count}
            </span>
          )}
          {hint && (
            <span className="ml-auto font-mono text-[9px] tracking-normal normal-case text-ink-faint/70">
              {hint}
            </span>
          )}
        </span>
      }
      className="[&_[cmdk-group-heading]]:eyebrow mb-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:pb-1.5"
    >
      {children}
    </Command.Group>
  );
}

function Item({
  children,
  icon,
  meta,
  kind,
  value,
  onSelect,
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  /** Right-hand context — the entity a field belongs to, a project's sharing. */
  meta?: string;
  /** A short type tag, so results stay distinguishable when several groups
   * match the same word. */
  kind?: string;
  value?: string;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className={cn(
        "group/item relative flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-ink-dim",
        "data-[selected=true]:bg-surface-2 data-[selected=true]:text-ink",
        // A brand bar on the selected row: with several groups on screen the
        // background tint alone is easy to lose track of while arrowing.
        "before:absolute before:top-1.5 before:bottom-1.5 before:left-0 before:w-[2px] before:rounded-full before:bg-brand before:opacity-0 data-[selected=true]:before:opacity-100",
        "[&>svg]:size-3.5 [&>svg]:shrink-0 [&>svg]:text-ink-faint"
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {meta && (
        <span className="hidden shrink-0 truncate font-mono text-[10px] text-ink-faint sm:inline sm:max-w-32">
          {meta}
        </span>
      )}
      {kind && (
        <span className="shrink-0 rounded bg-surface-3 px-1.5 py-px font-mono text-[9px] text-ink-faint">
          {kind}
        </span>
      )}
    </Command.Item>
  );
}

/** Marks the matched run inside a result, so it is obvious *why* something
 * matched — particularly for fields, where the name may be the only difference
 * between two rows. */
function Highlight({ text, query }: { text: string; query: string }) {
  const needle = query.trim();
  if (!needle) return <>{text}</>;

  const at = text.toLowerCase().indexOf(needle.toLowerCase());
  if (at === -1) return <>{text}</>;

  return (
    <>
      {text.slice(0, at)}
      <mark className="bg-brand/25 text-ink">{text.slice(at, at + needle.length)}</mark>
      {text.slice(at + needle.length)}
    </>
  );
}

function Hint({ keys, children }: { keys: React.ReactNode[]; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1 font-mono text-[10px] text-ink-faint">
      {keys.map((key, index) => (
        <kbd
          key={index}
          className="flex h-4 min-w-4 items-center justify-center rounded border border-line bg-surface px-1"
        >
          {key}
        </kbd>
      ))}
      {children}
    </span>
  );
}
