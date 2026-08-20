"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/hooks";

interface FormValues {
  name: string;
}

export default function ProjectDetailPage() {
  const accessToken = useRequireAuth();
  const router = useRouter();
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset } = useForm<FormValues>();

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const entitiesQuery = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => api.listEntities(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const createEntity = useMutation({
    mutationFn: (values: FormValues) => api.createEntity(accessToken!, projectId, values.name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
      reset();
    },
    onError: (error: Error) => toast.error(error.message || "Could not create entity"),
  });

  const deleteProject = useMutation({
    mutationFn: () => api.deleteProject(accessToken!, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push("/projects");
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete project"),
  });

  if (!accessToken) return null;

  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <Link href="/projects" className="text-sm text-muted-foreground hover:underline">
            ← Projects
          </Link>
        </div>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {projectQuery.data?.name ?? "…"}
            </h1>
            {projectQuery.data?.description && (
              <p className="mt-1 text-sm text-muted-foreground">
                {projectQuery.data.description}
              </p>
            )}
          </div>
          <Button
            variant="destructive"
            size="sm"
            disabled={deleteProject.isPending}
            onClick={() => {
              if (confirm("Delete this project and all its entities?")) {
                deleteProject.mutate();
              }
            }}
          >
            Delete project
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add an entity</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="flex gap-2"
              onSubmit={handleSubmit((values) => createEntity.mutate(values))}
            >
              <Input placeholder="e.g. Customer" {...register("name", { required: true })} />
              <Button type="submit" disabled={createEntity.isPending}>
                Add
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">Entities</h2>
          {entitiesQuery.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No entities yet. Add one above to start defining fields.
            </p>
          )}
          {entitiesQuery.data?.map((entity) => (
            <Link key={entity.id} href={`/projects/${projectId}/entities/${entity.id}`}>
              <Card className="transition-colors hover:border-foreground/30">
                <CardContent className="flex items-center justify-between py-4">
                  <span className="font-medium">{entity.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {entity.fields.length} field{entity.fields.length === 1 ? "" : "s"}
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
