"use client";

import { useEffect } from "react";
import type { PipelineTrace } from "@/lib/types";
import { Button } from "@/components/ui";
import { InspectorCanvas } from "./InspectorCanvas";
import { CorpusExplainer } from "./CorpusExplainer";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="rounded-lg border border-border bg-surface-2/50 px-3 py-2" open>
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
      </summary>
      <div className="mt-2 text-xs leading-5 text-foreground/85">{children}</div>
    </details>
  );
}

export function InspectorModal({ trace, onClose }: { trace: PipelineTrace; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background/95 backdrop-blur-sm">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <h2 className="font-display text-lg font-bold">
          Pipeline Inspector <span className="text-sm font-medium text-muted">· how this answer was built</span>
        </h2>
        <Button variant="outline" onClick={onClose} className="px-3 py-1.5 text-sm">
          Close (Esc)
        </Button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="min-h-[320px] flex-1 border-b border-border lg:border-b-0 lg:border-r">
          <InspectorCanvas trace={trace} />
        </div>

        <aside className="scroll-fade w-full space-y-3 overflow-auto p-4 lg:w-[380px]">
          {trace.condensed_question !== trace.original_question && (
            <Panel title="Condensed follow-up">
              <p className="text-muted">“{trace.original_question}”</p>
              <p className="mt-1">→ “{trace.condensed_question}”</p>
            </Panel>
          )}
          {trace.framing_context && (
            <Panel title="Framing notes (not cited)">
              <pre className="whitespace-pre-wrap font-sans">{trace.framing_context}</pre>
            </Panel>
          )}
          <Panel title="Raw model output (markdown)">
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-[11px]">
              {trace.raw_prose}
            </pre>
          </Panel>
          <Panel title="Corpus / ingestion">
            <CorpusExplainer />
          </Panel>
        </aside>
      </div>
    </div>
  );
}
