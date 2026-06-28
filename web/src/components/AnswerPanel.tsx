"use client";

import type { QueryResponse } from "@/lib/types";
import { Card, Badge } from "./ui";
import { AnswerMarkdown } from "./AnswerMarkdown";
import { References } from "./References";

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="chip chip-lecture">Lecture</span> reference
      </span>
      <span className="flex items-center gap-1.5">
        <span className="chip chip-timestamp">00:00:00</span> timestamp
      </span>
    </div>
  );
}

export function AnswerPanel({
  data,
  onInspect,
  inspectBusy,
}: {
  data: QueryResponse;
  onInspect?: () => void;
  inspectBusy?: boolean;
}) {
  if (data.no_concept_match) {
    return (
      <Card className="p-6">
        <p className="text-[15px] leading-7 text-foreground">{data.intro_text}</p>
      </Card>
    );
  }

  const modeLabel = data.mode === "lecture_only" ? "Lecture-only · when & where" : "Course-wide · explained & grounded";

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-2/50 px-6 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className="border-accent/30 text-accent">{modeLabel}</Badge>
          {data.matched_concepts.slice(0, 4).map((c) => (
            <Badge key={c}>{c}</Badge>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <Legend />
          {onInspect && (
            <button
              onClick={onInspect}
              disabled={inspectBusy}
              className="rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-muted transition-colors hover:text-accent disabled:opacity-60"
            >
              {inspectBusy ? "Inspecting…" : "🔍 Inspect"}
            </button>
          )}
        </div>
      </div>

      <div className="px-6 py-5">
        {data.intro_text && (
          <p className="mb-4 text-[15px] font-medium text-foreground">{data.intro_text}</p>
        )}

        {data.answer_markdown && (
          <AnswerMarkdown markdown={data.answer_markdown} markerMap={data.marker_map} />
        )}

        <References
          references={data.references}
          caption={data.references_caption}
          coverage={data.coverage_timeline}
          coverageCaption={data.coverage_caption}
        />

        {data.citations.length > 0 && (
          <details className="mt-6 rounded-xl border border-border bg-surface-2/50 px-4 py-3 text-sm">
            <summary className="cursor-pointer font-medium text-muted">
              Grounded in {data.citations.length} source excerpt
              {data.citations.length === 1 ? "" : "s"}
            </summary>
            <ul className="scroll-fade mt-2 max-h-48 space-y-1 overflow-auto font-mono text-xs text-muted">
              {data.citations.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </Card>
  );
}
