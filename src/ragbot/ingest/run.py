"""Ingestion orchestrator: classify -> extract -> dedup -> chunk, emitting an auditable
manifest and a chunk file. Indexing (stage 5) consumes ``chunks.jsonl`` in a later step.

Run with ``make ingest`` or ``python -m ragbot.ingest.run``.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from .chunk import chunk_document
from .classify import classify_file
from .dedup import DedupResult, dedupe
from .extract import extract, load_transcript
from .models import Chunk, ExtractedDoc


def _iter_files(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != ".DS_Store":
            yield p


def run(
    materials_dir: str | None = None,
    transcripts_dir: str | None = None,
    out_dir: str | None = None,
    captioner: Callable[[Path], str] | None = None,
) -> dict[str, Any]:
    materials = Path(materials_dir or os.environ.get("MATERIALS_DIR", "misccontext/raw"))
    transcripts = Path(transcripts_dir or os.environ.get("TRANSCRIPTS_DIR", "transcripts"))
    out = Path(out_dir or os.environ.get("INDEX_DIR", "data/index"))
    out.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    docs: list[ExtractedDoc] = []

    # --- Materials: classify + extract ---
    for path in _iter_files(materials):
        sf = classify_file(path)
        entry = sf.model_dump(mode="json")
        if not sf.keep:
            entry["stage"] = "dropped:classify"
            manifest.append(entry)
            continue
        doc = extract(sf, captioner=captioner)
        entry["extractor"] = doc.extractor
        entry["chars"] = len(doc.text)
        entry["extract_error"] = doc.extract_error
        entry["stage"] = "extracted"
        manifest.append(entry)
        docs.append(doc)

    # --- Transcripts: load (always kept; they are the primary corpus) ---
    transcript_count = 0
    if transcripts.exists():
        for path in _iter_files(transcripts):
            if path.suffix.lower() != ".txt":
                continue
            doc = load_transcript(path)
            docs.append(doc)
            transcript_count += 1

    # --- Dedup (materials + transcripts; transcripts won't collide) ---
    deduped = dedupe(docs)
    dropped_names = {name for name, _ in deduped.dropped}
    for entry in manifest:
        if entry["name"] in dropped_names:
            reason = next(r for n, r in deduped.dropped if n == entry["name"])
            entry["stage"] = "dropped:dedup"
            entry["drop_reason"] = reason

    # --- Chunk ---
    chunks: list[Chunk] = []
    for doc in deduped.kept:
        chunks.extend(chunk_document(doc))

    # --- Write outputs ---
    (out / "ingest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (out / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(c.model_dump_json() + "\n")

    summary = _summarize(manifest, deduped, chunks, transcript_count)
    (out / "ingest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print_summary(summary)
    return summary


def _summarize(
    manifest: list[dict[str, Any]],
    deduped: DedupResult,
    chunks: list[Chunk],
    transcript_count: int,
) -> dict[str, Any]:
    by_cat = Counter(c.category.value for c in chunks)
    high = [c.source_file for c in chunks if c.sensitivity.value == "high"]
    prompts = sorted({c.exercise_id for c in chunks if c.exercise_id})
    expected = [f"PE{i:02d}" for i in range(1, 11)] + [f"HW{i:02d}" for i in range(1, 9)]
    missing = [e for e in expected if e not in set(prompts)]
    return {
        "files_seen": len(manifest),
        "transcripts_loaded": transcript_count,
        "dropped_classify": sum(1 for m in manifest if m["stage"] == "dropped:classify"),
        "dropped_dedup": len(deduped.dropped),
        "kept_docs": len(deduped.kept),
        "chunks": len(chunks),
        "chunks_by_category": dict(by_cat.most_common()),
        "high_sensitivity_chunks": len(high),
        "high_sensitivity_sources": sorted(set(high)),
        "exercise_prompts_found": prompts,
        "exercise_prompts_missing": missing,
        "dedup_dropped": deduped.dropped,
    }


def _print_summary(s: dict[str, Any]) -> None:
    print("=== Ingestion summary ===")
    print(f"files seen:           {s['files_seen']}")
    print(f"transcripts loaded:   {s['transcripts_loaded']}")
    print(f"dropped (classify):   {s['dropped_classify']}")
    print(f"dropped (dedup):      {s['dropped_dedup']}")
    print(f"kept docs:            {s['kept_docs']}")
    print(f"chunks:               {s['chunks']}")
    print(f"high-sensitivity:     {s['high_sensitivity_chunks']} chunks "
          f"from {len(s['high_sensitivity_sources'])} sources")
    print(f"exercise prompts:     {len(s['exercise_prompts_found'])} found")
    if s["exercise_prompts_missing"]:
        print(f"  MISSING prompts:    {', '.join(s['exercise_prompts_missing'])}")
    print("chunks by category:")
    for cat, n in s["chunks_by_category"].items():
        print(f"  {n:5} {cat}")


if __name__ == "__main__":
    run()
