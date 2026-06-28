"""FastAPI application for the RAGBot tutor.

Builds shared singletons on startup (concept store, hybrid index, LLM client) and exposes a
single ``POST /query`` plus a ``GET /health``. CORS is open for local development so the
Next.js dev server (http://localhost:3000) can call it directly.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ragbot.config import Settings, get_settings
from ragbot.retrieve.index import HybridIndex
from ragbot.tutor.concept_store import ConceptStore
from ragbot.tutor.llm import LLMError, get_llm
from ragbot.tutor.schemas import (
    CorpusExplain,
    ModelInfo,
    ModelStatus,
    QueryRequest,
    QueryResponse,
)
from ragbot.tutor.service import answer

# Cache the parsed corpus summary, keyed by the summary file's mtime.
_corpus_cache: dict[str, tuple[float, CorpusExplain]] = {}


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


# --- Ollama model lifecycle (free/reclaim local RAM) -------------------------------------


def _require_ollama(settings: Settings) -> None:
    if settings.llm_provider != "ollama":
        raise HTTPException(
            status_code=409, detail="Model controls are only available for the Ollama provider."
        )


def _ps_models(base_url: str, timeout: float = 3.0) -> list[dict[str, Any]]:
    """Models currently resident in Ollama (GET /api/ps)."""
    resp = httpx.get(f"{base_url.rstrip('/')}/api/ps", timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("models") or []


def _matches(m: dict[str, Any], model_name: str) -> bool:
    return model_name in (m.get("model"), m.get("name"))


def _model_status(settings: Settings, *, freed_bytes: int | None = None) -> ModelStatus:
    """Build the status from /api/ps; on connection error return loaded=false + error (HTTP 200)."""
    try:
        models = _ps_models(settings.ollama_base_url)
    except httpx.HTTPError as exc:
        return ModelStatus(provider=settings.llm_provider, loaded=False, error=str(exc))
    infos = [
        ModelInfo(
            name=str(m.get("name") or m.get("model") or ""),
            size=int(m.get("size") or 0),
            size_vram=int(m.get("size_vram") or 0),
        )
        for m in models
    ]
    loaded = any(_matches(m, settings.ollama_model) for m in models)
    return ModelStatus(
        provider=settings.llm_provider, loaded=loaded, models=infos, freed_bytes=freed_bytes
    )


@app.get("/model/status", response_model=ModelStatus)
def model_status() -> ModelStatus:
    settings = app.state.settings
    _require_ollama(settings)
    return _model_status(settings)


@app.post("/model/unload", response_model=ModelStatus)
def model_unload() -> ModelStatus:
    settings = app.state.settings
    _require_ollama(settings)
    freed = 0
    try:
        for m in _ps_models(settings.ollama_base_url):
            if _matches(m, settings.ollama_model):
                freed = int(m.get("size_vram") or m.get("size") or 0)
                break
        # keep_alive:0 evicts the model from memory after this (no-op) request.
        httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={"model": settings.ollama_model, "keep_alive": 0},
            timeout=30.0,
        ).raise_for_status()
        # /api/ps is eventually-consistent — poll briefly so the reported status is accurate.
        for _ in range(5):
            resident = _ps_models(settings.ollama_base_url)
            if not any(_matches(m, settings.ollama_model) for m in resident):
                break
            time.sleep(0.3)
    except httpx.HTTPError as exc:
        return ModelStatus(provider=settings.llm_provider, loaded=False, error=str(exc))
    return _model_status(settings, freed_bytes=freed)


@app.post("/model/load", response_model=ModelStatus)
def model_load() -> ModelStatus:
    settings = app.state.settings
    _require_ollama(settings)
    try:
        # Warm-up: an empty generate loads the model and sets the keep-alive window.
        httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": "",
                "keep_alive": settings.ollama_keep_alive,
            },
            timeout=settings.request_timeout,
        ).raise_for_status()
    except httpx.HTTPError as exc:
        return ModelStatus(provider=settings.llm_provider, loaded=False, error=str(exc))
    return _model_status(settings)


@app.get("/corpus/explain", response_model=CorpusExplain)
def corpus_explain() -> CorpusExplain:
    """Ingestion summary for the Inspector's corpus explainer (cached by file mtime)."""
    settings = app.state.settings
    summary_path = f"{settings.index_dir}/ingest_summary.json"
    manifest_path = f"{settings.index_dir}/ingest_manifest.json"
    try:
        mtime = os.path.getmtime(summary_path)
    except OSError as exc:
        return CorpusExplain(error=str(exc))
    cached = _corpus_cache.get(summary_path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(summary_path, encoding="utf-8") as fh:
            s = json.load(fh)
        by_format: dict[str, int] = {}
        try:
            with open(manifest_path, encoding="utf-8") as fh:
                for rec in json.load(fh):
                    ext = str(rec.get("ext") or "?")
                    by_format[ext] = by_format.get(ext, 0) + 1
        except OSError:
            pass
        ce = CorpusExplain(
            files_seen=s.get("files_seen", 0),
            transcripts_loaded=s.get("transcripts_loaded", 0),
            kept_docs=s.get("kept_docs", 0),
            chunks=s.get("chunks", 0),
            chunks_by_category=s.get("chunks_by_category") or {},
            high_sensitivity_chunks=s.get("high_sensitivity_chunks", 0),
            high_sensitivity_sources=s.get("high_sensitivity_sources") or [],
            dropped_classify=s.get("dropped_classify", 0),
            dropped_dedup=s.get("dropped_dedup", 0),
            by_format=by_format,
        )
    except (OSError, ValueError) as exc:
        return CorpusExplain(error=str(exc))
    _corpus_cache[summary_path] = (mtime, ce)
    return ce


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    try:
        # Single entry point: hand the request + startup singletons to the orchestrator.
        return answer(
            req,
            store=app.state.store,
            index=app.state.index,
            llm=app.state.llm,
            settings=app.state.settings,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
