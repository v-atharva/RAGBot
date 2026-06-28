"""Generate ``misccontext/lecture_meta.json`` — the lecture_prefix -> {number, date, title} map.

This is workstream C0 of the retrieval/citation overhaul. The map is the single source of truth
for turning a lecture chunk into a human-friendly citation ("Lecture 17 · Feb 12, 2025 @ ...").

Date sourcing (NEVER fabricate — a wrong date is worse than no date):
  1. Parse a Month[ Day][ Year] embedded in the transcript filename when present
     (e.g. ``02_January_17_2025…`` -> 2025-01-17). Year defaults to the Spring-2025 term.
  2. Gaps where no date can be reliably parsed are emitted as ``null``; the UI then shows
     just "Lecture N" with no date. Fill such gaps by hand ONLY from an authoritative anchor
     (deadlines.json / course_structure.md), never by interpolation.

Run:  python scripts/build_lecture_meta.py   (writes misccontext/lecture_meta.json)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Make ``src/`` importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragbot.summaries.parse import load_all  # noqa: E402

TERM_YEAR = 2025  # Spring 2025 (2245); year defaults to this when absent from the filename.

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
# Month, optional day (with optional ordinal suffix), optional 4-digit year.
_DATE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:[ _]+(\d{1,2})(?:st|nd|rd|th)?)?"
    r"(?:[ _]+(\d{4}))?",
    re.IGNORECASE,
)
_PREFIX_RE = re.compile(r"^(\d+)")


def parse_date_from_name(name: str) -> str | None:
    """Return ISO ``YYYY-MM-DD`` parsed from a filename, or ``None`` if no day is present.

    Requires both a month and a day to commit to a date; a bare month name is too coarse.
    """
    m = _DATE_RE.search(name)
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    day = m.group(2)
    if not day:
        return None  # month-only -> not specific enough to commit a date
    year = int(m.group(3)) if m.group(3) else TERM_YEAR
    return f"{year:04d}-{month:02d}-{int(day):02d}"


def _deunderscore_stem(stem: str) -> str:
    no_prefix = re.sub(r"^\d+[ _]+", "", stem)
    return re.sub(r"[ _]+", " ", no_prefix).strip()


def build(transcripts_dir: str, summaries_dir: str) -> dict[str, dict[str, object]]:
    # Titles come from the parsed summaries (authoritative human titles); fall back to the stem.
    summaries = {s.lecture_prefix: s for s in load_all(summaries_dir, transcripts_dir)}

    out: dict[str, dict[str, object]] = {}
    for path in sorted(Path(transcripts_dir).glob("*.txt")):
        pm = _PREFIX_RE.match(path.stem)
        if not pm:
            continue
        prefix = pm.group(1)
        summary = summaries.get(prefix)
        title = summary.title if summary and summary.title else _deunderscore_stem(path.stem)
        out[prefix] = {
            "number": int(prefix),
            "date": parse_date_from_name(path.name),
            "title": title,
        }
    return out


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    meta = build(str(root / "transcripts"), str(root / "generated_summaries"))
    out_path = root / "misccontext" / "lecture_meta.json"
    out_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    dated = sum(1 for v in meta.values() if v["date"])
    print(f"Wrote {out_path} — {len(meta)} lectures, {dated} dated, {len(meta) - dated} null-date.")


if __name__ == "__main__":
    main()
