import csv
import json

from models.book import Book, Chapter, Page
from output.json_io import export_chapter_csv, export_master_csv, save_master_json
from ai.annotator import build_document_frame


def _book(tmp_path):
    source = tmp_path / "study.pdf"
    source.write_bytes(b"%PDF-1.4")
    book = Book(
        title="Sleep and attention",
        filepath=str(source),
        source_filepath=str(source),
        total_pages=2,
        author="A. Researcher",
        output_root=str(tmp_path),
        pages=[
            Page(1, "Abstract\n\nThis study tests attention after sleep loss."),
            Page(2, "Methods\n\nParticipants completed a randomized trial."),
        ],
        chapters=[
            Chapter(1, "Abstract", 1, 1, "article_headings"),
            Chapter(2, "Methods", 2, 2, "article_headings"),
        ],
    )
    return book, str(source)


def test_document_frame_uses_real_metadata():
    book = Book(
        title="Sleep and attention",
        filepath="study.pdf",
        source_filepath="study.pdf",
        total_pages=1,
        author="",
        pages=[Page(1, "Abstract\n\nAttention declined after sleep loss.")],
        chapters=[Chapter(1, "Abstract", 1, 1)],
    )
    frame = build_document_frame(book)
    assert "Title: Sleep and attention" in frame
    assert "Author: unavailable" in frame
    assert "Abstract" in frame


def test_csv_and_json_schema(tmp_path):
    book, source = _book(tmp_path)
    chapter = {
        "chapter_number": 2,
        "chapter_title": "Methods",
        "source_filename": "study.pdf",
        "quality": "high",
        "density": 1,
        "annotations": [
            {
                "page": 2,
                "book_text": "randomized trial",
                "annotation": "Random assignment supports a causal comparison in this study.",
                "category": "METHOD",
                "grounding": "source_fact",
            }
        ],
    }
    csv_path = export_chapter_csv(source, 2, chapter, book.output_root)
    with open(csv_path, encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["category"] == "METHOD"
    assert rows[0]["source_text"] == "randomized trial"
    assert rows[0]["grounding"] == "source_fact"
    assert "annotation" in rows[0]

    from output.json_io import save_chapter_json

    save_chapter_json(source, 2, chapter, book.output_root)
    master = save_master_json(
        source,
        book.title,
        {
            "quality": "high",
            "quotes_per_page": 1,
            "source_filename": "study.pdf",
            "model": "gpt-5.6-luna",
            "author": book.author,
        },
        book.output_root,
    )
    master_csv = export_master_csv(source, book.output_root, master)
    with open(master, encoding="utf-8") as file:
        payload = json.load(file)
    assert payload["run_metadata"]["model"] == "gpt-5.6-luna"
    assert payload["chapters"][0]["annotations"][0]["category"] == "METHOD"
    with open(master_csv, encoding="utf-8", newline="") as file:
        master_rows = list(csv.DictReader(file))
    assert master_rows[0]["document"] == "study.pdf"
    assert master_rows[0]["quality"] == "high"
    assert master_rows[0]["density"] == "1"
