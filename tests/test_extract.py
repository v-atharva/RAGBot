from pathlib import Path

from ragbot.ingest.extract import extract
from ragbot.ingest.models import Category, Sensitivity, SourceFile


def _src(tmp_path: Path, name: str, content: str, ext: str) -> SourceFile:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return SourceFile(
        path=str(p),
        name=name,
        ext=ext,
        size_bytes=p.stat().st_size,
        category=Category.SQL_SCRIPT,
        sensitivity=Sensitivity.NORMAL,
    )


def test_plaintext_sql(tmp_path):
    sf = _src(tmp_path, "q.sql", "SELECT * FROM t;", ".sql")
    doc = extract(sf)
    assert "SELECT" in doc.text
    assert doc.extractor == "read"
    assert doc.pages[0].label == "sql"


def test_html_strips_tags(tmp_path):
    html = "<html><body><p>Hello</p><script>x()</script></body></html>"
    sf = _src(tmp_path, "x.html", html, ".html")
    doc = extract(sf)
    assert "Hello" in doc.text
    assert "x()" not in doc.text


def test_image_caption_stubbed(tmp_path):
    p = tmp_path / "diagram.png"
    p.write_bytes(b"\x89PNG")
    sf = SourceFile(
        path=str(p), name="diagram.png", ext=".png", size_bytes=4,
        category=Category.DIAGRAM_IMAGE,
    )
    doc = extract(sf)
    assert "caption pending" in doc.text
    assert doc.extractor == "caption-stub"


def test_image_caption_injected(tmp_path):
    p = tmp_path / "diagram.png"
    p.write_bytes(b"\x89PNG")
    sf = SourceFile(
        path=str(p), name="diagram.png", ext=".png", size_bytes=4,
        category=Category.DIAGRAM_IMAGE,
    )
    doc = extract(sf, captioner=lambda _p: "ER diagram with two tables")
    assert doc.text == "ER diagram with two tables"
    assert doc.extractor == "caption"
