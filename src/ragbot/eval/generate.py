"""Per-chunk question generation (workstream D.1).

For each (sampled) chunk we ask the local LLM for K natural student questions whose answer is
in that chunk. Output is cached to ``data/eval/questions.jsonl`` keyed by ``chunk_id`` so it is
reproducible and not regenerated every run. Generation cost is local-Ollama time, not money;
the default sample is modest and what was sampled vs skipped is logged (no silent truncation).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ragbot.tutor.llm import LLMClient, LLMError

_GEN_SYSTEM = """\
You write natural questions a student would ask, whose answer is contained in the given course \
excerpt. Output ONLY the questions, one per line, no numbering or preamble. Each must be \
answerable from the excerpt alone and sound like a real student (not a quiz item)."""


class GeneratedQuestion:
    __slots__ = ("chunk_id", "source_file", "question")

    def __init__(self, chunk_id: str, source_file: str, question: str):
        self.chunk_id = chunk_id
        self.source_file = source_file
        self.question = question

    def to_json(self) -> dict[str, str]:
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "question": self.question,
        }


def load_chunks(path: str | Path) -> list[dict[str, Any]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def sample_chunks(chunks: list[dict[str, Any]], sample: int | None) -> list[dict[str, Any]]:
    """Evenly sample ``sample`` chunks across the corpus (deterministic stride). None -> all."""
    if sample is None or sample >= len(chunks):
        return chunks
    stride = max(1, len(chunks) // sample)
    return chunks[::stride][:sample]


def _load_cache(cache_path: Path) -> dict[str, list[GeneratedQuestion]]:
    if not cache_path.exists():
        return {}
    cache: dict[str, list[GeneratedQuestion]] = {}
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cache.setdefault(r["chunk_id"], []).append(
            GeneratedQuestion(r["chunk_id"], r["source_file"], r["question"])
        )
    return cache


def generate_questions(
    chunks: list[dict[str, Any]],
    llm: LLMClient,
    *,
    k: int = 2,
    sample: int | None = 60,
    cache_path: str | Path = "data/eval/questions.jsonl",
    log: Callable[[str], None] = print,
) -> list[GeneratedQuestion]:
    """Generate (and cache) K questions per sampled chunk. Cached chunks are not regenerated."""
    cache_p = Path(cache_path)
    cache_p.parent.mkdir(parents=True, exist_ok=True)
    cache = _load_cache(cache_p)

    selected = sample_chunks(chunks, sample)
    log(
        f"[generate] corpus={len(chunks)} sampled={len(selected)} "
        f"skipped={len(chunks) - len(selected)}"
    )

    out: list[GeneratedQuestion] = []
    to_generate = [c for c in selected if c["chunk_id"] not in cache]
    log(f"[generate] cached={len(selected) - len(to_generate)} new={len(to_generate)} (k={k})")

    with cache_p.open("a", encoding="utf-8") as fh:
        for c in to_generate:
            user = f"Excerpt:\n{c['text'].strip()[:1500]}\n\nWrite {k} questions:"
            try:
                raw = llm.chat(_GEN_SYSTEM, user, temperature=0.3)
            except LLMError as exc:
                log(f"[generate] LLM unavailable ({exc}); stopping early.")
                break
            qs = [ln.strip(" -•\t") for ln in raw.splitlines() if ln.strip()][:k]
            for q in qs:
                gq = GeneratedQuestion(c["chunk_id"], c["source_file"], q)
                cache.setdefault(c["chunk_id"], []).append(gq)
                fh.write(json.dumps(gq.to_json()) + "\n")

    for c in selected:
        out.extend(cache.get(c["chunk_id"], []))
    return out
