"""Retriever tests use the RRF fusion and filtering logic directly, plus a fake embedder, so
they run fast and offline (no model download, no Chroma server)."""

from __future__ import annotations

from ragbot.retrieve.index import HybridIndex, _tokenize


def test_tokenize():
    assert _tokenize("SELECT * FROM Foo_Bar;") == ["select", "from", "foo", "bar"]


def test_rrf_combines_rankings():
    dense = ["a", "b", "c"]
    sparse = ["c", "a", "d"]
    fused = dict(HybridIndex._rrf(dense, sparse, rrf_k=60))
    # 'a' (ranks 1 and 2) and 'c' (ranks 3 and 1) should outrank singletons 'b','d'.
    assert fused["a"] > fused["b"]
    assert fused["c"] > fused["d"]


def _index_with_records(records):
    idx = HybridIndex.__new__(HybridIndex)
    idx._collection = None
    idx._bm25 = None
    idx._records = {}
    idx._load_sparse(records)
    # Stub dense ranking so we don't need Chroma/embeddings in unit tests.
    idx._dense_rank = lambda q, n: [r["chunk_id"] for r in records][:n]  # type: ignore[method-assign]
    return idx


def _rec(cid, text, sensitivity="normal", category="lecture_transcript"):
    return {
        "chunk_id": cid,
        "text": text,
        "source_file": f"{cid}.txt",
        "category": category,
        "sensitivity": sensitivity,
        "citation": f"[{cid}]",
        "exercise_id": None,
    }


def test_excludes_high_sensitivity():
    records = [
        _rec("sol", "normalize the table answer key", "high", "solution_key"),
        _rec("lec", "normalization lecture on normal forms"),
    ]
    idx = _index_with_records(records)
    hits = idx.search("normalize the table", k=5, exclude_high_sensitivity=True)
    assert all(h.sensitivity != "high" for h in hits)
    assert "sol" not in {h.chunk_id for h in hits}


def test_category_filter():
    records = [
        _rec("t", "join example", category="lecture_transcript"),
        _rec("p", "join exercise prompt", category="assignment_prompt"),
    ]
    idx = _index_with_records(records)
    hits = idx.search("join", k=5, categories=["assignment_prompt"])
    assert {h.category for h in hits} == {"assignment_prompt"}
