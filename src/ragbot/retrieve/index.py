"""Hybrid index: dense (Chroma + local embeddings) + sparse (BM25), fused with RRF.

Chunks carry provenance metadata (source, category, sensitivity, citation, exercise id). The
retriever can exclude ``sensitivity=high`` chunks — the hook the guardrail uses in
assignment-help mode so solution keys never surface in an answer.
"""

from __future__ import annotations

import json
import re
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


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_file: str
    category: str
    sensitivity: str
    citation: str
    exercise_id: str | None = None
    score: float = 0.0


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
        self._bm25 = BM25Okapi([_tokenize(c["text"]) for c in chunks])

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
        dense_ids = self._dense_rank(query, candidates)
        sparse_ids = self._sparse_rank(query, candidates)
        fused = self._rrf(dense_ids, sparse_ids, rrf_k)

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

    def _dense_rank(self, query: str, n: int) -> list[str]:
        col = self._get_collection()
        qvec = self.embedder.encode_query(query)
        res = col.query(query_embeddings=[qvec], n_results=n)  # type: ignore[arg-type]
        ids = res.get("ids") or [[]]
        return list(ids[0])

    def _sparse_rank(self, query: str, n: int) -> list[str]:
        assert self._bm25 is not None
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._bm25_ids, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [cid for cid, _ in ranked[:n]]

    @staticmethod
    def _rrf(dense: list[str], sparse: list[str], rrf_k: int) -> list[tuple[str, float]]:
        """Reciprocal-rank fusion: score = sum 1/(rrf_k + rank) across both rankings."""
        scores: dict[str, float] = {}
        for ranking in (dense, sparse):
            for rank, cid in enumerate(ranking):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
