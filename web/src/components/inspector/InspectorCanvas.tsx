"use client";

import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { PipelineTrace } from "@/lib/types";
import { buildGraph, type FlowNodeData, type NodeAccent } from "@/lib/trace-graph";

const ACCENT_VAR: Record<NodeAccent, string> = {
  accent: "var(--accent)",
  lecture: "var(--lecture)",
  timestamp: "var(--timestamp)",
  muted: "var(--muted)",
  danger: "#ef4444",
};

function StageNode({ data }: NodeProps) {
  const d = data as unknown as FlowNodeData;
  const color = ACCENT_VAR[d.accent];
  return (
    <div
      className="glow-pill rounded-xl border bg-surface px-3 py-2 text-left"
      style={{ borderColor: color, width: 232 }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="flex items-center justify-between gap-2">
        <span className="font-display text-sm font-semibold" style={{ color }}>
          {d.title}
        </span>
        {d.stat && <span className="shrink-0 text-[10px] text-muted">{d.stat}</span>}
      </div>
      <ul className="mt-1 space-y-0.5 text-[11px] leading-4 text-foreground/80">
        {d.lines.map((l, i) => (
          <li key={i} className="truncate">
            {l}
          </li>
        ))}
      </ul>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { stage: StageNode };

export function InspectorCanvas({ trace }: { trace: PipelineTrace }) {
  const g = buildGraph(trace);
  const nodes: Node[] = g.nodes.map((n) => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: n.data as unknown as Record<string, unknown>,
    type: "stage",
  }));
  const edges: Edge[] = g.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
  }));
  return (
    <div className="h-full w-full">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2}>
        <Background color="var(--border)" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
