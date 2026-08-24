"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DATABASE_DEFAULT_PORTS,
  DATABASE_DIALECTS,
  type DatabaseConnectionCreateInput,
  type DatabaseDialect,
} from "@/lib/types";

interface FormValues {
  name: string;
  dialect: DatabaseDialect;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
}

export function AddDatabaseConnectionDialog({
  onSubmit,
  isPending,
}: {
  onSubmit: (values: DatabaseConnectionCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      dialect: "postgresql",
      port: "5432",
    },
  });

  const dialect = watch("dialect");

  const submit = (values: FormValues) => {
    onSubmit({
      name: values.name,
      dialect: values.dialect,
      host: values.host,
      port: Number(values.port),
      database: values.database,
      username: values.username,
      password: values.password,
    });
    reset({ dialect: "postgresql", port: "5432" });
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset({ dialect: "postgresql", port: "5432" });
      }}
    >
      <DialogTrigger render={<Button size="sm">Add connection</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add database connection</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="e.g. Production Warehouse"
              {...register("name", { required: "Name is required" })}
            />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>

          <div className="flex flex-col gap-2">
            <Label>Dialect</Label>
            <Select
              value={dialect}
              onValueChange={(v) => {
                const next = (v ?? "postgresql") as DatabaseDialect;
                setValue("dialect", next);
                // Carry the port with the dialect. Leaving 5432 behind
                // after switching to MongoDB is a confusing failure that
                // looks like the server is down.
                setValue("port", DATABASE_DEFAULT_PORTS[next]);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DATABASE_DIALECTS.map((d) => (
                  <SelectItem key={d} value={d}>
                    {d}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {(dialect === "mysql" || dialect === "mongodb") && (
              <p className="text-xs text-muted-foreground">
                {dialect === "mysql"
                  ? "Needs the mysql extra installed on the backend (synthflow init)."
                  : "Needs the mongo extra installed on the backend (synthflow init). " +
                    "Documents are written to a collection named after the table; " +
                    "credentials are checked against the admin database."}
              </p>
            )}
          </div>

          <div className="flex gap-4">
            <div className="flex flex-1 flex-col gap-2">
              <Label htmlFor="host">Host</Label>
              <Input id="host" {...register("host", { required: true })} />
            </div>
            <div className="flex w-24 flex-col gap-2">
              <Label htmlFor="port">Port</Label>
              <Input id="port" type="number" {...register("port", { required: true })} />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="database">Database</Label>
            <Input id="database" {...register("database", { required: true })} />
          </div>

          <div className="flex gap-4">
            <div className="flex flex-1 flex-col gap-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" {...register("username", { required: true })} />
            </div>
            <div className="flex flex-1 flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" {...register("password", { required: true })} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Encrypted at rest and never returned by the API. Use a
            low-privilege database user, the same way you would for any
            external tool.
          </p>

          <DialogFooter>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Adding…" : "Add connection"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
