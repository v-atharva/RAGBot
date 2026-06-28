"""Eval entry point (workstream D.4): ``make eval`` -> ``python -m ragbot.eval.run``.

Runs three things and prints a human report:
  1. per-chunk question generation (cached) -> retrieval recall@k / MRR + worst misses
  2. the curated golden set through the full pipeline (catches the §1 gate regression)
Exits non-zero if any golden case fails, so CI gates on it.
"""

from __future__ import annotations

import sys

from ragbot.config import get_settings
from ragbot.retrieve.index import HybridIndex
from ragbot.tutor.concept_store import ConceptStore
from ragbot.tutor.llm import get_llm
from ragbot.tutor.service import answer

from .generate import generate_questions, load_chunks
from .golden import check_case, load_golden, request_for
from .recall import evaluate_recall


def main() -> int:
    settings = get_settings()
    index = HybridIndex(persist_dir=settings.chroma_dir)
    store = ConceptStore.build(settings)
    llm = get_llm(settings)

    # --- 1. generation + recall ---------------------------------------------------------
    print("== Retrieval recall (per-chunk generated questions) ==")
    try:
        chunks = load_chunks(f"{settings.index_dir}/chunks.jsonl")
    except FileNotFoundError:
        print("  chunks.jsonl not found — run `make build-all` first. Skipping recall.")
        chunks = []

    if chunks:
        questions = generate_questions(chunks, llm, k=2, sample=60)
        if questions:
            report = evaluate_recall(questions, index, k=settings.retrieval_k)
            print(f"  questions={report.n_questions}  recall@{report.k}={report.recall_at_k:.3f}"
                  f"  MRR={report.mrr:.3f}")
            if report.misses:
                print(f"  worst misses ({len(report.misses)} chunks no question retrieves):")
                for cid in report.misses[:10]:
                    print(f"    - {cid}")
        else:
            print("  no questions generated (LLM unavailable?) — skipping recall.")

    # --- 2. golden regression set -------------------------------------------------------
    print("\n== Golden set (full pipeline) ==")
    failures = 0
    for case in load_golden():
        response = answer(request_for(case), store=store, index=index, llm=llm, settings=settings)
        result = check_case(case, response, index, k=settings.retrieval_k)
        flag = "PASS" if result.passed else "FAIL"
        if not result.passed:
            failures += 1
        print(f"  [{flag}] ({case.mode}) {case.question}\n         {result.reason}")

    print(f"\nGolden: {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
