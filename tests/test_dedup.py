from ragbot.ingest.dedup import dedupe, normalize_text
from ragbot.ingest.models import Category, ExtractedDoc, SourceFile


def _doc(name: str, text: str, ext: str = ".pdf") -> ExtractedDoc:
    return ExtractedDoc(
        source=SourceFile(
            path=f"/x/{name}", name=name, ext=ext, size_bytes=len(text),
            category=Category.WORKED_EXAMPLE,
        ),
        text=text,
    )


def test_normalize_collapses_inline_ws_keeps_newlines():
    # NBSP + runs of spaces collapse to one space; newlines are preserved (structural).
    assert normalize_text("a\xa0\xa0b   c") == "a b c"
    assert normalize_text("line1  \n\n\n\nline2") == "line1\n\nline2"


def test_exact_content_duplicate_dropped():
    res = dedupe([_doc("a.pdf", "same body"), _doc("b.pdf", "same  body")])
    assert len(res.kept) == 1
    assert res.dropped and "duplicate" in res.dropped[0][1]


def test_older_version_dropped():
    res = dedupe([_doc("ex_version2.pdf", "v2 body"), _doc("ex_version3.pdf", "v3 body")])
    kept = {d.source.name for d in res.kept}
    assert kept == {"ex_version3.pdf"}


def test_same_version_different_type_both_kept():
    res = dedupe([_doc("ex_version3.pdf", "pdf body"), _doc("ex_version3.sql", "sql body", ".sql")])
    assert len(res.kept) == 2
    assert not res.dropped
