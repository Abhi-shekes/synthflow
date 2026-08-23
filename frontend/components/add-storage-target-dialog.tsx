"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { ObjectStorageTargetCreateInput } from "@/lib/types";

/**
 * One form for every S3-compatible service. `endpoint_url` is what selects
 * between them — blank for real AWS, a URL for MinIO, R2, Spaces or B2 —
 * which is why there is no provider dropdown to get wrong.
 */
export function AddStorageTargetDialog({
  projectId,
  onCreated,
}: {
  projectId: string;
  onCreated: () => void;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset } = useForm<ObjectStorageTargetCreateInput>({
    defaultValues: { region: "us-east-1", prefix: "", endpoint_url: "" },
  });

  const create = useMutation({
    mutationFn: (input: ObjectStorageTargetCreateInput) =>
      api.createStorageTarget(accessToken!, projectId, input),
    onSuccess: () => {
      toast.success("Storage target added");
      setOpen(false);
      reset({ region: "us-east-1", prefix: "", endpoint_url: "" });
      onCreated();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add the target"),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset({ region: "us-east-1", prefix: "", endpoint_url: "" });
      }}
    >
      <DialogTrigger render={<Button variant="outline">Add storage target</Button>} />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a storage target</DialogTitle>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={handleSubmit((values) => create.mutate(values))}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="storage-name">Name</Label>
            <Input id="storage-name" {...register("name", { required: true })} />
          </div>

          <div className="flex gap-4">
            <div className="flex flex-1 flex-col gap-2">
              <Label htmlFor="storage-bucket">Bucket</Label>
              <Input id="storage-bucket" {...register("bucket", { required: true })} />
            </div>
            <div className="flex w-40 flex-col gap-2">
              <Label htmlFor="storage-region">Region</Label>
              <Input id="storage-region" {...register("region")} />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="storage-prefix">Key prefix (optional)</Label>
            <Input id="storage-prefix" placeholder="runs" {...register("prefix")} />
            <p className="text-xs text-muted-foreground">
              Lets one bucket hold several projects without them colliding.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="storage-endpoint">Endpoint URL (optional)</Label>
            <Input
              id="storage-endpoint"
              placeholder="https://… — leave blank for AWS S3"
              {...register("endpoint_url")}
            />
            <p className="text-xs text-muted-foreground">
              Set this for MinIO, Cloudflare R2, DigitalOcean Spaces or Backblaze
              B2 — they all speak the S3 API.
            </p>
          </div>

          <div className="flex gap-4">
            <div className="flex flex-1 flex-col gap-2">
              <Label htmlFor="storage-key">Access key ID</Label>
              <Input id="storage-key" {...register("access_key_id", { required: true })} />
            </div>
            <div className="flex flex-1 flex-col gap-2">
              <Label htmlFor="storage-secret">Secret access key</Label>
              <Input
                id="storage-secret"
                type="password"
                {...register("secret_access_key", { required: true })}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            The secret is encrypted at rest and is never returned by the API.
          </p>

          <DialogFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Adding…" : "Add target"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
