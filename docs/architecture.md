# Architecture: Tiered CAG → RAG → KAG-lite

RAGBot answers a wide range of query types over a **small, static, finite** course corpus
(43 lecture transcripts + 43 generated lecture summaries + textbook chapters, slides, SQL
scripts, diagrams, assignment prompts, and structured course metadata). Different query types
need different machinery; routing them is what makes the tutor feel intelligent rather than a
single retrieval pipe.

The corpus being small and static is the decisive fact: it makes **Cache-Augmented Generation
(CAG)** viable, which most RAG systems cannot use. We combine three complementary layers.

## The three layers

### Tier 1 — CAG: the always-on comprehension layer
The 43 lecture summaries plus structured course metadata (`deadlines.json`, curriculum arc)
fit comfortably in a long-context window. We preload them once and reuse the model's KV-cache
across queries, so the model always "knows" the whole course at a high level.

- **Handles:** overview, "what was covered", timeline/logistics, cross-lecture framing.
- **Why summaries:** they are comprehensive, compressed, and timestamp-anchored — the ideal
  cacheable artifact. They give the model the *gist* so it answers with understanding, not just
  stitched fragments.
- **Local-model advantage:** with a local model we control the KV-cache directly and can
  snapshot/reload it from disk — the full CAG benefit, stronger than a hosted API's
  vendor-managed prompt caching.

### Tier 2 — RAG: the precision grounding layer
For specific, factual, or deep-dive questions we retrieve full transcript and document chunks
and cite them exactly. This is where **citation integrity** lives.

- **Handles:** "what exactly did he say about delete anomalies in BCNF?" → real
  `[lecture 24 @ 00:08:35]` chunk.
- **Routing inside RAG:** hybrid (BM25 + dense + RRF) for flat transcripts; reasoning-tree
  retrieval for hierarchical PDFs (textbook/slides).
- **Hard rule:** summaries (Tier 1) FRAME answers; they are never cited as the authority for a
  fact. The source of record for any factual claim is always a Tier-2 chunk. This keeps
  summarization from corrupting citations.

### Tier 3 — KAG-lite: the connective-tissue layer
Not a full knowledge graph (over-engineering for a linear curriculum). Instead a lightweight
structured index: `concept → {lectures, timestamps, assignments, textbook pages}`, built cheaply
from the summary highlight tables + `deadlines.json`.

- **Handles:** multi-hop course questions ("which assignments test normalization, and where was
  each concept taught?") and powers timeline-aware suggestions.
- **Why lite:** linear course = sparse entity web; a graph DB's cost/fragility isn't justified.
  A concept→location map captures the useful multi-hop structure at a fraction of the effort.

## Query routing

```
query → classify intent
  ├─ overview / timeline / "what was covered"  → CAG (summaries in cached context), no retrieval
  ├─ specific / factual / deep-dive            → RAG (retrieve full chunks, cite exactly)
  ├─ multi-hop / "connect across lectures"     → KAG-lite index → gather → RAG to ground
  └─ assignment-related                        → guardrail (CAG knows the map; RAG cites where
                                                  to look, never the answer)
```

## Model & serving

- **Model:** Qwen3.5-9B-Instruct (`qwen3.5:9b`) — 262K context, strong on structured/technical
  content, runs quantized locally on ~16 GB. No per-call cost; offline; reproducible from clone.
  Selected over the 27B/35B tiers because the CAG layer needs a large KV-cache headroom that the
  9B leaves room for on a 16 GB machine. It is a *thinking* model; the reasoning trace is disabled
  at call time (`think: false`) so the budget goes to the answer.
- **Serving:** Ollama for development and demo. A thin, provider-agnostic LLM-client interface
  (`src/ragbot/tutor/llm.py`) keeps the door open for a hosted backend later — set
  `LLM_PROVIDER=anthropic` + `LLM_API_KEY` to swap with no code changes (and vLLM later for
  better KV-cache control / true CAG snapshots).

## On fine-tuning (deliberately deferred)

Fine-tuning teaches **behavior/style, not facts**. Baking course content into weights would make
it un-citable and prone to confident hallucination — directly against this project's grounding
premise — and 43 lectures is far too little data to learn knowledge without overfitting.

Therefore: **no fine-tuning for knowledge.** A *behavior-only* LoRA — teaching the Socratic,
never-give-the-answer tutoring style and the citation format — is a legitimate, optional Tier-2
enhancement and a documented stretch goal. The system works with an off-the-shelf instruct model
from day one; the LoRA is an optimization, not a foundation.

## Why this is the strongest approach here

- **CAG** exploits the rare property that our corpus fits in context → fast, cheap, always-on
  comprehension.
- **RAG** preserves exact, faithful, citable grounding for the answers that matter.
- **KAG-lite** adds multi-hop reasoning without graph-database overhead.
- Routing matches each query class to the right layer, covering a genuinely wide range of
  queries while protecting citation integrity end-to-end.
