"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * Staged "what's happening" indicator while a query runs.
 *
 * NOTE: this is an ESTIMATED progression driven by timers — the backend returns one
 * non-streamed response, so we can't know the true current stage. Making it real would require
 * SSE streaming of per-stage events (intentionally out of scope). The last stage holds until the
 * response resolves and the parent unmounts this component.
 */
const STAGES = ["Matching concepts", "Retrieving sources", "Synthesizing answer"] as const;

export function StagedProgress() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setActive(1), 700),
      setTimeout(() => setActive(2), 1600),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-2 px-1 text-xs">
      {STAGES.map((label, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <div key={label} className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 transition-colors",
                current && "glow-pulse border-[var(--timestamp-border)] text-foreground",
                done && "border-border text-muted",
                !current && !done && "border-border text-muted/60",
              )}
            >
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  current ? "bg-[var(--timestamp)]" : done ? "bg-emerald-500" : "bg-border",
                )}
              />
              {label}
            </span>
            {i < STAGES.length - 1 && <span className="text-muted/40">→</span>}
          </div>
        );
      })}
    </div>
  );
}
