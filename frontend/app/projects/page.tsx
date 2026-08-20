"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
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

interface FormValues {
  name: string;
  description?: string;
}

export default function ProjectsPage() {
  const accessToken = useRequireAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset } = useForm<FormValues>();

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(accessToken!),
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

  if (!accessToken) return null;

  return (
    <AppShell>
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
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
      </div>
    </AppShell>
  );
}
