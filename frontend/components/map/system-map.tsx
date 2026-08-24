"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useStore,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Link from "next/link";
import { useMemo } from "react";

import { CoreSampleNode, TerminalNode } from "@/components/map/core-sample-node";
import { fieldFill } from "@/lib/field-visual";
import { OUTPUT_COLOR, OUTPUT_LABEL } from "@/lib/field-visual";
import { useReducedMotion } from "@/lib/motion";
import type { Entity, OutputSummary, Relationship } from "@/lib/types";

const NODE_TYPES = { core: CoreSampleNode, terminal: TerminalNode };

const COL_SOURCE = 0;
const COL_ENTITY = 300;
const COL_DEST = 660;

export interface MapSource {
  id: string;
  label: string;
  detail: string;
  color: string;
}

/**
 * The project as the pipeline it is: sources on the left, entities in the
 * middle, destinations on the right.
 *
 * This replaces ten stacked cards where the relationships between entities were
 * a bulleted list of "Customer.id → Order.customer_id" and the outputs were
 * spread across every entity's own page.
 */
export function SystemMap({
  projectId,
  entities,
  relationships,
  outputs,
  sources,
  /** Rows currently moving, by entity id. Drives the edge animation rate, so a
   * busy pipeline visibly moves faster than an idle one. */
  activity,
}: {
  projectId: string;
  entities: Entity[];
  relationships: Relationship[];
  outputs: OutputSummary[];
  sources: MapSource[];
  activity?: Record<string, number>;
}) {
  return (
    <ReactFlowProvider>
      <MapCanvas
        projectId={projectId}
        entities={entities}
        relationships={relationships}
        outputs={outputs}
        sources={sources}
        activity={activity}
      />
    </ReactFlowProvider>
  );
}

function MapCanvas({
  projectId,
  entities,
  relationships,
  outputs,
  sources,
  activity,
}: {
  projectId: string;
  entities: Entity[];
  relationships: Relationship[];
  outputs: OutputSummary[];
  sources: MapSource[];
  activity?: Record<string, number>;
}) {
  const reduced = useReducedMotion();

  const nodes = useMemo<Node[]>(() => {
    const out: Node[] = [];

    // Entity height varies with field count, so columns are laid out by running
    // offset rather than index × constant — otherwise a 30-field entity
    // overlaps whatever follows it.
    let y = 0;
    sources.forEach((source, index) => {
      out.push({
        id: `src-${source.id}`,
        type: "terminal",
        position: { x: COL_SOURCE, y: index * 78 },
        data: { ...source, side: "source" },
        draggable: false,
      });
    });

    y = 0;
    entities.forEach((entity) => {
      out.push({
        id: entity.id,
        type: "core",
        position: { x: COL_ENTITY, y },
        data: { entity, projectId },
      });
      y += 88 + entity.fields.length * 11.5;
    });

    outputs.forEach((output, index) => {
      out.push({
        id: `out-${output.id}`,
        type: "terminal",
        position: { x: COL_DEST, y: index * 78 },
        data: {
          label: OUTPUT_LABEL[output.type] ?? output.type,
          detail: output.detail.split(":").slice(-1)[0].trim().slice(0, 30),
          color: OUTPUT_COLOR[output.type] ?? "var(--brand)",
          side: "destination",
        },
        draggable: false,
      });
    });

    return out;
  }, [entities, outputs, sources, projectId]);

  const edges = useMemo<Edge[]>(() => {
    const out: Edge[] = [];

    for (const relationship of relationships) {
      const source = entities.find((e) => e.id === relationship.source_entity_id);
      const field = source?.fields.find((f) => f.id === relationship.source_field_id);
      const rows = activity?.[relationship.source_entity_id] ?? 0;
      out.push({
        id: relationship.id,
        source: relationship.source_entity_id,
        target: relationship.target_entity_id,
        label: relationship.relationship_type.replaceAll("_", " "),
        animated: !reduced && rows > 0,
        style: {
          stroke: field ? fieldFill(field.field_type, field.preset) : "var(--line)",
          strokeWidth: 1.5,
        },
        labelStyle: {
          fill: "var(--ink-faint)",
          fontSize: 9,
          fontFamily: "var(--font-mono)",
        },
        labelBgStyle: { fill: "var(--surface)" },
      });
    }

    // Every entity feeds every destination is not true, but the aggregate
    // endpoint does not say which entity backs which output for all kinds — so
    // connect only where the detail string names the entity, and leave the
    // rest unattached rather than drawing a relationship that may not exist.
    for (const output of outputs) {
      const owner = entities.find((entity) => output.detail.startsWith(`${entity.name}:`));
      if (!owner) continue;
      out.push({
        id: `edge-out-${output.id}`,
        source: owner.id,
        target: `out-${output.id}`,
        animated: !reduced && (activity?.[owner.id] ?? 0) > 0,
        style: { stroke: OUTPUT_COLOR[output.type] ?? "var(--line)", strokeWidth: 1.5 },
      });
    }

    return out;
  }, [relationships, entities, outputs, activity, reduced]);

  if (entities.length === 0) {
    return (
      <div className="flex h-80 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line text-center">
        <p className="text-sm text-ink-dim">No entities yet.</p>
        <p className="max-w-xs text-xs text-ink-faint">
          Add one and it appears here as a core sample — a band per field, coloured by type.
        </p>
      </div>
    );
  }

  return (
    <div className="h-[clamp(26rem,68vh,44rem)] overflow-hidden rounded-xl border border-line bg-ground">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.25}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <ParallaxBackdrop />
        <Background
          variant={BackgroundVariant.Dots}
          gap={22}
          size={1}
          color="var(--line)"
          className="opacity-60"
        />
        <Controls
          showInteractive={false}
          className="!rounded-lg !border !border-line !shadow-none"
        />
        <MiniMap
          pannable
          zoomable
          nodeColor="var(--surface-3)"
          maskColor="color-mix(in srgb, var(--ground) 78%, transparent)"
          className="!rounded-lg !border !border-line !bg-surface"
        />
      </ReactFlow>
    </div>
  );
}

/**
 * The far depth plane.
 *
 * Reads the live viewport and pans at 55% of the node layer's rate, so the
 * backdrop lags behind the content as you drag. That parallax is the depth cue —
 * real relative motion rather than a drop shadow implying it — and it does a
 * job: it separates the structural grid from the content sitting on it, so a
 * pan reads as movement across a surface instead of a list scrolling.
 */
function ParallaxBackdrop() {
  const [x, y, zoom] = useStore((state) => state.transform);
  const reduced = useReducedMotion();
  if (reduced) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
      style={{ zIndex: 0 }}
    >
      <div
        className="absolute inset-[-50%] opacity-[0.55]"
        style={{
          transform: `translate3d(${x * 0.55}px, ${y * 0.55}px, 0)`,
          backgroundImage:
            "linear-gradient(var(--line-soft) 1px, transparent 1px), linear-gradient(90deg, var(--line-soft) 1px, transparent 1px)",
          backgroundSize: `${110 * zoom}px ${110 * zoom}px`,
        }}
      />
    </div>
  );
}

/** The below-`md` fallback. A canvas on a phone is not a canvas — you cannot
 * pan and read at once on a 375px screen, so the same information is a list. */
export function SystemMapList({
  projectId,
  entities,
}: {
  projectId: string;
  entities: Entity[];
}) {
  return (
    <ul className="flex flex-col gap-2">
      {entities.map((entity, index) => (
        <li key={entity.id}>
          <Link
            href={`/projects/${projectId}/entities/${entity.id}`}
            data-tour={index === 0 ? "first-entity-card" : undefined}
            className="flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2.5"
          >
            <span className="flex h-8 w-1.5 shrink-0 flex-col gap-px">
              {entity.fields.slice(0, 8).map((field) => (
                <span
                  key={field.id}
                  className="flex-1 rounded-[1px]"
                  style={{ background: fieldFill(field.field_type, field.preset) }}
                />
              ))}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{entity.name}</span>
              <span className="font-mono text-xs text-ink-faint">
                {entity.fields.length} fields
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
