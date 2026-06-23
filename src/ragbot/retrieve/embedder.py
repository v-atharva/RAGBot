"""Local embedding model wrapper (BGE/GTE via sentence-transformers).

Lazy-loaded so importing the module is cheap and offline-friendly; the model downloads on
first use and is cached by sentence-transformers. No external embedding service.
"""

from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")


@lru_cache(maxsize=2)
def _load(model_name: str):  # type: ignore[no-untyped-def]
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class Embedder:
    """Encodes text to dense vectors. BGE models recommend a query instruction prefix for
    retrieval queries (not for documents), which materially improves recall."""

    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        model = _load(self.model_name)
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    def encode_query(self, text: str) -> list[float]:
        model = _load(self.model_name)
        prefixed = self.QUERY_PREFIX + text if "bge" in self.model_name.lower() else text
        vec = model.encode([prefixed], normalize_embeddings=True, show_progress_bar=False)[0]
        return list(vec.tolist())
