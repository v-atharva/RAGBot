"""Loader for ``misccontext/lecture_meta.json`` (workstream C0).

Maps a lecture's numeric prefix -> {number, date, title}. Built offline by
``scripts/build_lecture_meta.py`` so it is committed, deterministic, and reviewable. The
citation formatter (:mod:`ragbot.tutor.citations`) reads this to render human-friendly,
dated lecture labels. ``date`` is ISO ``YYYY-MM-DD`` or ``None`` when it could not be
reliably sourced — callers must tolerate a missing date.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DEFAULT_META_PATH = "misccontext/lecture_meta.json"


class LectureMeta(BaseModel):
    lecture_prefix: str
    number: int
    date: str | None = None  # ISO YYYY-MM-DD, or None when unknown
    title: str = ""


@lru_cache(maxsize=4)
def load_lecture_meta(path: str = DEFAULT_META_PATH) -> dict[str, LectureMeta]:
    """Load the prefix -> LectureMeta map (cached). Missing file -> empty map (degrades safely)."""
    p = Path(path)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, LectureMeta] = {}
    for prefix, v in raw.items():
        out[prefix] = LectureMeta(
            lecture_prefix=prefix,
            number=int(v.get("number", prefix) if str(v.get("number", "")).isdigit() else 0),
            date=v.get("date"),
            title=v.get("title", ""),
        )
    return out


def format_date(iso: str | None) -> str | None:
    """ISO ``2025-02-12`` -> ``Feb 12, 2025``; ``None``/unparseable -> ``None``."""
    if not iso:
        return None
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return None
