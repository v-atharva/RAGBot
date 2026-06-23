"""FastAPI application for the RAGBot tutor.

Builds shared singletons on startup (concept store, hybrid index, LLM client) and exposes a
single ``POST /query`` plus a ``GET /health``. CORS is open for local development so the
Next.js dev server (http://localhost:3000) can call it directly.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ragbot.config import get_settings
from ragbot.retrieve.index import HybridIndex
from ragbot.tutor.concept_store import ConceptStore
from ragbot.tutor.llm import LLMError, get_llm
from ragbot.tutor.schemas import QueryRequest, QueryResponse
from ragbot.tutor.service import answer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.store = ConceptStore.build(settings)
    app.state.index = HybridIndex(persist_dir=settings.chroma_dir)
    app.state.llm = get_llm(settings)
    yield


app = FastAPI(title="RAGBot Tutor", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    settings = app.state.settings
    index_ready = os.path.exists(f"{settings.chroma_dir}/records.jsonl")
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.active_model,
        "index_ready": index_ready,
        "concepts": len(app.state.store.entries),
    }


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    try:
        return answer(
            req,
            store=app.state.store,
            index=app.state.index,
            llm=app.state.llm,
            settings=app.state.settings,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
