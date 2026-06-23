"""KAG-lite concept index.

A lightweight knowledge layer (not a graph database): maps each course concept to where it
appears — lectures, timestamps, and related assignments. Built deterministically from parsed
summary highlights + ``deadlines.json``, so it is explainable and reproducible. Powers multi-hop
queries ("which assignments test normalization, and where was each concept taught?") and feeds
timeline-aware suggestions.

Concepts are a curated taxonomy with aliases, grounded in the actual frequency of terms in the
corpus (joins, keys, normal forms, constraints, aggregates, etc.).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from .models import LectureSummary

# Concept -> alias phrases (lowercased substring match). Ordered roughly by curriculum.
CONCEPT_ALIASES: dict[str, list[str]] = {
    "ER diagrams": ["er diagram", "entity relationship", "crow", "crow's foot", "crowfoot"],
    "entities & relationships": ["entity", "relationship", "cardinality", "degree of a relation"],
    "primary keys": ["primary key", " pk ", "composite key"],
    "foreign keys": ["foreign key", " fk ", "referential integrity"],
    "candidate keys": ["candidate key", "determinant"],
    "DDL/DML/DCL": ["ddl", "dml", "dcl", "data definition", "data manipulation"],
    "constraints": ["constraint", "not null", "unique", "check constraint", "default"],
    "ALTER statements": ["alter", "alter table"],
    "normalization": ["normalization", "normal form", "normalize"],
    "1NF": ["1nf", "first normal form"],
    "2NF": ["2nf", "second normal form", "partial dependency"],
    "3NF": ["3nf", "third normal form", "transitive dependency"],
    "BCNF": ["bcnf", "boyce", "boyce-codd", "boyce-cobb"],
    "functional dependencies": ["functional dependency", "functional dependencies"],
    "SELECT queries": ["select statement", " select ", "where clause"],
    "joins": ["join", "inner join", "outer join", "self-join", "self join", "multiple table"],
    "set operations": ["union", "intersection", "difference", "relational algebra"],
    "aggregate functions": ["aggregate", "count", "sum", "avg", "group by", "having"],
    "subqueries": ["subquery", "sub-query", "nested query"],
    "functions": ["function", "mod ", "stored function"],
    "stored procedures": ["stored procedure", "procedure"],
    "transactions": ["transaction", "commit", "rollback", "acid"],
    "DCL & security": ["dcl", "grant", "revoke", "privilege"],
    "subclass/superclass": ["subclass", "superclass", "supertype", "subtype", "inheritance"],
    "weak/strong entities": ["weak entity", "strong entity", "weak table", "strong table"],
    "forward engineering": ["forward engineering", "workbench", "reverse engineering"],
    "backup & restore": ["backup", "restore", "mysqldump"],
    "INSERT/UPDATE/DELETE": ["insert", "update", "delete", "crud"],
}


class ConceptLocation(BaseModel):
    lecture_prefix: str
    lecture_title: str
    transcript_file: str | None
    timestamps: list[str] = Field(default_factory=list)


class ConceptEntry(BaseModel):
    concept: str
    locations: list[ConceptLocation] = Field(default_factory=list)
    related_assignments: list[str] = Field(default_factory=list)
    mention_count: int = 0


# Cache compiled word-boundary patterns per alias for whole-word matching (avoids "count"
# matching "account", " select " matching mid-word, etc.).
_ALIAS_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    concept: [re.compile(rf"(?<![a-z0-9]){re.escape(a.strip())}(?![a-z0-9])") for a in aliases]
    for concept, aliases in CONCEPT_ALIASES.items()
}


def _match_concepts(text: str) -> set[str]:
    low = text.lower()
    return {c for c, pats in _ALIAS_PATTERNS.items() if any(p.search(low) for p in pats)}


def build_concept_index(
    summaries: list[LectureSummary],
    deadlines_path: str | Path | None = "misccontext/deadlines.json",
) -> list[ConceptEntry]:
    """Build the concept -> locations/assignments index."""
    entries: dict[str, ConceptEntry] = {
        c: ConceptEntry(concept=c) for c in CONCEPT_ALIASES
    }

    for summary in summaries:
        # Per-lecture: which concepts appear, and at which highlight timestamps.
        lecture_concepts: dict[str, list[str]] = {}
        for h in summary.highlights:
            for c in _match_concepts(h.topic):
                lecture_concepts.setdefault(c, []).append(h.timestamp)
        # Also catch concepts named in the title/body even without a highlight.
        for c in _match_concepts(summary.title):
            lecture_concepts.setdefault(c, [])

        for concept, timestamps in lecture_concepts.items():
            entry = entries[concept]
            entry.mention_count += max(len(timestamps), 1)
            entry.locations.append(
                ConceptLocation(
                    lecture_prefix=summary.lecture_prefix,
                    lecture_title=summary.title,
                    transcript_file=summary.transcript_file,
                    timestamps=sorted(set(timestamps)),
                )
            )

    _attach_assignments(entries, deadlines_path)
    # Drop concepts that never appeared; sort by frequency.
    result = [e for e in entries.values() if e.locations]
    result.sort(key=lambda e: e.mention_count, reverse=True)
    return result


def _attach_assignments(
    entries: dict[str, ConceptEntry], deadlines_path: str | Path | None
) -> None:
    """Link concepts to assignments whose lecture coverage overlaps.

    Assignment topics aren't structured in deadlines.json, so we use a simple curriculum-aware
    heuristic: an assignment that falls in the same lecture window as a concept's coverage is
    'related'. This is intentionally lightweight; the lecture/timestamp links are the precise
    part of the index.
    """
    if not deadlines_path or not Path(deadlines_path).exists():
        return
    data = json.loads(Path(deadlines_path).read_text(encoding="utf-8"))
    notes = []
    for item in data.get("homework", []) + data.get("practice_exercises", []):
        note = item.get("note", "")
        if note:
            notes.append((item["id"], note.lower()))
    for entry in entries.values():
        pats = _ALIAS_PATTERNS[entry.concept]
        related = [aid for aid, note in notes if any(p.search(note) for p in pats)]
        if related:
            entry.related_assignments = sorted(set(related))


def write_concept_index(entries: list[ConceptEntry], out_path: str | Path) -> None:
    payload = [e.model_dump(mode="json") for e in entries]
    Path(out_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
