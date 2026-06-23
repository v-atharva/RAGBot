"""Stage 4 — split extracted documents into retrievable, citable chunks.

Chunking is source-aware:
- PDFs/docs: page-aware windows, cited by page number.
- Transcripts: timestamp-windowed, cited by the first timestamp in the window.
- SQL: kept whole (statement-aware splitting would fragment context); cited by filename.

Every chunk carries provenance (source, category, sensitivity, citation) so retrieval can
filter on sensitivity and the tutor can cite precisely.
"""

from __future__ import annotations

import re

from .models import Category, Chunk, ExtractedDoc, SourceFile

# Target chunk size in characters (rough proxy for tokens; embeddings handle the rest).
TARGET_CHARS = 1200
OVERLAP_CHARS = 150

_TS_LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$")


def _citation_label(category: Category, name: str, locator: str) -> str:
    stem = name.rsplit(".", 1)[0]
    if category == Category.LECTURE_TRANSCRIPT:
        return f"[{stem} @ {locator}]"
    if category in (Category.TEXTBOOK_CHAPTER, Category.LECTURE_SLIDES):
        return f"[{stem} {locator}]"
    return f"[{stem}]"


def _window(
    text: str, size: int = TARGET_CHARS, overlap: int = OVERLAP_CHARS
) -> list[tuple[int, int]]:
    """Return (start, end) char windows over text, breaking on a boundary where possible."""
    spans: list[tuple[int, int]] = []
    n = len(text)
    if n == 0:
        return spans
    start = 0
    while start < n:
        end = min(start + size, n)
        if end < n:
            # Prefer to break at a paragraph or sentence boundary near the window end.
            window = text[start:end]
            for sep in ("\n\n", ". ", "\n", " "):
                idx = window.rfind(sep)
                if idx > size * 0.5:
                    end = start + idx + len(sep)
                    break
        spans.append((start, end))
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return spans


def _page_for_offset(doc: ExtractedDoc, offset: int) -> str:
    """Return the page/segment label whose span contains the offset (best effort)."""
    label = doc.pages[0].label if doc.pages else "p.1"
    for span in doc.pages:
        if span.start <= offset:
            label = span.label
        else:
            break
    return label


def chunk_document(doc: ExtractedDoc) -> list[Chunk]:
    src = doc.source
    if not doc.text.strip():
        return []
    if src.category == Category.LECTURE_TRANSCRIPT:
        return _chunk_transcript(doc)
    if src.category == Category.SQL_SCRIPT:
        return [_make_chunk(src, 0, doc.text, "[" + src.name.rsplit(".", 1)[0] + "]")]
    return _chunk_paged(doc)


def _make_chunk(src: SourceFile, idx: int, text: str, citation: str) -> Chunk:
    return Chunk(
        chunk_id=f"{src.name}#{idx}",
        text=text.strip(),
        source_file=src.name,
        category=src.category,
        sensitivity=src.sensitivity,
        citation=citation,
        exercise_id=src.exercise_id,
    )


def _chunk_paged(doc: ExtractedDoc) -> list[Chunk]:
    chunks: list[Chunk] = []
    for i, (start, end) in enumerate(_window(doc.text)):
        page = _page_for_offset(doc, start)
        citation = _citation_label(doc.source.category, doc.source.name, page)
        chunks.append(_make_chunk(doc.source, i, doc.text[start:end], citation))
    return chunks


def _chunk_transcript(doc: ExtractedDoc) -> list[Chunk]:
    """Group timestamped utterances into ~TARGET_CHARS windows; cite the first timestamp."""
    chunks: list[Chunk] = []
    cur: list[str] = []
    cur_len = 0
    cur_ts: str | None = None
    idx = 0

    def flush() -> None:
        nonlocal cur, cur_len, cur_ts, idx
        if not cur:
            return
        ts = cur_ts or "00:00:00"
        citation = _citation_label(Category.LECTURE_TRANSCRIPT, doc.source.name, ts)
        chunks.append(_make_chunk(doc.source, idx, "\n".join(cur), citation))
        idx += 1
        cur, cur_len, cur_ts = [], 0, None

    for line in doc.text.splitlines():
        m = _TS_LINE_RE.match(line.strip())
        if m:
            ts, speaker, utterance = m.group(1), m.group(2).strip(), m.group(3).strip()
            if cur_ts is None:
                cur_ts = ts
            piece = f"{speaker}: {utterance}"
        else:
            piece = line.strip()
        if not piece:
            continue
        cur.append(piece)
        cur_len += len(piece)
        if cur_len >= TARGET_CHARS:
            flush()
    flush()
    return chunks
