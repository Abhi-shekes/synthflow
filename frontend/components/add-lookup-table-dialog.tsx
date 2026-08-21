"use client";

import { type FormEvent, useState } from "react";

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

export function AddLookupTableDialog({
  onSubmit,
  isPending,
}: {
  onSubmit: (values: { name: string; file: File }) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const reset = () => {
    setName("");
    setFile(null);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    onSubmit({ name, file });
    reset();
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger render={<Button size="sm" />}>Upload lookup table</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload lookup table</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="lookup-name">Name</Label>
            <Input
              id="lookup-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="lookup-file">File</Label>
            <Input
              id="lookup-file"
              type="file"
              accept=".csv,.xlsx,.xls,.json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
            <p className="text-xs text-muted-foreground">
              CSV, Excel, or JSON (a list of flat objects). The first row/keys
              become columns any field can draw values from.
            </p>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !name || !file}>
              {isPending ? "Uploading…" : "Upload"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
