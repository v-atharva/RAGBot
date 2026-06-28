"""Curated golden regression set (workstream D.3).

Hand-written cases with expected source files (and the genuinely-absent negatives), so CI can
fail if retrieval/routing regresses — in particular the §1 gate bug, where a corpus-present
question wrongly came back as "no match". See ``data/eval/golden.jsonl``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from ragbot.retrieve.index import HybridIndex
from ragbot.tutor.schemas import Mode, QueryRequest, QueryResponse

DEFAULT_GOLDEN_PATH = "data/eval/golden.jsonl"


class GoldenCase(BaseModel):
    question: str
    mode: Mode
    expect_sources: list[str] = []  # substrings expected among retrieved/cited source files
    expect_no_match: bool = False


class GoldenResult(BaseModel):
    case: GoldenCase
    passed: bool
    reason: str


def load_golden(path: str | Path = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [GoldenCase(**json.loads(line)) for line in lines if line.strip()]


def _sources_present(case: GoldenCase, index: HybridIndex, k: int) -> tuple[bool, str]:
    """Check the expected source substrings appear among the top-k retrieved chunks."""
    hits = index.search(case.question, k=k, exclude_high_sensitivity=True)
    files = " ".join(h.source_file for h in hits).lower()
    missing = [s for s in case.expect_sources if s.lower() not in files]
    if missing:
        got = [h.source_file for h in hits]
        return False, f"missing expected source(s) {missing} in top-{k}: {got}"
    return True, "ok"


def check_case(
    case: GoldenCase, response: QueryResponse, index: HybridIndex, *, k: int = 8
) -> GoldenResult:
    """Validate one golden case against a pipeline response + raw retrieval."""
    if case.expect_no_match:
        ok = response.no_concept_match
        return GoldenResult(
            case=case, passed=ok,
            reason="ok" if ok else "expected no_concept_match but got an answer",
        )

    # Positive case: must NOT be a no-match (the §1 regression), and expected sources retrieved.
    if response.no_concept_match:
        return GoldenResult(case=case, passed=False, reason="regressed to no_concept_match")
    src_ok, reason = _sources_present(case, index, k)
    return GoldenResult(case=case, passed=src_ok, reason=reason)


def request_for(case: GoldenCase) -> QueryRequest:
    return QueryRequest(mode=case.mode, question=case.question)
