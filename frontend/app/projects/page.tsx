"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { SchemaImportDialog } from "@/components/schema-import-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/hooks";
import type { ProjectTemplate } from "@/lib/types";

interface FormValues {
  name: string;
  description?: string;
}

export default function ProjectsPage() {
  const accessToken = useRequireAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset } = useForm<FormValues>();
  const importInputRef = useRef<HTMLInputElement>(null);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(accessToken!),
    enabled: !!accessToken,
  });

  const starterTemplatesQuery = useQuery({
    queryKey: ["starter-templates"],
    queryFn: () => api.listStarterTemplates(accessToken!),
    enabled: !!accessToken,
  });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => api.createProject(accessToken!, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
      reset();
    },
    onError: (error: Error) => toast.error(error.message || "Could not create project"),
  });

  const importMutation = useMutation({
    mutationFn: (template: ProjectTemplate) => api.importProject(accessToken!, template),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project imported");
    },
    onError: (error: Error) => toast.error(error.message || "Could not import project"),
  });

  const useStarterTemplate = useMutation({
    mutationFn: async (key: string) => {
      const template = await api.getStarterTemplate(accessToken!, key);
      return api.importProject(accessToken!, template);
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(`"${project.name}" created from starter template`);
    },
    onError: (error: Error) => toast.error(error.message || "Could not use starter template"),
  });

  const handleImportFile = async (file: File) => {
    let template: ProjectTemplate;
    try {
      template = JSON.parse(await file.text());
    } catch {
      toast.error("That file isn't valid JSON");
      return;
    }
    importMutation.mutate(template);
  };

  if (!accessToken) return null;

  return (
    <AppShell>
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <div className="flex gap-2">
            <input
              ref={importInputRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleImportFile(file);
                e.target.value = "";
              }}
            />
            <Button
              variant="outline"
              disabled={importMutation.isPending}
              onClick={() => importInputRef.current?.click()}
            >
              {importMutation.isPending ? "Importing…" : "Import project"}
            </Button>
            <SchemaImportDialog
              onImported={() => queryClient.invalidateQueries({ queryKey: ["projects"] })}
            />
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger render={<Button>New project</Button>} />
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>New project</DialogTitle>
                </DialogHeader>
                <form
                  className="flex flex-col gap-4"
                  onSubmit={handleSubmit((values) => createMutation.mutate(values))}
                >
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="name">Name</Label>
                    <Input id="name" {...register("name", { required: true })} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="description">Description (optional)</Label>
                    <Input id="description" {...register("description")} />
                  </div>
                  <DialogFooter>
                    <Button type="submit" disabled={createMutation.isPending}>
                      {createMutation.isPending ? "Creating…" : "Create"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {projectsQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Loading projects…</p>
        )}

        {projectsQuery.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No projects yet. Create one to start modeling entities.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {projectsQuery.data?.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}`}>
              <Card className="h-full transition-colors hover:border-foreground/30">
                <CardHeader>
                  <CardTitle className="text-base">{project.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {project.description || "No description"}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold tracking-tight">Starter templates</h2>
          <p className="text-sm text-muted-foreground">
            Pre-built entities, relationships, and simulation config for common domains —
            creates a new project you can freely edit afterward.
          </p>
        </div>

        {starterTemplatesQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Loading starter templates…</p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {starterTemplatesQuery.data?.map((t) => {
            const isThisPending = useStarterTemplate.isPending && useStarterTemplate.variables === t.key;
            return (
              <Card key={t.key} className="flex h-full flex-col justify-between">
                <CardHeader>
                  <CardTitle className="text-base">{t.name}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <p className="text-sm text-muted-foreground">{t.description}</p>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={useStarterTemplate.isPending}
                    onClick={() => useStarterTemplate.mutate(t.key)}
                  >
                    {isThisPending ? "Creating…" : "Use template"}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
