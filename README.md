# RAGBot — A Grounded Course Tutor with Guardrails

A retrieval-augmented tutor built over a full semester of a real university database course
(lecture transcripts, textbook chapters, slide decks, assignments, and the course
calendar). It answers questions grounded in those sources with exact citations — and, crucially,
**guides students through assignments without ever handing them the solution.**

This is deliberately *not* another "chat with your PDF" demo. The engineering centers on three
problems that generic RAG ignores:

1. **Guardrails.** For assignment-related questions the tutor returns *where to look*
   (lecture timestamp, textbook page), analogies, and Socratic prompts — never the literal
   answer. This is enforced and measured as an adversarial evaluation (answer-leak rate).
2. **Routed retrieval.** Flat, keyword-rich lecture transcripts use hybrid retrieval
   (BM25 + dense + reciprocal-rank fusion); hierarchical textbook/slide PDFs use a reasoning-based
   tree retriever. Each source type is routed to the method that wins for it, and the choice is
   backed by an evaluation table rather than asserted.
3. **Source-sensitivity tagging.** Solution keys and exam-review documents are tagged at ingest
   and excluded from retrieval in assignment-help mode, so the system cannot undermine its own
   guardrail by surfacing an answer key.

## Features

- **Two modes**
  - *Lecture-only* — strictly answers from lecture transcripts, cited to `[lecture N @ 00:12:34]`.
  - *Course-wide* — synthesizes scattered information across transcripts, textbook, slides, and
    the course calendar, and collates it into a single grounded answer.
- **Citations everywhere** — every claim resolves to a lecture timestamp or a textbook page number.
- **Timeline-aware suggestions** — fresh-chat prompts adapt to where the course is in time
  ("the midterm in 4 days covers normalization — revise 2NF/3NF?"), driven by the course
  schedule and an injectable clock.
- **Context-aware nudges** — mid-conversation, the tutor proposes next directions that deepen
  understanding of the current topic.
- **Multi-format ingestion** — a pipeline that classifies, extracts, de-duplicates, and chunks
  13 source formats (PDF, DOC/DOCX, SQL, TXT, HTML, spreadsheets, and image-only diagrams).

## Architecture

```
Ingestion (offline)
  raw course materials ─► classify ─► extract (per-format) ─► normalize + dedup ─► chunk ─► index
                                                                                   │
                                          transcripts → Chroma (local embeddings) + BM25
                                          textbook/slide PDFs → reasoning tree index
                                          every chunk tagged: {source, category, sensitivity, page|timestamp}

Query path (online)
  query ─► classify mode ─► query optimization (cached) ─► route + retrieve ─► fuse + cite
        ─► assignment detector → guardrailed response when the query maps to a known exercise
        ─► answer synthesis with citations (response caching)
        ─► suggestion generator (timeline-aware | context-aware)

Evaluation (offline)
  retrieval: hit-rate@k, MRR (hybrid vs. tree, per source type)
  guardrail: adversarial answer-leak rate
  faithfulness: groundedness judging
```

## Tech stack

- **Backend:** Python 3.11, FastAPI, Pydantic
- **Retrieval:** Chroma + `rank_bm25` + reciprocal-rank fusion; reasoning-based tree retrieval for PDFs
- **Embeddings:** local `sentence-transformers` (BGE/GTE) — no external embedding service
- **Generation:** LLM-backed answer synthesis with prompt + response caching
- **Frontend:** React / Next.js (two-tab UI with citation chips and suggestion cards)
- **Quality:** ruff, mypy, pytest; evaluation harness run in CI on every push

## Getting started

```bash
# 1. Install dependencies
make install

# 2. Provide course materials locally (not committed) under misccontext/ and transcripts/,
#    plus an LLM API key in .env (see .env.example)

# 3. Build the index
make ingest

# 4. Run the evaluation suites
make eval

# 5. Start the API + UI
make run
```

> **Note on data.** The course materials (transcripts, textbook chapters, assignment prompts)
> are owned by the course and are intentionally **not** committed — see `.gitignore`. The
> repository contains the pipeline, retrieval, guardrail, evaluation, and application code; point
> it at your own course corpus to reproduce the system.

## Repository layout

```
src/
  ingest/        multi-format extraction, dedup, chunking, indexing
  retrieve/      hybrid + tree retrieval, fusion, query optimization & caching
  tutor/         mode classification, guardrail, answer synthesis, suggestions
  api/           FastAPI app
  eval/          retrieval / guardrail / faithfulness harnesses
web/             Next.js frontend
tests/           unit + integration tests
```

## Status

Active development. See the issue tracker for the current roadmap.
