"use client";

import type { QueryResponse } from "@/lib/types";
import { Card, Badge } from "./ui";
import { AnswerSegments } from "./AnswerSegments";
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

export function AnswerPanel({ data }: { data: QueryResponse }) {
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
        <Legend />
      </div>

      <div className="px-6 py-5">
        {data.intro_text && (
          <p className="mb-4 text-[15px] font-medium text-foreground">{data.intro_text}</p>
        )}

        {data.explanation_segments.length > 0 && (
          <AnswerSegments segments={data.explanation_segments} />
        )}

        <References references={data.references} caption={data.references_caption} />

        {data.citations.length > 0 && (
          <details className="mt-6 rounded-xl border border-border bg-surface-2/50 px-4 py-3 text-sm">
            <summary className="cursor-pointer font-medium text-muted">
              Grounded in {data.citations.length} source excerpt
              {data.citations.length === 1 ? "" : "s"}
            </summary>
            <ul className="mt-2 space-y-1 font-mono text-xs text-muted">
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
