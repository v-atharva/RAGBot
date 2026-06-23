from pathlib import Path

from ragbot.summaries.parse import link_summaries, parse_summary

TABLE_MD = """# BCNF Lecture Summary

## Key Highlights (Chapters)

| Timestamp | Topic |
|-----------|-------|
| **00:00:36** | ⚠️ **BCNF is the only subjective normal form** |
| **00:00:47** | ✅ **The BCNF rule: every determinant is a candidate key** |

## 1. Body

- **00:05:00** — some body bullet that is NOT a highlight
"""

BULLET_MD = """# Functions Lecture Summary

## ⭐ Key Highlights (Chapters)

- **[00:00:26]** — Final exam logistics
- **[00:02:22]** — ⚠️ Aggregate functions overview

---

## Body
- **[00:09:00]** — body bullet, not a highlight
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_table_highlights(tmp_path):
    s = parse_summary(_write(tmp_path, "24_BCNF.md", TABLE_MD))
    assert len(s.highlights) == 2
    assert s.highlights[0].timestamp == "00:00:36"
    assert s.highlights[0].is_warning is True
    assert s.highlights[1].is_key is True
    assert s.lecture_prefix == "24"


def test_parse_bullet_highlights_section_scoped(tmp_path):
    s = parse_summary(_write(tmp_path, "40_Functions.md", BULLET_MD))
    # Two highlights in the section; the body bullet must NOT be captured.
    assert len(s.highlights) == 2
    assert s.highlights[1].is_warning is True
    assert "00:09:00" not in {h.timestamp for h in s.highlights}


def test_all_timestamps_collected(tmp_path):
    s = parse_summary(_write(tmp_path, "01_X.md", BULLET_MD))
    assert "00:09:00" in s.timestamps  # body timestamps still collected for navigation


def test_link_by_prefix(tmp_path):
    sdir = tmp_path / "summaries"
    tdir = tmp_path / "transcripts"
    sdir.mkdir()
    tdir.mkdir()
    (sdir / "24_BCNF_summary.md").write_text("# x", encoding="utf-8")
    (tdir / "24_BCNF_-_Last.txt").write_text("body", encoding="utf-8")
    (sdir / "99_orphan.md").write_text("# y", encoding="utf-8")
    mapping = link_summaries(sdir, tdir)
    assert mapping[str(sdir / "24_BCNF_summary.md")].endswith("24_BCNF_-_Last.txt")
    assert mapping[str(sdir / "99_orphan.md")] == ""
