"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AddFieldDialog } from "@/components/add-field-dialog";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/hooks";
import type { FieldCreateInput } from "@/lib/types";

export default function EntityDetailPage() {
  const accessToken = useRequireAuth();
  const { projectId, entityId } = useParams<{ projectId: string; entityId: string }>();
  const queryClient = useQueryClient();
  const [count, setCount] = useState(10);
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null);

  const entityQuery = useQuery({
    queryKey: ["entity", projectId, entityId],
    queryFn: () => api.getEntity(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const addField = useMutation({
    mutationFn: (field: FieldCreateInput) => api.addField(accessToken!, projectId, entityId, field),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add field"),
  });

  const deleteField = useMutation({
    mutationFn: (fieldId: string) => api.deleteField(accessToken!, projectId, entityId, fieldId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete field"),
  });

  const generate = useMutation({
    mutationFn: () => api.generate(accessToken!, projectId, entityId, count),
    onSuccess: (data) => setRows(data),
    onError: (error: Error) => toast.error(error.message || "Generation failed"),
  });

  if (!accessToken) return null;

  const entity = entityQuery.data;
  const columns = entity?.fields.map((f) => f.name) ?? [];

  return (
    <AppShell>
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div>
          <Link
            href={`/projects/${projectId}`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Back to project
          </Link>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight">{entity?.name ?? "…"}</h1>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Fields</CardTitle>
            <AddFieldDialog onSubmit={(v) => addField.mutate(v)} isPending={addField.isPending} />
          </CardHeader>
          <CardContent>
            {entity?.fields.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No fields yet. Add one to start generating data.
              </p>
            )}
            {entity && entity.fields.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Constraints</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entity.fields.map((field) => (
                    <TableRow key={field.id}>
                      <TableCell className="font-medium">{field.name}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{field.field_type}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {[
                          field.required && "required",
                          field.unique && "unique",
                          !field.nullable && "not null",
                          field.min_value != null && `min ${field.min_value}`,
                          field.max_value != null && `max ${field.max_value}`,
                          field.regex && `regex ${field.regex}`,
                          field.enum_values && field.enum_values.join(" | "),
                        ]
                          .filter(Boolean)
                          .join(", ") || "—"}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteField.mutate(field.id)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Generate</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={5000}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-32"
              />
              <Button
                onClick={() => generate.mutate()}
                disabled={generate.isPending || !entity?.fields.length}
              >
                {generate.isPending ? "Generating…" : "Generate"}
              </Button>
            </div>

            {rows && rows.length > 0 && (
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {columns.map((col) => (
                        <TableHead key={col}>{col}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row, i) => (
                      <TableRow key={i}>
                        {columns.map((col) => (
                          <TableCell key={col} className="font-mono text-xs">
                            {row[col] === null || row[col] === undefined
                              ? "null"
                              : typeof row[col] === "object"
                                ? JSON.stringify(row[col])
                                : String(row[col])}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
