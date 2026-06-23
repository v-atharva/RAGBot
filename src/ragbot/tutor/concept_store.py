"""Runtime holder for the KAG-lite concept index.

Built once on API startup from the parsed lecture summaries (deterministic, sub-second over
43 summaries, no embedding cost) so it is always consistent with ``generated_summaries/``.
Holds both the concept entries and a ``lecture_prefix -> LectureSummary`` map, since the
reference builder needs the summaries' highlight topics for per-timestamp blurbs.

Query-side matching is intentionally more lenient than the index-build matcher: it allows a
trailing plural ("joins" -> "join") and treats the concept's own name as a match term, so
natural questions resolve even when the curated alias is singular.
"""

from __future__ import annotations

import re

from ragbot.config import Settings
from ragbot.summaries.concepts import CONCEPT_ALIASES, ConceptEntry, build_concept_index
from ragbot.summaries.models import LectureSummary
from ragbot.summaries.parse import load_all


def _compile_patterns(concept: str) -> list[re.Pattern[str]]:
    terms = set(CONCEPT_ALIASES.get(concept, [])) | {concept.lower()}
    patterns: list[re.Pattern[str]] = []
    for term in terms:
        cleaned = term.strip().lower()
        if not cleaned:
            continue
        # Word-boundaried, with an optional trailing plural 's'.
        patterns.append(re.compile(rf"(?<![a-z0-9]){re.escape(cleaned)}s?(?![a-z0-9])"))
    return patterns


class ConceptStore:
    def __init__(self, entries: list[ConceptEntry], summaries: list[LectureSummary]):
        self.entries = entries
        self._by_concept = {e.concept: e for e in entries}
        self._patterns = {e.concept: _compile_patterns(e.concept) for e in entries}
        self.summaries_by_prefix = {s.lecture_prefix: s for s in summaries}

    @classmethod
    def build(cls, settings: Settings) -> ConceptStore:
        summaries = load_all(settings.summaries_dir, settings.transcripts_dir)
        entries = build_concept_index(summaries, settings.deadlines_path)
        return cls(entries, summaries)

    def all_concepts(self) -> set[str]:
        return set(self._by_concept)

    def get(self, concept: str) -> ConceptEntry | None:
        return self._by_concept.get(concept)

    def match(self, text: str) -> list[ConceptEntry]:
        """Concepts named in ``text`` that appear in the corpus, most-mentioned first."""
        low = text.lower()
        matched = [
            self._by_concept[concept]
            for concept, pats in self._patterns.items()
            if any(p.search(low) for p in pats)
        ]
        matched.sort(key=lambda e: e.mention_count, reverse=True)
        return matched
