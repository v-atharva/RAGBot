"use client";

import { useEffect, useState } from "react";
import type { CorpusExplain } from "@/lib/types";
import { getCorpusExplain } from "@/lib/api";

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
      <div className="font-display text-lg font-bold text-foreground">{value}</div>
      <div className="text-[11px] text-muted">{label}</div>
    </div>
  );
}

/** How the corpus was built — counts per format/category + the sensitivity guardrail tagging. */
export function CorpusExplainer() {
  const [data, setData] = useState<CorpusExplain | null>(null);
  useEffect(() => {
    getCorpusExplain().then(setData).catch(() => {});
  }, []);

  if (!data) return <p className="text-xs text-muted">Loading corpus summary…</p>;
  if (data.error) return <p className="text-xs text-red-500">Corpus summary unavailable: {data.error}</p>;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="files seen" value={data.files_seen} />
        <Stat label="docs kept" value={data.kept_docs} />
        <Stat label="chunks" value={data.chunks} />
        <Stat label="high-sensitivity" value={data.high_sensitivity_chunks} />
      </div>

      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
          Chunks by category
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(data.chunks_by_category).map(([k, v]) => (
            <span key={k} className="chip chip-lecture">
              {k} · {v}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">By format</h4>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(data.by_format).map(([k, v]) => (
            <span key={k} className="chip chip-source">
              {k} · {v}
            </span>
          ))}
        </div>
      </div>

      {data.high_sensitivity_sources.length > 0 && (
        <p className="text-[11px] text-muted">
          Guardrail excludes solution-key / exam-review sources from assignment-help retrieval:{" "}
          <span className="text-foreground/80">{data.high_sensitivity_sources.join(", ")}</span>.
        </p>
      )}
    </div>
  );
}
