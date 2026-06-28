"""Retrieval-recall measurement (workstream D.1).

Given questions tagged with the chunk they came from, run each through the hybrid index and
record whether the source chunk appears in the top-k, and at what rank. Reports recall@k and
MRR, and surfaces the worst misses (chunks no generated question can retrieve) so coverage
gaps are visible rather than silently tolerated.
"""

from __future__ import annotations

from pydantic import BaseModel

from ragbot.retrieve.index import HybridIndex

from .generate import GeneratedQuestion


class RecallReport(BaseModel):
    k: int
    n_questions: int
    recall_at_k: float
    mrr: float
    misses: list[str]  # chunk_ids whose own question never retrieved them


def evaluate_recall(
    questions: list[GeneratedQuestion], index: HybridIndex, *, k: int = 8
) -> RecallReport:
    hits = 0
    rr_sum = 0.0
    missed: set[str] = set()
    retrieved_ok: set[str] = set()

    for gq in questions:
        results = index.search(gq.question, k=k, exclude_high_sensitivity=False)
        ids = [r.chunk_id for r in results]
        if gq.chunk_id in ids:
            rank = ids.index(gq.chunk_id) + 1
            hits += 1
            rr_sum += 1.0 / rank
            retrieved_ok.add(gq.chunk_id)
        else:
            missed.add(gq.chunk_id)

    n = len(questions)
    # A chunk is a true miss only if NONE of its questions ever retrieved it.
    misses = sorted(missed - retrieved_ok)
    return RecallReport(
        k=k,
        n_questions=n,
        recall_at_k=(hits / n) if n else 0.0,
        mrr=(rr_sum / n) if n else 0.0,
        misses=misses,
    )
