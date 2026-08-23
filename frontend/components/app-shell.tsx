"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Boxes,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  Database,
  FolderOpen,
  Gauge,
  HelpCircle,
  KeyRound,
  LogOut,
  Radio,
  ScrollText,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Mark } from "@/components/brand/mark";
import { HelpPanel } from "@/components/help/help-panel";
import { CommandPalette } from "@/components/shell/command-palette";
import { ModeToggle } from "@/components/shell/mode-toggle";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import type { SectionKey } from "@/lib/field-visual";
import { useViewMode } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

/** Tailwind class per `SectionKey` — a static map rather than an inline
 * style, since every one of these already exists as a generated utility
 * (`lib/field-visual.ts`'s `SECTION_COLOR` values are all `--color-*`
 * tokens declared in `app/globals.css`'s `@theme inline` block). */
const SECTION_TEXT_CLASS: Record<SectionKey, string> = {
  map: "text-brand",
  data: "text-sec-data",
  delivery: "text-t-string",
  monitor: "text-sev-ok",
  governance: "text-sec-governance",
};

interface NavItem {
  href: string;
  label: string;
  Icon: typeof Boxes;
  /** Match the pathname exactly rather than by prefix. Needed for the project
   * root, which is a prefix of every other project route. */
  exact?: boolean;
  /** Deferred behind the rail's "More" disclosure in Guided mode. Full
   * capability either way — this only changes what's on screen by default. */
  advanced?: boolean;
  /** Which page section this links to, for the active-state colour
   * (VISUAL_POLISH_PLAN.md V2). Settings/workspace links have none and fall
   * back to the brand colour, same as before this existed. */
  section?: SectionKey;
}

/**
 * The application frame.
 *
 * The rail keeps the same shape everywhere. An earlier version only rendered
 * the project section when the URL happened to carry a `projectId`, so the menu
 * was nine entries inside a project and four on Projects or Settings — the same
 * navigation appearing to gain and lose options as you moved around. The
 * project section is now always present, pointed at the project you are in or,
 * failing that, the last one you opened, with a switcher to change it.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ projectId?: string; entityId?: string }>();
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const lastProjectId = useAuthStore((s) => s.lastProjectId);
  const setLastProject = useAuthStore((s) => s.setLastProject);
  const logout = useAuthStore((s) => s.logout);

  const routeProjectId = params?.projectId;
  const entityId = params?.entityId;

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(accessToken!),
    enabled: !!accessToken,
  });
  const projects = projectsQuery.data ?? [];

  // Prefer the URL, fall back to what was open last, and finally to the first
  // project that exists — so a fresh sign-in still gets a usable rail instead
  // of a section pointing nowhere.
  const activeProjectId = routeProjectId ?? lastProjectId ?? projects[0]?.id;
  const activeProject = projects.find((project) => project.id === activeProjectId);

  useEffect(() => {
    if (routeProjectId && routeProjectId !== lastProjectId) setLastProject(routeProjectId);
  }, [routeProjectId, lastProjectId, setLastProject]);

  // A remembered project that has since been deleted would leave every link in
  // the section pointing at a 404.
  useEffect(() => {
    if (!projectsQuery.isSuccess || !lastProjectId) return;
    if (!projects.some((project) => project.id === lastProjectId)) setLastProject(null);
  }, [projectsQuery.isSuccess, projects, lastProjectId, setLastProject]);

  const mode = useViewMode();
  const [projectAdvancedOpen, setProjectAdvancedOpen] = useState(false);
  const [globalAdvancedOpen, setGlobalAdvancedOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const projectNav: NavItem[] = activeProjectId
    ? [
        {
          href: `/projects/${activeProjectId}`,
          label: "System map",
          Icon: Boxes,
          exact: true,
          section: "map",
        },
        {
          href: `/projects/${activeProjectId}/delivery`,
          label: "Delivery",
          Icon: Radio,
          section: "delivery",
        },
        {
          href: `/projects/${activeProjectId}/data`,
          label: "Data & jobs",
          Icon: Database,
          advanced: true,
          section: "data",
        },
        {
          href: `/projects/${activeProjectId}/monitor`,
          label: "Live monitor",
          Icon: Gauge,
          advanced: true,
          section: "monitor",
        },
        {
          href: `/projects/${activeProjectId}/governance`,
          label: "Governance",
          Icon: ScrollText,
          advanced: true,
          section: "governance",
        },
      ]
    : [];

  const globalNav: NavItem[] = [
    { href: "/projects", label: "All projects", Icon: FolderOpen, exact: true },
    { href: "/settings/api-keys", label: "API keys", Icon: KeyRound, advanced: true },
    { href: "/settings/organizations", label: "Organizations", Icon: Users, advanced: true },
    { href: "/settings/activity", label: "Activity", Icon: ScrollText, advanced: true },
  ];

  const isActive = (item: NavItem) =>
    item.exact ? pathname === item.href : pathname.startsWith(item.href);

  // In Advanced mode every item is always visible — no forked layout, just a
  // filter that happens to keep everything. In Guided mode an item marked
  // `advanced` only shows once its section's disclosure is opened, or if the
  // current page is already inside it (so navigating there doesn't hide the
  // very link you're standing on).
  const visible = (items: NavItem[], open: boolean) =>
    mode === "advanced" ? items : items.filter((item) => !item.advanced || open || isActive(item));

  const crumbs: { href: string; label: string }[] = [{ href: "/projects", label: "Projects" }];
  if (routeProjectId) {
    crumbs.push({
      href: `/projects/${routeProjectId}`,
      label: activeProject?.name ?? "…",
    });
  }
  const entityQuery = useQuery({
    queryKey: ["entity", routeProjectId, entityId],
    queryFn: () => api.getEntity(accessToken!, routeProjectId!, entityId!),
    enabled: !!accessToken && !!routeProjectId && !!entityId,
  });
  if (routeProjectId && entityId) {
    crumbs.push({
      href: `/projects/${routeProjectId}/entities/${entityId}`,
      label: entityQuery.data?.name ?? "…",
    });
  }

  return (
    <div className="flex min-h-screen flex-col bg-ground md:flex-row">
      {/* Full labels from lg, icons only at md, and on phones it drops out
          entirely — the sections reappear as a scrollable strip below the top
          bar, because a drawer costs a tap to answer "where am I?", which is
          the question the rail exists for. */}
      <aside className="sticky top-0 z-30 hidden h-screen shrink-0 flex-col gap-1 border-r border-line bg-surface px-2.5 py-4 md:flex md:w-14 lg:w-56 lg:px-3">
        <Link
          href="/projects"
          className="mb-3 flex items-center gap-2 rounded-lg px-1.5 py-1 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <Mark />
          <span className="hidden font-display text-sm font-bold tracking-tight lg:inline">
            SynthFlow
          </span>
        </Link>

        <ProjectSwitcher
          projects={projects}
          activeProjectId={activeProjectId}
          activeName={activeProject?.name}
          onPick={(id) => {
            setLastProject(id);
            router.push(`/projects/${id}`);
          }}
        />

        <p className="eyebrow mt-3 hidden px-1.5 pb-1.5 lg:block">Project</p>
        <nav className="flex flex-col gap-0.5">
          {projectNav.length > 0 ? (
            <>
              {visible(projectNav, projectAdvancedOpen).map((item) => (
                <RailLink key={item.href} item={item} active={isActive(item)} />
              ))}
              {mode === "guided" && !projectAdvancedOpen && projectNav.some((i) => i.advanced) && (
                <MoreDisclosure onClick={() => setProjectAdvancedOpen(true)} />
              )}
            </>
          ) : (
            // No project exists yet. The section still occupies its place so
            // the rail does not change height the moment one is created.
            <p className="hidden px-1.5 py-1 text-[13px] leading-relaxed text-ink-faint lg:block">
              Create a project and its sections appear here.
            </p>
          )}
        </nav>

        <div className="my-3 h-px bg-line-soft" />

        <p className="eyebrow hidden px-1.5 pb-1.5 lg:block">Workspace</p>
        <nav className="flex flex-col gap-0.5">
          {visible(globalNav, globalAdvancedOpen).map((item) => (
            <RailLink key={item.href} item={item} active={isActive(item)} />
          ))}
          {mode === "guided" && !globalAdvancedOpen && globalNav.some((i) => i.advanced) && (
            <MoreDisclosure onClick={() => setGlobalAdvancedOpen(true)} />
          )}
        </nav>

        {/* Stacked, not side by side: the two segmented controls together
            are wider than the rail's content column, and a squeezed row
            wraps its labels mid-word. Each gets its own row instead. */}
        <div className="mt-auto hidden flex-col gap-1.5 lg:flex">
          <ModeToggle />
          <ThemeToggle />
          {user && (
            <p className="truncate px-1.5 pt-0.5 font-mono text-xs text-ink-faint">
              {user.email}
            </p>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-ground px-4 py-2.5 lg:px-6">
          <Link href="/projects" className="md:hidden">
            <Mark />
          </Link>

          <nav aria-label="Breadcrumb" className="flex min-w-0 flex-1 items-center gap-1 text-xs">
            {crumbs.map((crumb, index) => {
              const last = index === crumbs.length - 1;
              return (
                <span key={crumb.href} className="flex min-w-0 items-center gap-1">
                  {index > 0 && <ChevronRight className="size-3 shrink-0 text-ink-faint" />}
                  {last ? (
                    <span className="truncate font-medium text-ink">{crumb.label}</span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className="truncate text-ink-dim transition-colors hover:text-ink"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </span>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center gap-2">
            <CommandPalette />
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Help"
              aria-pressed={helpOpen}
              onClick={() => setHelpOpen((v) => !v)}
            >
              <HelpCircle />
            </Button>
            <span className="lg:hidden">
              <ModeToggle />
            </span>
            <span className="lg:hidden">
              <ThemeToggle />
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Log out"
              onClick={() => {
                logout();
                router.replace("/login");
              }}
            >
              <LogOut />
            </Button>
          </div>
        </header>

        <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />

        {/* Phone strip. Both groups, always, in the same order as the rail —
            the whole point is that the menu does not change shape by route. */}
        <div className="flex gap-1 overflow-x-auto border-b border-line px-4 py-2 md:hidden">
          {[...visible(projectNav, projectAdvancedOpen), ...visible(globalNav, globalAdvancedOpen)].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "shrink-0 rounded-lg px-2.5 py-1 text-xs whitespace-nowrap transition-colors",
                isActive(item) ? "bg-surface-2 text-ink" : "text-ink-dim"
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>

        <main className="min-w-0 flex-1 px-4 py-6 lg:px-6 lg:py-8">{children}</main>
      </div>
    </div>
  );
}

/**
 * Which project the section below refers to, and how to change it.
 *
 * Without this the project links were implicit — they pointed at whatever was
 * in the URL, and you could not tell from the rail which project you were
 * about to navigate within.
 */
function ProjectSwitcher({
  projects,
  activeProjectId,
  activeName,
  onPick,
}: {
  projects: { id: string; name: string }[];
  activeProjectId: string | undefined;
  activeName: string | undefined;
  onPick: (id: string) => void;
}) {
  if (projects.length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            title={activeName ?? "Choose a project"}
            className="flex w-full items-center gap-2 rounded-lg border border-line bg-surface-2 px-1.5 py-1.5 text-left transition-colors hover:border-ink-faint focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none max-md:justify-center md:justify-center lg:justify-start"
          >
            <Boxes className="size-4 shrink-0 text-ink-faint" />
            <span className="hidden min-w-0 flex-1 truncate text-[0.8rem] font-medium lg:inline">
              {activeName ?? "Choose a project"}
            </span>
            <ChevronsUpDown className="hidden size-3 shrink-0 text-ink-faint lg:inline" />
          </button>
        }
      />
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Switch project</DropdownMenuLabel>
          {projects.map((project) => (
            <DropdownMenuItem key={project.id} onClick={() => onPick(project.id)}>
              <Check
                className={cn(
                  "size-3.5",
                  project.id === activeProjectId ? "opacity-100" : "opacity-0"
                )}
              />
              <span className="truncate">{project.name}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          render={
            <Link href="/projects">
              <FolderOpen className="size-3.5" />
              All projects
            </Link>
          }
        />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function RailLink({ item, active }: { item: NavItem; active: boolean }) {
  const { Icon, href, label, section } = item;
  const activeColor = section ? SECTION_TEXT_CLASS[section] : "text-brand";
  return (
    <Link
      href={href}
      title={label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-[0.8rem] transition-colors",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        "max-md:justify-center md:justify-center lg:justify-start",
        active
          ? "bg-surface-2 font-medium text-ink"
          : "text-ink-dim hover:bg-surface-2 hover:text-ink"
      )}
    >
      <Icon className={cn("size-4 shrink-0", active ? activeColor : "text-ink-faint")} />
      <span className="hidden truncate lg:inline">{label}</span>
    </Link>
  );
}

/** Opens a section's deferred links in place, rather than navigating —
 * Guided mode hides depth, it never makes it a second page to find.
 *
 * Labelled "More", never "Advanced" — that word is reserved for the actual
 * Guided/Advanced mode switch (`ModeToggle`, below in this same rail).
 * Two controls both called "Advanced" would be genuinely ambiguous: this one
 * only reveals more nav links for this visit, it doesn't change the mode. */
function MoreDisclosure({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title="More"
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-[0.8rem] text-ink-faint transition-colors",
        "hover:bg-surface-2 hover:text-ink-dim",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        "max-md:justify-center md:justify-center lg:justify-start"
      )}
    >
      <ChevronDown className="size-4 shrink-0" />
      <span className="hidden truncate lg:inline">More</span>
    </button>
  );
}

