"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

const PERSONAL = "personal";

/**
 * Which organisation, if any, this project is shared with.
 *
 * Only the project's owner sees a usable control here — an org admin who
 * could move projects in and out of their organisation could quietly take
 * one over, so the server refuses it and this does not pretend otherwise.
 */
export function ShareProjectCard({
  projectId,
  organizationId,
  isOwner,
}: {
  projectId: string;
  organizationId: string | null;
  isOwner: boolean;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.listOrganizations(accessToken!),
    enabled: !!accessToken,
  });

  const share = useMutation({
    mutationFn: (next: string) =>
      api.setProjectOrganization(accessToken!, projectId, next === PERSONAL ? null : next),
    onSuccess: (project) => {
      toast.success(
        project.organization_id
          ? "Shared — everyone in that organization can see it now"
          : "Personal again — only you can see it"
      );
      return queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not change sharing"),
  });

  const available = orgs.data ?? [];
  const current = organizationId ?? PERSONAL;
  const currentName = available.find((o) => o.id === organizationId)?.name;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Sharing</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!isOwner ? (
          <p className="text-sm text-muted-foreground">
            Shared with you through{" "}
            <span className="font-medium">{currentName ?? "an organization"}</span>. Only
            the project&apos;s owner can change who it is shared with.
          </p>
        ) : available.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            This project is personal. To share it, first{" "}
            <Link href="/settings/organizations" className="underline">
              create an organization
            </Link>
            .
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              A personal project is visible only to you. Sharing it with an
              organization gives every member access at whatever role they
              hold there.
            </p>
            <Select
              value={current}
              onValueChange={(v) => share.mutate(v ?? PERSONAL)}
            >
              <SelectTrigger className="w-64">
                <SelectValue>
                  {(v: string) =>
                    v === PERSONAL || !v
                      ? "Personal — only you"
                      : (available.find((o) => o.id === v)?.name ?? "an organization")
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={PERSONAL}>Personal — only you</SelectItem>
                {available.map((org) => (
                  <SelectItem key={org.id} value={org.id}>
                    {org.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}
      </CardContent>
    </Card>
  );
}
