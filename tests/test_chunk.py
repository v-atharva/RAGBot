from ragbot.ingest.chunk import chunk_document
from ragbot.ingest.models import Category, ExtractedDoc, PageSpan, Sensitivity, SourceFile


def _src(name, cat, ext=".pdf", **kw):
    return SourceFile(path=f"/x/{name}", name=name, ext=ext, size_bytes=1, category=cat, **kw)


def test_transcript_timestamp_citation():
    text = "\n".join(f"[00:0{i}:00] Speaker: utterance {i} " + "x" * 200 for i in range(5))
    doc = ExtractedDoc(source=_src("lec01.txt", Category.LECTURE_TRANSCRIPT, ".txt"), text=text)
    chunks = chunk_document(doc)
    assert chunks
    assert "@ 00:0" in chunks[0].citation
    assert chunks[0].source_file == "lec01.txt"


def test_pdf_page_citation():
    text = "A" * 1500 + "B" * 1500
    doc = ExtractedDoc(
        source=_src("Ch05_MySQL.pdf", Category.TEXTBOOK_CHAPTER),
        text=text,
        pages=[
            PageSpan(label="p.1", start=0, end=1500),
            PageSpan(label="p.2", start=1500, end=3000),
        ],
    )
    chunks = chunk_document(doc)
    cites = {c.citation for c in chunks}
    assert any("p.1" in c for c in cites)
    assert any("p.2" in c for c in cites)


def test_sql_kept_whole():
    doc = ExtractedDoc(source=_src("q.sql", Category.SQL_SCRIPT, ".sql"), text="SELECT 1;" * 500)
    assert len(chunk_document(doc)) == 1


def test_chunk_carries_sensitivity_and_exercise():
    doc = ExtractedDoc(
        source=_src("MoreNormEx-Soln.pdf", Category.SOLUTION_KEY, sensitivity=Sensitivity.HIGH),
        text="answer key body " * 100,
    )
    chunks = chunk_document(doc)
    assert all(c.sensitivity == Sensitivity.HIGH for c in chunks)
