"""Hybrid index: dense (Chroma + local embeddings) + sparse (BM25), fused with RRF.

Chunks carry provenance metadata (source, category, sensitivity, citation, exercise id). The
retriever can exclude ``sensitivity=high`` chunks — the hook the guardrail uses in
assignment-help mode so solution keys never surface in an answer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .embedder import Embedder

if TYPE_CHECKING:
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# Stopwords stripped when testing whether a query shares *content* vocabulary with the corpus.
# (BM25 alone can't gate relevance: common words like "how"/"the" appear in nearly every chunk.)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "is", "are", "was", "were", "be",
    "to", "of", "in", "on", "for", "with", "how", "do", "does", "did", "can", "could", "i",
    "you", "we", "what", "when", "where", "why", "which", "who", "this", "that", "it", "as",
    "at", "by", "from", "about", "into", "my", "your", "me", "turn",
}


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_file: str
    category: str
    sensitivity: str
    citation: str
    exercise_id: str | None = None
    score: float = 0.0


# --- Phase-2 trace artifacts (raw data; schemas.py shapes the API payload) ---


@dataclass
class LexicalGateReport:
    """Why the concept-less relevance gate passed/failed (see has_lexical_match)."""

    tokens: list[str]
    content_tokens: list[str]
    dropped_stopwords: list[str]
    in_vocab: list[str]
    fraction: float
    passed: bool


@dataclass
class RetrievalTrace:
    """Per-stage rankings recorded by search_with_trace (dense ‖ sparse → RRF → filters)."""

    dense: list[tuple[str, float]] = field(default_factory=list)  # (chunk_id, 1 - cos distance)
    sparse: list[tuple[str, float]] = field(default_factory=list)  # (chunk_id, BM25 score)
    fused: list[tuple[str, float]] = field(default_factory=list)  # (chunk_id, RRF score)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (chunk_id, reason)


class HybridIndex:
    """Dense + sparse retrieval over a chunk collection with reciprocal-rank fusion."""

    def __init__(self, persist_dir: str | Path = "data/index/chroma", collection: str = "chunks"):
        self.persist_dir = str(persist_dir)
        self.collection_name = collection
        self.embedder = Embedder()
        self._client: ClientAPI | None = None
        self._collection: Collection | None = None
        # Sparse side kept in memory, rebuilt from the persisted chunk records.
        self._bm25: Any = None
        self._bm25_ids: list[str] = []
        self._records: dict[str, dict[str, Any]] = {}
        self._vocab: set[str] = set()  # all content tokens in the corpus (relevance gate)

    # --- build ---
    def _get_collection(self) -> Collection:
        if self._collection is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                self.collection_name, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def build(self, chunks: list[dict[str, Any]], batch_size: int = 256) -> int:
        """Index chunk dicts (as produced by the ingestion pipeline's chunks.jsonl)."""
        col = self._get_collection()
        ids = [c["chunk_id"] for c in chunks]
        docs = [c["text"] for c in chunks]
        metadatas = [
            {
                "source_file": c["source_file"],
                "category": c["category"],
                "sensitivity": c["sensitivity"],
                "citation": c["citation"],
                "exercise_id": c.get("exercise_id") or "",
            }
            for c in chunks
        ]
        for i in range(0, len(ids), batch_size):
            sl = slice(i, i + batch_size)
            embeddings = self.embedder.encode_documents(docs[sl])
            # chromadb's stubs want ndarray/Mapping; plain lists are accepted at runtime.
            col.upsert(
                ids=ids[sl],
                documents=docs[sl],
                metadatas=metadatas[sl],  # type: ignore[arg-type]
                embeddings=embeddings,  # type: ignore[arg-type]
            )
        # Persist the raw records for BM25 reload.
        records_path = Path(self.persist_dir) / "records.jsonl"
        with records_path.open("w", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c) + "\n")
        self._load_sparse(chunks)
        return len(ids)

    def _load_sparse(self, chunks: list[dict[str, Any]]) -> None:
        from rank_bm25 import BM25Okapi

        self._bm25_ids = [c["chunk_id"] for c in chunks]
        self._records = {c["chunk_id"]: c for c in chunks}
        tokenized = [_tokenize(c["text"]) for c in chunks]
        self._bm25 = BM25Okapi(tokenized)
        self._vocab = {tok for doc in tokenized for tok in doc}

    def _ensure_sparse(self) -> None:
        if self._bm25 is not None:
            return
        records_path = Path(self.persist_dir) / "records.jsonl"
        if not records_path.exists():
            raise RuntimeError("Index not built: records.jsonl missing. Run build() first.")
        lines = records_path.read_text(encoding="utf-8").splitlines()
        chunks = [json.loads(line) for line in lines]
        self._load_sparse(chunks)

    # --- query ---
    def search(
        self,
        query: str,
        k: int = 8,
        *,
        candidates: int = 30,
        exclude_high_sensitivity: bool = False,
        categories: list[str] | None = None,
        rrf_k: int = 60,
    ) -> list[RetrievedChunk]:
        """Hybrid search with reciprocal-rank fusion.

        ``exclude_high_sensitivity`` drops solution-key chunks (guardrail mode).
        ``categories`` optionally restricts to specific source categories.
        """
        self._ensure_sparse()
        dense_ids = self._dense_rank(query, candidates)  # semantic: embedding cosine NN
        sparse_ids = self._sparse_rank(query, candidates)  # lexical: BM25 keyword match
        fused = self._rrf(dense_ids, sparse_ids, rrf_k)  # combine both rankings into one order

        results: list[RetrievedChunk] = []
        for cid, score in fused:
            rec = self._records.get(cid)
            if rec is None:
                continue
            if exclude_high_sensitivity and rec.get("sensitivity") == "high":
                continue
            if categories and rec.get("category") not in categories:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text=rec["text"],
                    source_file=rec["source_file"],
                    category=rec["category"],
                    sensitivity=rec["sensitivity"],
                    citation=rec["citation"],
                    exercise_id=rec.get("exercise_id") or None,
                    score=score,
                )
            )
            if len(results) >= k:
                break
        return results

    def lexical_gate_report(self, query: str, *, min_fraction: float = 0.5) -> LexicalGateReport:
        """Detail behind :meth:`has_lexical_match` — the tokens, dropped stopwords, the content
        terms found in the corpus vocabulary, and the resulting fraction/pass (for the trace)."""
        try:
            self._ensure_sparse()
        except RuntimeError:
            return LexicalGateReport([], [], [], [], 0.0, False)
        tokens = _tokenize(query)
        content = [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]
        dropped = [t for t in tokens if t not in content]
        in_vocab = [t for t in content if t in self._vocab]
        fraction = (len(in_vocab) / len(content)) if content else 0.0
        return LexicalGateReport(
            tokens=tokens,
            content_tokens=content,
            dropped_stopwords=dropped,
            in_vocab=in_vocab,
            fraction=fraction,
            passed=bool(content) and fraction >= min_fraction,
        )

    def has_lexical_match(self, query: str, *, min_fraction: float = 0.5) -> bool:
        """True if a meaningful share of the query's content words occur in the corpus.

        A relevance gate for concept-less queries (workstream A): dense retrieval always returns
        nearest neighbours, so an off-topic question ("deploy Kubernetes") would otherwise look
        "answerable". We require at least ``min_fraction`` of the query's content tokens to share
        the corpus vocabulary — so on-topic phrasing ("verbose on mac" -> 2/2) passes, while a
        question with only an incidental word in common ("unladen swallow" -> 1/4) falls through
        to the "no match" nudge.
        """
        return self.lexical_gate_report(query, min_fraction=min_fraction).passed

    def search_with_trace(
        self,
        query: str,
        k: int = 8,
        *,
        candidates: int = 30,
        exclude_high_sensitivity: bool = False,
        categories: list[str] | None = None,
        rrf_k: int = 60,
    ) -> tuple[list[RetrievedChunk], RetrievalTrace]:
        """Like :meth:`search`, but also records dense/sparse/fused rankings + filter drops.

        Kept separate from the (byte-for-byte unchanged, hot-path) ``search`` so the default
        query stays fast; here we issue exactly one dense query (the *scored* variant) and walk
        the fused list the same way ``search`` does.
        """
        self._ensure_sparse()
        dense_scored = self._dense_rank_scored(query, candidates)
        sparse_scored = self._sparse_rank_scored(query, candidates)
        fused = self._rrf([c for c, _ in dense_scored], [c for c, _ in sparse_scored], rrf_k)

        results: list[RetrievedChunk] = []
        excluded: list[tuple[str, str]] = []
        for cid, score in fused:
            rec = self._records.get(cid)
            if rec is None:
                continue
            if exclude_high_sensitivity and rec.get("sensitivity") == "high":
                excluded.append((cid, "sensitivity"))
                continue
            if categories and rec.get("category") not in categories:
                excluded.append((cid, "category"))
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text=rec["text"],
                    source_file=rec["source_file"],
                    category=rec["category"],
                    sensitivity=rec["sensitivity"],
                    citation=rec["citation"],
                    exercise_id=rec.get("exercise_id") or None,
                    score=score,
                )
            )
            if len(results) >= k:
                break
        trace = RetrievalTrace(
            dense=dense_scored, sparse=sparse_scored, fused=fused, excluded=excluded
        )
        return results, trace

    def _dense_rank(self, query: str, n: int) -> list[str]:
        col = self._get_collection()
        qvec = self.embedder.encode_query(query)
        res = col.query(query_embeddings=[qvec], n_results=n)  # type: ignore[arg-type]
        ids = res.get("ids") or [[]]
        return list(ids[0])

    def _dense_rank_scored(self, query: str, n: int) -> list[tuple[str, float]]:
        """Dense ranking with similarity scores. Chroma returns cosine *distance*; we report
        ``1 - distance`` so higher = closer (labelled accordingly in the UI)."""
        col = self._get_collection()
        qvec = self.embedder.encode_query(query)
        res = col.query(
            query_embeddings=[qvec],  # type: ignore[arg-type]
            n_results=n,
            include=["distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out: list[tuple[str, float]] = []
        for i, cid in enumerate(ids):
            dist = dists[i] if i < len(dists) else None
            out.append((cid, (1.0 - float(dist)) if dist is not None else 0.0))
        return out

    def _sparse_rank(self, query: str, n: int) -> list[str]:
        assert self._bm25 is not None
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._bm25_ids, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [cid for cid, _ in ranked[:n]]

    def _sparse_rank_scored(self, query: str, n: int) -> list[tuple[str, float]]:
        assert self._bm25 is not None
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._bm25_ids, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [(cid, float(sc)) for cid, sc in ranked[:n]]

    @staticmethod
    def _rrf(dense: list[str], sparse: list[str], rrf_k: int) -> list[tuple[str, float]]:
        """Reciprocal-rank fusion: score = sum 1/(rrf_k + rank) across both rankings."""
        scores: dict[str, float] = {}
        for ranking in (dense, sparse):
            for rank, cid in enumerate(ranking):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
