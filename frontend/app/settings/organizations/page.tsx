"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";
import { ROLES, type Organization, type Role } from "@/lib/types";

const ROLE_HELP: Record<Role, string> = {
  viewer: "reads everything, changes nothing",
  member: "reads and writes — entities, fields, generation, jobs",
  admin: "and manages membership",
  owner: "and manages the organization itself",
};

/**
 * Organisations.
 *
 * Roles are a ladder, not a matrix, and the page says so: each level is
 * listed with what it adds to the one below. A permission matrix is more
 * expressive and, in practice, is the thing nobody can reason about.
 */
export default function OrganizationsPage() {
  useRequireAuth();
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.listOrganizations(accessToken!),
    enabled: !!accessToken,
  });

  const create = useMutation({
    mutationFn: () => {
      if (!name.trim()) throw new Error("Give the organization a name");
      return api.createOrganization(accessToken!, name.trim());
    },
    onSuccess: () => {
      setName("");
      return queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not create it"),
  });

  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <Link href="/projects" className="text-sm text-muted-foreground">
            ← Projects
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Organizations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            A group of people who share projects. Projects stay personal
            until you share one — a project without an organization behaves
            exactly as it always did.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">New organization</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="org-name">Name</Label>
              <Input
                id="org-name"
                className="w-64"
                placeholder="Acme Data Team"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <Button onClick={() => create.mutate()} disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
            <p className="w-full text-xs text-muted-foreground">
              You become its owner. An organization always keeps at least one
              — otherwise it is a group nobody can administer or delete.
            </p>
          </CardContent>
        </Card>

        {(orgs.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">
            You are not in any organizations yet.
          </p>
        ) : (
          (orgs.data ?? []).map((org) => <OrgCard key={org.id} org={org} />)
        )}
      </div>
    </AppShell>
  );
}

function OrgCard({ org }: { org: Organization }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");

  const members = useQuery({
    queryKey: ["organization-members", org.id],
    queryFn: () => api.listMembers(accessToken!, org.id),
    enabled: !!accessToken,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["organization-members", org.id] });

  const add = useMutation({
    mutationFn: () => {
      if (!email.trim()) throw new Error("Enter an email address");
      return api.addMember(accessToken!, org.id, email.trim(), role);
    },
    onSuccess: () => {
      setEmail("");
      return invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Could not add them"),
  });

  const changeRole = useMutation({
    mutationFn: ({ memberId, next }: { memberId: string; next: Role }) =>
      api.updateMemberRole(accessToken!, org.id, memberId, next),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast.error(error.message || "Could not change that role"),
  });

  const remove = useMutation({
    mutationFn: (memberId: string) => api.removeMember(accessToken!, org.id, memberId),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast.error(error.message || "Could not remove them"),
  });

  const dissolve = useMutation({
    mutationFn: () => api.deleteOrganization(accessToken!, org.id),
    onSuccess: () => {
      toast.success(`"${org.name}" dissolved — its projects went back to their owners`);
      return queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not dissolve it"),
  });

  // An admin cannot grant a role above their own, and the server refuses it.
  // Offering the option anyway would be teaching the rule by rejection.
  const grantable = ROLES.filter((r) => ROLES.indexOf(r) <= ROLES.indexOf(org.my_role));
  const canManage = org.my_role === "admin" || org.my_role === "owner";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">
          {org.name}{" "}
          <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground">
            you are {org.my_role}
          </span>
        </CardTitle>
        {org.my_role === "owner" && (
          <Button variant="ghost" size="sm" onClick={() => dissolve.mutate()}>
            Dissolve
          </Button>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {canManage && (
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor={`invite-${org.id}`}>Add by email</Label>
              <Input
                id={`invite-${org.id}`}
                className="w-64"
                placeholder="colleague@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Role</Label>
              <Select value={role} onValueChange={(v) => setRole((v ?? "member") as Role)}>
                <SelectTrigger className="w-36">
                  <SelectValue>{(v: string) => v || "member"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {grantable.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={() => add.mutate()} disabled={add.isPending}>
              {add.isPending ? "Adding…" : "Add"}
            </Button>
          </div>
        )}

        <ul className="flex flex-col gap-1 text-sm">
          {(members.data ?? []).map((member) => (
            <li
              key={member.id}
              className="flex flex-wrap items-center gap-2 rounded border px-2 py-1"
            >
              <span>{member.email}</span>
              {canManage ? (
                <Select
                  value={member.role}
                  onValueChange={(v) =>
                    changeRole.mutate({ memberId: member.id, next: (v ?? member.role) as Role })
                  }
                >
                  <SelectTrigger className="h-7 w-28">
                    <SelectValue>{(v: string) => v || member.role}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {grantable.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                  {member.role}
                </span>
              )}
              {canManage && (
                <Button
                  className="ml-auto"
                  size="sm"
                  variant="ghost"
                  onClick={() => remove.mutate(member.id)}
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>

        <dl className="text-xs text-muted-foreground">
          {ROLES.map((r) => (
            <div key={r} className="flex gap-2">
              <dt className="w-16 font-medium">{r}</dt>
              <dd>{ROLE_HELP[r]}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
