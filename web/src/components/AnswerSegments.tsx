"use client";

import type { ProseSegment } from "@/lib/types";

/**
 * Renders model prose with lecture references and timestamps colour-highlighted. The spans
 * are pre-typed by the backend, so colouring is reliable — no client-side parsing.
 */
export function AnswerSegments({ segments }: { segments: ProseSegment[] }) {
  return (
    <div className="whitespace-pre-wrap text-[15px] leading-7 text-foreground">
      {segments.map((s, i) => {
        if (s.type === "lecture") {
          return (
            <span key={i} className="chip chip-lecture">
              {s.text}
            </span>
          );
        }
        if (s.type === "timestamp") {
          return (
            <span key={i} className="chip chip-timestamp">
              {s.text}
            </span>
          );
        }
        return <span key={i}>{s.text}</span>;
      })}
    </div>
  );
}
