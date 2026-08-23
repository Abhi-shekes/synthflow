"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/section-header";
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
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";
import type { ApiKey, ApiKeyScope } from "@/lib/types";

/**
 * API keys.
 *
 * The one page whose main job is to show a secret exactly once and then
 * never again. Everything about the layout follows from that: the new key
 * gets the largest, loudest panel on the page, it does not disappear on a
 * refetch, and the list below it can only ever show a prefix.
 */
export default function ApiKeysPage() {
  useRequireAuth();
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [scope, setScope] = useState<ApiKeyScope>("full");
  const [expiresAt, setExpiresAt] = useState("");
  const [freshKey, setFreshKey] = useState<string | null>(null);

  const keysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.listApiKeys(accessToken!),
    enabled: !!accessToken,
  });

  const create = useMutation({
    mutationFn: () => {
      if (!name.trim()) throw new Error("Give the key a name you will recognise later");
      return api.createApiKey(accessToken!, {
        name: name.trim(),
        scope,
        // A date input gives a day, not an instant. Midnight UTC at the end
        // of that day is the reading that matches what someone typing a
        // date means by it.
        expires_at: expiresAt ? new Date(`${expiresAt}T23:59:59Z`).toISOString() : null,
      });
    },
    onSuccess: (created) => {
      setFreshKey(created.key);
      setName("");
      setExpiresAt("");
      return queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create that key"),
  });

  const revoke = useMutation({
    mutationFn: (keyId: string) => api.revokeApiKey(accessToken!, keyId),
    onSuccess: () => {
      toast.success("Key revoked");
      return queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not revoke that key"),
  });

  const keys = keysQuery.data ?? [];

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <div>
          <Link href="/projects" className="text-sm text-muted-foreground">
            ← Projects
          </Link>
          <div className="mt-2">
            <SectionHeader
              icon={KeyRound}
              color={SECTION_COLOR.governance}
              eyebrow="Workspace"
              title="API keys"
              description={
                <>
                  A session token lasts minutes and needs a password to get. A key lasts until you
                  revoke it, which is what makes it usable from CI. Send it the same way as any
                  other token:{" "}
                  <code className="rounded bg-muted px-1 py-0.5 text-xs">
                    Authorization: Bearer sfk_…
                  </code>
                </>
              }
            />
          </div>
        </div>

        {freshKey && (
          <Card className="border-2">
            <CardHeader>
              <CardTitle className="text-base">
                Copy this now — it is not shown again
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <code className="break-all rounded bg-muted p-3 font-mono text-sm">
                {freshKey}
              </code>
              <p className="text-sm text-muted-foreground">
                Only a hash is stored, so this cannot be recovered — if you
                lose it, revoke this key and make another. The list below
                keeps the short prefix so you can tell your keys apart.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard
                      .writeText(freshKey)
                      .then(() => toast.success("Copied"))
                      // Clipboard access can be refused outright, and a
                      // silent no-op would look like the button is broken.
                      .catch(() => toast.error("Copy it manually — the browser blocked access"));
                  }}
                >
                  Copy
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setFreshKey(null)}>
                  Done
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">New key</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="key-name">Name</Label>
              <Input
                id="key-name"
                className="w-56"
                placeholder="nightly seed job"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Scope</Label>
              <Select value={scope} onValueChange={(v) => setScope((v ?? "full") as ApiKeyScope)}>
                <SelectTrigger className="w-52">
                  <SelectValue>
                    {(v: string) =>
                      v === "read_only" ? "Read-only" : "Full access"
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full">Full access</SelectItem>
                  <SelectItem value="read_only">Read-only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="key-expiry">Expires (optional)</Label>
              <Input
                id="key-expiry"
                type="date"
                className="w-44"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
              />
            </div>
            <Button onClick={() => create.mutate()} disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create key"}
            </Button>
            <p className="w-full text-xs text-muted-foreground">
              A read-only key may only GET. It is enforced by request method,
              not a list of endpoints, so an endpoint added tomorrow is
              covered too. Leaving the expiry blank means the key lives until
              revoked.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Your keys</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {keys.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No keys yet.
              </p>
            ) : (
              keys.map((key) => (
                <KeyRow
                  key={key.id}
                  apiKey={key}
                  pending={revoke.isPending}
                  onRevoke={() => revoke.mutate(key.id)}
                />
              ))
            )}
            <p className="text-xs text-muted-foreground">
              Revoked keys stay listed on purpose — &ldquo;this key was
              revoked last Tuesday&rdquo; is the answer you want when
              something stops working, and a list that quietly drops them
              cannot give it.
            </p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function KeyRow({
  apiKey,
  pending,
  onRevoke,
}: {
  apiKey: ApiKey;
  pending: boolean;
  onRevoke: () => void;
}) {
  // Captured at mount rather than read during render: `Date.now()` is
  // impure, and expiry here is day-granular, so the page's own load time is
  // as precise as this needs to be.
  const [now] = useState(() => Date.now());
  const expired = apiKey.expires_at !== null && new Date(apiKey.expires_at).getTime() < now;
  const dead = apiKey.revoked_at !== null || expired;

  return (
    <div
      className={`flex flex-wrap items-center gap-2 rounded-md border p-3 text-sm ${
        dead ? "opacity-60" : ""
      }`}
    >
      <span className="font-medium">{apiKey.name}</span>
      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
        sfk_{apiKey.prefix}…
      </code>
      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
        {apiKey.scope === "read_only" ? "read-only" : "full"}
      </span>
      <span className="text-xs text-muted-foreground">
        {apiKey.revoked_at
          ? `revoked ${apiKey.revoked_at.slice(0, 10)}`
          : expired
            ? `expired ${apiKey.expires_at!.slice(0, 10)}`
            : apiKey.last_used_at
              ? `last used ${apiKey.last_used_at.slice(0, 10)}`
              : "never used"}
      </span>
      {!dead && (
        <Button
          className="ml-auto"
          size="sm"
          variant="ghost"
          onClick={onRevoke}
          disabled={pending}
        >
          Revoke
        </Button>
      )}
    </div>
  );
}
