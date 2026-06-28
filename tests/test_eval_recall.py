"""Golden regression set wired into pytest (workstream D.3).

This is the test that would have caught the §1 gate bug: a corpus-present question must not come
back as ``no_concept_match``. It runs the full pipeline with a stub LLM (no Ollama needed) over
the real built index. If the index isn't built — or the embedding model can't be loaded in this
environment — the test skips rather than reporting a false regression.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ragbot.config import get_settings
from ragbot.eval.golden import check_case, load_golden, request_for
from ragbot.retrieve.index import HybridIndex
from ragbot.tutor.concept_store import ConceptStore
from ragbot.tutor.llm import LLMError
from ragbot.tutor.service import answer


class _StubLLM:
    """Stand-in LLM: always unavailable, so the pipeline exercises its deterministic paths.

    no_concept_match is decided *before* synthesis, so this is sufficient to assert routing.
    """

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        raise LLMError("stub: LLM disabled in tests")


@pytest.fixture(scope="module")
def index_and_store():
    settings = get_settings()
    if not Path(f"{settings.chroma_dir}/records.jsonl").exists():
        pytest.skip("index not built (run `make build-all`)")
    index = HybridIndex(persist_dir=settings.chroma_dir)
    try:
        index.search("warm up the embedder", k=1)  # surfaces a missing model as a skip, not a fail
    except Exception as exc:  # noqa: BLE001 - environmental, not a regression
        pytest.skip(f"retrieval unavailable in this environment: {exc}")
    return index, ConceptStore.build(settings), settings


@pytest.mark.parametrize("case", load_golden(), ids=lambda c: c.question)
def test_golden_case(case, index_and_store):
    index, store, settings = index_and_store
    response = answer(
        request_for(case), store=store, index=index, llm=_StubLLM(), settings=settings
    )
    result = check_case(case, response, index, k=settings.retrieval_k)
    assert result.passed, result.reason
