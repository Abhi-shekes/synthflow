"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { Mark } from "@/components/brand/mark";
import { SchemaImportDialog } from "@/components/schema-import-dialog";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/friendly-error";
import { useCompleteOnboarding, useRequireAuth } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";

/**
 * The first-run welcome flow — a brand-new
 * account's first stop instead of a cold, empty /projects page.
 *
 * One screen rather than a three-step wizard: every path here — a starter
 * template, a blank project, or an existing schema — leads to the same next
 * screen regardless of *why* someone's here, so asking "what are you here
 * for?" first would only add a click without changing what happens next.
 * Skippable at every point; skipping still marks onboarding complete so
 * this never re-appears uninvited.
 */
export default function WelcomePage() {
  const accessToken = useRequireAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const completeOnboarding = useCompleteOnboarding();

  // A returning user who navigates here directly (bookmark, back button)
  // has already been through this — send them on rather than re-running it.
  useEffect(() => {
    if (user?.has_onboarded) router.replace("/projects");
  }, [user, router]);

  const templatesQuery = useQuery({
    queryKey: ["starter-templates"],
    queryFn: () => api.listStarterTemplates(accessToken!),
    enabled: !!accessToken,
  });

  const finish = (projectId?: string) => {
    completeOnboarding.mutate(undefined, {
      onSuccess: () => router.push(projectId ? `/projects/${projectId}` : "/projects"),
    });
  };

  const useTemplate = useMutation({
    mutationFn: async (key: string) => {
      const template = await api.getStarterTemplate(accessToken!, key);
      return api.importProject(accessToken!, template);
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      finish(project.id);
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not use that template"),
  });

  const startBlank = useMutation({
    mutationFn: () => api.createProject(accessToken!, { name: "My first project" }),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      finish(project.id);
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create a project"),
  });

  if (!accessToken) return null;

  return (
    <div className="flex flex-1 justify-center px-4 py-12">
      <div className="flex w-full max-w-3xl flex-col gap-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <Mark className="size-8" />
            <div>
              <h1 className="font-display text-xl font-bold tracking-tight">
                Welcome to SynthFlow
              </h1>
              <p className="mt-0.5 text-sm text-ink-dim">
                How would you like to start? You can change any of this later.
              </p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => finish()}>
            Skip for now
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Panel tone="flat" className="flex h-full flex-col">
            <PanelBody className="flex h-full flex-col gap-2">
              <p className="font-display text-sm font-semibold tracking-tight">Start blank</p>
              <p className="text-xs leading-relaxed text-ink-dim">
                An empty project — build your own entities and fields from scratch.
              </p>
              <Button
                size="xs"
                variant="outline"
                className="mt-auto self-start"
                disabled={startBlank.isPending}
                onClick={() => startBlank.mutate()}
              >
                {startBlank.isPending ? "Creating…" : "Start blank"}
              </Button>
            </PanelBody>
          </Panel>

          <Panel tone="flat" className="flex h-full flex-col">
            <PanelBody className="flex h-full flex-col gap-2">
              <p className="font-display text-sm font-semibold tracking-tight">
                Import an existing schema
              </p>
              <p className="text-xs leading-relaxed text-ink-dim">
                From a SQL file, JSON Schema, a live database, or a sample data file you already
                have.
              </p>
              <div className="mt-auto self-start">
                <SchemaImportDialog
                  onImported={() => {
                    queryClient.invalidateQueries({ queryKey: ["projects"] });
                    // The dialog doesn't hand back the new project's id, so
                    // this lands on /projects rather than inside it — a
                    // small inconsistency against the template/blank paths
                    // below, which do route straight in.
                    finish();
                  }}
                />
              </div>
            </PanelBody>
          </Panel>
        </div>

        <div>
          <p className="eyebrow mb-2">Or start from a template</p>
          {templatesQuery.isLoading && <p className="text-sm text-ink-dim">Loading…</p>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {templatesQuery.data?.map((t) => (
              <Panel key={t.key} tone="flat" className="flex h-full flex-col">
                <PanelBody className="flex h-full flex-col gap-2">
                  <p className="font-display text-sm font-semibold tracking-tight">{t.name}</p>
                  <p className="text-xs leading-relaxed text-ink-dim">{t.description}</p>
                  <Button
                    size="xs"
                    variant="outline"
                    className="mt-auto self-start"
                    disabled={useTemplate.isPending}
                    onClick={() => useTemplate.mutate(t.key)}
                  >
                    {useTemplate.isPending && useTemplate.variables === t.key
                      ? "Creating…"
                      : "Use this"}
                  </Button>
                </PanelBody>
              </Panel>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
