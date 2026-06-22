"""Stage 3 — normalize extracted text and drop duplicates / stale versions.

Two kinds of duplication in this corpus:
1. Exact/near-exact content duplicates (same file downloaded twice, trivial re-exports).
2. Versioned files where only the newest matters (``example1_version2`` vs ``_version3``).

Every exclusion is recorded so the manifest stays auditable.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from .models import ExtractedDoc

# Collapse runs of spaces/tabs but PRESERVE newlines — line structure is meaningful for
# transcripts ([HH:MM:SS] per line) and aids paragraph-aware chunking elsewhere.
_INLINE_WS_RE = re.compile(r"[^\S\n]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_VERSION_RE = re.compile(r"v(?:ersion)?\s*[_-]?\s*(\d+)", re.I)


class DedupResult:
    def __init__(self, kept: list[ExtractedDoc], dropped: list[tuple[str, str]]):
        self.kept = kept
        self.dropped = dropped  # (filename, reason)


def normalize_text(text: str) -> str:
    """Unicode-normalize, collapse whitespace, replace non-breaking spaces.

    PDF extraction (esp. these slides) is full of NBSP and soft hyphens; normalizing makes
    both dedup hashing and downstream embedding cleaner.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xad", "")  # soft hyphen
    text = _INLINE_WS_RE.sub(" ", text)  # collapse spaces/tabs, keep newlines
    text = _BLANK_LINES_RE.sub("\n\n", text)  # cap consecutive blank lines
    # Trim trailing spaces on each line.
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def _content_key(text: str) -> str:
    return hashlib.sha256(normalize_text(text).lower().encode("utf-8")).hexdigest()


def _version_stem(name: str) -> tuple[str, int]:
    """Return a (stem-without-version, version-number) pair. Files sharing a stem are
    versions of the same material; the highest version wins."""
    base = name.rsplit(".", 1)[0]
    m = _VERSION_RE.search(base)
    version = int(m.group(1)) if m else 0
    stem = _VERSION_RE.sub("", base)
    stem = re.sub(r"[\s_-]+", "", stem).lower()
    return stem, version


def dedupe(docs: list[ExtractedDoc]) -> DedupResult:
    kept: list[ExtractedDoc] = []
    dropped: list[tuple[str, str]] = []

    # Pass 1: exact content dedup (keep first occurrence).
    seen_content: dict[str, str] = {}
    after_content: list[ExtractedDoc] = []
    for doc in docs:
        if not doc.text.strip():
            after_content.append(doc)
            continue
        key = _content_key(doc.text)
        if key in seen_content:
            dropped.append(
                (doc.source.name, f"exact content duplicate of {seen_content[key]}")
            )
            continue
        seen_content[key] = doc.source.name
        after_content.append(doc)

    # Pass 2: versioned-file dedup (keep highest version per stem). Only applied when more
    # than one file shares a stem AND at least one carries an explicit version marker.
    by_stem: dict[str, list[ExtractedDoc]] = {}
    for doc in after_content:
        stem, _ = _version_stem(doc.source.name)
        by_stem.setdefault(stem, []).append(doc)

    for group in by_stem.values():
        if len(group) == 1:
            kept.append(group[0])
            continue
        versioned = [(_version_stem(d.source.name)[1], d) for d in group]
        has_explicit = any(v > 0 for v, _ in versioned)
        if not has_explicit:
            # Same stem but no version markers (e.g. different file types) — keep all.
            kept.extend(group)
            continue
        best_v = max(v for v, _ in versioned)
        # Keep ALL files at the highest version (a .pdf and its .sql at v3 are both wanted);
        # only drop files whose version is strictly older.
        winners = [d for v, d in versioned if v == best_v]
        winner_names = ", ".join(sorted(d.source.name for d in winners))
        for v, d in versioned:
            if v == best_v:
                kept.append(d)
            else:
                dropped.append(
                    (d.source.name, f"superseded version (v{v} < v{best_v}: '{winner_names}')")
                )

    # Normalize text in place on kept docs.
    for doc in kept:
        doc.text = normalize_text(doc.text)

    kept.sort(key=lambda d: d.source.name)
    return DedupResult(kept=kept, dropped=dropped)
