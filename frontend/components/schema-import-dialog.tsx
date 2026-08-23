"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type {
  ProfileColumnReport,
  ProfileResponse,
  ProjectTemplate,
  SchemaImportResponse,
} from "@/lib/types";

/** Marks the warnings that describe redaction rather than a loss. They are
 * shown in their own panel, because "we replaced the real names with
 * synthetic ones" is the tool working, not something that went wrong. */
const REDACTION_MARKER = "replaced with synthetic values";

type Source = "sql" | "json-schema" | "database" | "sample" | "learn" | "url";

const SOURCE_LABELS: Record<Source, string> = {
  sql: "SQL (CREATE TABLE…)",
  "json-schema": "JSON Schema / OpenAPI",
  database: "A live database (via a saved connection)",
  sample: "Sample data file (schema only)",
  learn: "Sample data file (learn distributions)",
  url: "URL (learn distributions)",
};

/**
 * Two-step by construction: importing only *previews* a template, and a
 * second explicit click applies it. That mirrors the backend, where an
 * importer returns a template and never creates anything — see
 * app/services/schema_import/common.py. The review screen exists because
 * every importer is lossy, and the warnings are the honest part.
 */
export function SchemaImportDialog({ onImported }: { onImported: () => void }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState<Source>("sql");
  const [projectName, setProjectName] = useState("");
  const [sql, setSql] = useState("");
  const [dialect, setDialect] = useState("postgres");
  const [jsonText, setJsonText] = useState("");
  const [urlText, setUrlText] = useState("");
  // The database importer reads a connection, and connections are
  // project-scoped — so this branch picks a project before a connection.
  const [sourceProjectId, setSourceProjectId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [schemaName, setSchemaName] = useState("");
  const [result, setResult] = useState<
    (SchemaImportResponse & { report?: ProfileColumnReport[] }) | null
  >(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setResult(null);
    setSql("");
    setJsonText("");
    setUrlText("");
    setConnectionId("");
    setSchemaName("");
    setProjectName("");
    if (fileRef.current) fileRef.current.value = "";
  };

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(accessToken!),
    enabled: !!accessToken && open && source === "database",
  });

  const connectionsQuery = useQuery({
    queryKey: ["database-connections", sourceProjectId],
    queryFn: () => api.listDatabaseConnections(accessToken!, sourceProjectId),
    enabled: !!accessToken && source === "database" && !!sourceProjectId,
  });

  const preview = useMutation({
    mutationFn: async (): Promise<
      SchemaImportResponse & { report?: ProfileColumnReport[] }
    > => {
      const token = accessToken!;
      if (source === "sql") {
        return api.importSchemaFromSql(token, sql, dialect, projectName);
      }
      if (source === "json-schema") {
        let document: unknown;
        try {
          document = JSON.parse(jsonText);
        } catch {
          throw new Error("That isn't valid JSON");
        }
        return api.importSchemaFromJsonSchema(token, document, projectName);
      }
      if (source === "database") {
        if (!connectionId) throw new Error("Choose a connection first");
        return api.importSchemaFromDatabase(
          token,
          connectionId,
          schemaName.trim() || undefined,
          projectName
        );
      }
      if (source === "url") {
        const urls = urlText
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);
        if (urls.length === 0) throw new Error("Enter at least one URL");
        const profiled: ProfileResponse = await api.profileFromSource(token, {
          urls,
          project_name: projectName || null,
        });
        return {
          template: profiled.template,
          warnings: profiled.warnings,
          report: profiled.report,
        };
      }
      const chosen = Array.from(fileRef.current?.files ?? []);
      if (chosen.length === 0) throw new Error("Choose a file first");
      if (source === "learn") {
        const profiled: ProfileResponse = await api.profileSample(
          token,
          chosen,
          projectName
        );
        return {
          template: profiled.template,
          warnings: profiled.warnings,
          report: profiled.report,
        };
      }
      return api.importSchemaFromSample(token, chosen[0], projectName);
    },
    onSuccess: setResult,
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not read that schema"),
  });

  const apply = useMutation({
    mutationFn: (template: ProjectTemplate) => api.importProject(accessToken!, template),
    onSuccess: (project) => {
      toast.success(`"${project.name}" created`);
      setOpen(false);
      reset();
      onImported();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create the project"),
  });

  const entityCount = result?.template.entities.length ?? 0;
  const fieldCount =
    result?.template.entities.reduce((sum, e) => sum + e.fields.length, 0) ?? 0;

  const piiFindings = (result?.report ?? []).filter((r) => r.pii_kind !== null);
  const redacted = piiFindings.filter((r) => r.pii_redacted);
  const flaggedOnly = piiFindings.filter((r) => !r.pii_redacted);
  // Redaction warnings are rendered in the privacy panel instead, so they
  // don't read as failures in the list below it.
  const lossWarnings = (result?.warnings ?? []).filter(
    (w) => !w.includes(REDACTION_MARKER)
  );

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger render={<Button variant="outline">Import schema</Button>} />
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import a schema</DialogTitle>
        </DialogHeader>

        {result === null ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Build a project from a schema you already have. Nothing is created
              until you review what came back.
            </p>

            <div className="flex flex-col gap-2">
              <Label>Source</Label>
              <Select value={source} onValueChange={(v) => setSource((v ?? "sql") as Source)}>
                <SelectTrigger>
                  <SelectValue>
                    {(v: string) => SOURCE_LABELS[(v || "sql") as Source]}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(SOURCE_LABELS) as Source[]).map((key) => (
                    <SelectItem key={key} value={key}>
                      {SOURCE_LABELS[key]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="import-project-name">Project name (optional)</Label>
              <Input
                id="import-project-name"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="Defaults to something derived from the source"
              />
            </div>

            {source === "sql" && (
              <>
                <div className="flex flex-col gap-2">
                  <Label>Dialect</Label>
                  <Select value={dialect} onValueChange={(v) => setDialect(v ?? "postgres")}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["postgres", "mysql", "sqlite", "snowflake", "bigquery"].map((d) => (
                        <SelectItem key={d} value={d}>
                          {d}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="import-sql">CREATE TABLE statements</Label>
                  <Textarea
                    id="import-sql"
                    className="min-h-40 font-mono text-xs"
                    placeholder={"CREATE TABLE customers (\n  id SERIAL PRIMARY KEY,\n  email TEXT NOT NULL UNIQUE\n);"}
                    value={sql}
                    onChange={(e) => setSql(e.target.value)}
                  />
                </div>
              </>
            )}

            {source === "json-schema" && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="import-json">JSON Schema or OpenAPI document</Label>
                <Textarea
                  id="import-json"
                  className="min-h-40 font-mono text-xs"
                  placeholder={'{ "title": "Person", "type": "object", "properties": { … } }'}
                  value={jsonText}
                  onChange={(e) => setJsonText(e.target.value)}
                />
              </div>
            )}

            {source === "database" && (
              <>
                <div className="flex flex-col gap-2">
                  <Label>Connection lives in</Label>
                  <Select
                    value={sourceProjectId}
                    onValueChange={(v) => {
                      setSourceProjectId(v ?? "");
                      // A connection id is only meaningful inside its own
                      // project, so changing project has to clear it.
                      setConnectionId("");
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a project" />
                    </SelectTrigger>
                    <SelectContent>
                      {(projectsQuery.data ?? []).map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-col gap-2">
                  <Label>Connection</Label>
                  <Select
                    value={connectionId}
                    onValueChange={(v) => setConnectionId(v ?? "")}
                    disabled={!sourceProjectId}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a saved connection" />
                    </SelectTrigger>
                    <SelectContent>
                      {(connectionsQuery.data ?? []).map((connection) => (
                        <SelectItem key={connection.id} value={connection.id}>
                          {connection.name} ({connection.dialect})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {sourceProjectId && (connectionsQuery.data ?? []).length === 0 && (
                    <p className="text-xs text-ink-faint">
                      That project has no database connections. Add one on the project&apos;s
                      Data page first.
                    </p>
                  )}
                </div>

                <div className="flex flex-col gap-2">
                  <Label htmlFor="import-schema-name">Schema (optional)</Label>
                  <Input
                    id="import-schema-name"
                    value={schemaName}
                    onChange={(e) => setSchemaName(e.target.value)}
                    placeholder="public"
                  />
                  <p className="text-xs text-ink-faint">
                    SynthFlow reads the table definitions only — column types, keys and
                    constraints. No rows are read, so nothing from the live database ends up in
                    the new project.
                  </p>
                </div>
              </>
            )}

            {source === "url" && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="import-urls">
                  CSV, Excel or JSON URLs — one per line
                </Label>
                <Textarea
                  id="import-urls"
                  className="min-h-24 font-mono text-xs"
                  placeholder={"https://example.com/customers.csv\nhttps://example.com/orders.csv"}
                  value={urlText}
                  onChange={(e) => setUrlText(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  SynthFlow downloads and profiles these the same way as an
                  upload — fitted distributions, category frequencies,
                  correlations, and relationships between several files.
                  Only http and https, and each file is capped at 64 MB.
                </p>
              </div>
            )}

            {(source === "sample" || source === "learn") && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="import-file">
                  {source === "learn"
                    ? "CSV, Excel or JSON files — upload related files together"
                    : "CSV, Excel or JSON file"}
                </Label>
                <Input
                  id="import-file"
                  ref={fileRef}
                  type="file"
                  multiple={source === "learn"}
                  accept=".csv,.json,.xlsx,.xls"
                />
                <p className="text-xs text-muted-foreground">
                  {source === "learn" ? (
                    <>
                      Fits a real distribution to each numeric column
                      (<code className="font-mono">gauss</code>,{" "}
                      <code className="font-mono">lognormal</code>,{" "}
                      <code className="font-mono">expo</code>), measures
                      category frequencies, and detects correlations between
                      columns — so generated data has the shape of the
                      original, not just its schema. Upload several related
                      files at once and relationships between them are
                      detected too.
                    </>
                  ) : (
                    <>
                      Field types are inferred from the rows in the file. Ranges
                      and enum values reflect only what appears in the sample —
                      this isn&apos;t distribution fitting; pick the option
                      above for that.
                    </>
                  )}
                </p>
              </div>
            )}

            <DialogFooter>
              <Button onClick={() => preview.mutate()} disabled={preview.isPending}>
                {preview.isPending ? "Reading…" : "Preview import"}
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <p className="text-sm">
                <span className="font-medium">{result.template.name}</span> —{" "}
                {entityCount} {entityCount === 1 ? "entity" : "entities"}, {fieldCount}{" "}
                fields, {result.template.relationships.length} relationships.
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Nothing has been created yet. Review this, then apply it.
              </p>
            </div>

            {piiFindings.length > 0 && (
              <div className="flex flex-col gap-2 rounded-md border p-3">
                <p className="text-sm font-medium">
                  Personal data found in {piiFindings.length} column
                  {piiFindings.length === 1 ? "" : "s"}
                </p>
                {redacted.length > 0 && (
                  <>
                    <p className="text-xs text-muted-foreground">
                      Replaced with synthetic generators — no value from your
                      file was copied into this project.
                    </p>
                    <ul className="flex flex-col gap-1 text-xs">
                      {redacted.map((r) => (
                        <li key={`${r.entity}.${r.column}`} className="font-mono">
                          {r.entity}.{r.column}
                          <span className="opacity-60"> → {r.pii_kind}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {flaggedOnly.length > 0 && (
                  <>
                    <p className="text-xs text-muted-foreground">
                      Possibly personal, but not certain enough to replace
                      automatically — check these yourself:
                    </p>
                    <ul className="flex flex-col gap-1 text-xs">
                      {flaggedOnly.map((r) => (
                        <li key={`${r.entity}.${r.column}`} className="font-mono">
                          {r.entity}.{r.column}
                          <span className="opacity-60">
                            {" "}
                            — {r.pii_reason}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {lossWarnings.length > 0 && (
              <div className="flex flex-col gap-2 rounded-md border border-dashed p-3">
                <p className="text-sm font-medium">
                  {lossWarnings.length} thing
                  {lossWarnings.length === 1 ? "" : "s"} couldn&apos;t be carried across
                </p>
                <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-muted-foreground">
                  {lossWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex flex-col gap-3">
              {result.template.entities.map((entity) => (
                <div key={entity.name} className="rounded-md border px-3 py-2">
                  <p className="font-mono text-sm font-medium">{entity.name}</p>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    {entity.fields.map((field) => (
                      <span key={field.name} className="font-mono">
                        {field.name}
                        <span className="opacity-60">:{field.field_type}</span>
                        {field.required && <span className="opacity-60">*</span>}
                        {field.formula && (
                          <span className="opacity-60"> = {field.formula}</span>
                        )}
                        {field.preset && (
                          <span className="opacity-60"> = {field.preset}()</span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {result.template.relationships.length > 0 && (
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">Relationships</p>
                {result.template.relationships.map((link) => (
                  <code
                    key={`${link.source_entity}.${link.source_field}`}
                    className="font-mono text-xs text-muted-foreground"
                  >
                    {link.source_entity}.{link.source_field} → {link.target_entity}.
                    {link.target_field}
                  </code>
                ))}
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setResult(null)}>
                Back
              </Button>
              <Button
                onClick={() => apply.mutate(result.template)}
                disabled={apply.isPending || entityCount === 0}
              >
                {apply.isPending ? "Creating…" : "Create project"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
