"""Build the hybrid index from the ingestion pipeline's chunk output.

Separate from ``ragbot.ingest.run`` because embedding is slow and needs the model, whereas
ingestion is fast and offline. Run with ``make index`` after ``make ingest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .index import HybridIndex


def build(chunks_path: str | Path | None = None, persist_dir: str | Path | None = None) -> int:
    index_dir = os.environ.get("INDEX_DIR", "data/index")
    chunks_file = Path(chunks_path or Path(index_dir) / "chunks.jsonl")
    if not chunks_file.exists():
        raise SystemExit(f"chunks file not found: {chunks_file}. Run `make ingest` first.")
    chunks = [json.loads(line) for line in chunks_file.read_text(encoding="utf-8").splitlines()]
    idx = HybridIndex(persist_dir=persist_dir or Path(index_dir) / "chroma")
    n = idx.build(chunks)
    print(f"Indexed {n} chunks into {idx.persist_dir}")
    return n


if __name__ == "__main__":
    build()
