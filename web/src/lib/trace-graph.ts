// Renderer-agnostic derivation of an inspector flow graph from a PipelineTrace.
// No React Flow import here, so a hand-rolled SVG fallback can consume the same shape.

import type { PipelineTrace, RankedChunk } from "./types";

export type NodeAccent = "accent" | "lecture" | "timestamp" | "muted" | "danger";

export interface FlowNodeData {
  title: string;
  accent: NodeAccent;
  stat?: string;
  lines: string[];
}

export interface FlowNode {
  id: string;
  x: number;
  y: number;
  data: FlowNodeData;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

const COL = 270; // horizontal spacing between stages

function shortId(id: string): string {
  const [file, n] = id.split("#");
  const stem = (file.split("/").pop() ?? file).replace(/\.[^.]+$/, "");
  const trimmed = stem.length > 22 ? stem.slice(0, 22) + "…" : stem;
  return n !== undefined ? `${trimmed} #${n}` : trimmed;
}

function rankedLines(items: RankedChunk[], limit = 3): string[] {
  return items
    .slice(0, limit)
    .map((r) => `${r.rank}. ${shortId(r.chunk_id)}  ${r.score != null ? r.score.toFixed(3) : "—"}`);
}

export function buildGraph(trace: PipelineTrace): FlowGraph {
  const nodes: FlowNode[] = [];
  const edges: FlowEdge[] = [];
  const add = (n: FlowNode) => nodes.push(n);
  const link = (source: string, target: string) =>
    edges.push({ id: `${source}->${target}`, source, target });

  let col = 0;
  const x = () => col++ * COL;

  // 1. Query (condensed vs original)
  add({
    id: "query",
    x: x(),
    y: 0,
    data: {
      title: "Query",
      accent: "accent",
      stat: trace.condensed_question === trace.original_question ? "single-turn" : "condensed",
      lines: [
        `“${trace.original_question}”`,
        ...(trace.condensed_question !== trace.original_question
          ? [`→ “${trace.condensed_question}”`]
          : []),
      ],
    },
  });

  // 2. Concepts + lexical gate
  const gate = trace.lexical_gate;
  add({
    id: "concepts",
    x: x(),
    y: 0,
    data: {
      title: "Concepts + gate",
      accent: "lecture",
      stat: trace.retrieval_path,
      lines: [
        trace.matched_concepts.length
          ? `concepts: ${trace.matched_concepts.map((c) => c.concept).join(", ")}`
          : "no concept match",
        gate ? `lexical gate: ${(gate.fraction * 100).toFixed(0)}% ${gate.passed ? "✓" : "✗"}` : "",
        gate && gate.in_vocab.length ? `in-vocab: ${gate.in_vocab.slice(0, 5).join(", ")}` : "",
      ].filter(Boolean),
    },
  });
  link("query", "concepts");

  // 3. Enriched query diff
  add({
    id: "enriched",
    x: x(),
    y: 0,
    data: {
      title: "Query expansion",
      accent: "muted",
      stat: trace.appended_terms.length ? `+${trace.appended_terms.length} terms` : "no expansion",
      lines: trace.appended_terms.length
        ? [`+ ${trace.appended_terms.slice(0, 8).join(", ")}`]
        : ["(query unchanged)"],
    },
  });
  link("concepts", "enriched");

  // 4 + 5. Dense ‖ Sparse (branch)
  add({
    id: "dense",
    x: x(),
    y: -120,
    data: {
      title: "Dense (semantic)",
      accent: "accent",
      stat: `${trace.dense.length} hits`,
      lines: rankedLines(trace.dense),
    },
  });
  col--; // keep sparse in the same column as dense
  add({
    id: "sparse",
    x: x(),
    y: 120,
    data: {
      title: "Sparse (BM25)",
      accent: "timestamp",
      stat: `${trace.sparse.length} hits`,
      lines: rankedLines(trace.sparse),
    },
  });
  link("enriched", "dense");
  link("enriched", "sparse");

  // 6. RRF fusion
  add({
    id: "rrf",
    x: x(),
    y: 0,
    data: {
      title: "RRF fusion",
      accent: "lecture",
      stat: `${trace.fused.length} fused`,
      lines: rankedLines(trace.fused),
    },
  });
  link("dense", "rrf");
  link("sparse", "rrf");

  // 7. Guardrail (sensitivity / category drops)
  add({
    id: "guardrail",
    x: x(),
    y: 0,
    data: {
      title: "Guardrail",
      accent: trace.excluded.length ? "danger" : "muted",
      stat: trace.excluded.length ? `dropped ${trace.excluded.length}` : "none dropped",
      lines: trace.excluded.length
        ? trace.excluded.slice(0, 4).map((e) => `✕ ${shortId(e.chunk_id)} (${e.reason})`)
        : ["no solution-key / filtered chunks"],
    },
  });
  link("rrf", "guardrail");

  // 8. Top-k retained
  add({
    id: "topk",
    x: x(),
    y: 0,
    data: {
      title: "Top-k retained",
      accent: "accent",
      stat: `${trace.top_k.length} chunks`,
      lines: trace.top_k
        .slice(0, 4)
        .map(
          (c, i) =>
            `S${i + 1} ${shortId(c.chunk_id)} ${c.rrf_score != null ? c.rrf_score.toFixed(3) : ""}`,
        ),
    },
  });
  link("guardrail", "topk");

  // 9. Synthesis
  add({
    id: "synthesis",
    x: x(),
    y: 0,
    data: {
      title: "LLM synthesis",
      accent: "lecture",
      stat: `${trace.raw_prose.length} chars`,
      lines: [trace.raw_prose.slice(0, 140).replace(/\s+/g, " ").trim() + "…"],
    },
  });
  link("topk", "synthesis");

  // 10. Citations resolved
  const citedCount = trace.cited_vs_retrieved.filter((c) => c.cited).length;
  add({
    id: "citations",
    x: x(),
    y: 0,
    data: {
      title: "Citations",
      accent: "timestamp",
      stat: `${citedCount}/${trace.cited_vs_retrieved.length} cited`,
      lines: trace.cited_vs_retrieved
        .slice(0, 5)
        .map((c) => `${c.cited ? "●" : "○"} ${c.marker ?? ""} ${shortId(c.source_file)}`),
    },
  });
  link("synthesis", "citations");

  return { nodes, edges };
}
