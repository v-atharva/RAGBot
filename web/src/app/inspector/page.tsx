"use client";

import Link from "next/link";
import { useState } from "react";
import type { Mode, PipelineTrace } from "@/lib/types";
import { postQueryTraced } from "@/lib/api";
import { Button, Card, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";
import { InspectorCanvas } from "@/components/inspector/InspectorCanvas";
import { CorpusExplainer } from "@/components/inspector/CorpusExplainer";

const MODES: Mode[] = ["course_wide", "lecture_only"];

export default function InspectorPage() {
  const [mode, setMode] = useState<Mode>("course_wide");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [trace, setTrace] = useState<PipelineTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    const text = q.trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = await postQueryTraced(mode, text, []);
      setTrace(data.trace ?? null);
      if (!data.trace) {
        setError(data.no_concept_match ? "No match — try a core database topic." : "No trace returned.");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-5 py-3">
        <h1 className="font-display text-lg font-bold">
          Pipeline Inspector <span className="text-sm font-medium text-muted">· run a traced query</span>
        </h1>
        <Link href="/" className="text-sm text-muted transition-colors hover:text-accent">
          ← back to tutor
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <div className="inline-flex rounded-lg bg-surface-2 p-0.5">
            {MODES.map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-semibold transition-colors",
                  mode === m ? "bg-surface text-accent glow-pill" : "text-muted hover:text-foreground",
                )}
              >
                {m === "course_wide" ? "Course-wide" : "Lecture-only"}
              </button>
            ))}
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="Ask a question to trace…  e.g. What is BCNF?"
            className="w-72 rounded-xl border border-border bg-surface px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          />
          <Button onClick={run} disabled={loading || !q.trim()}>
            {loading ? <Spinner /> : "Trace"}
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="relative min-h-[320px] flex-1 border-b border-border lg:border-b-0 lg:border-r">
          {trace ? (
            <InspectorCanvas trace={trace} />
          ) : (
            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted">
              {error ?? "Run a query to visualize the retrieval pipeline."}
            </div>
          )}
        </div>
        <aside className="scroll-fade w-full overflow-auto p-4 lg:w-[380px]">
          <h2 className="mb-2 font-display text-sm font-semibold uppercase tracking-wide text-muted">
            Corpus / ingestion
          </h2>
          <Card className="p-3">
            <CorpusExplainer />
          </Card>
        </aside>
      </div>
    </div>
  );
}
