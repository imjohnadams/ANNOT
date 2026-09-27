import os
import re

import fitz

from models.book import Book, Page
from pdf.chapter_detector import detect_chapters
from pdf.header_footer import detect_repeating_lines, strip_headers_footers


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(pdf_path: str, source_filepath: str | None = None) -> Book:
    if source_filepath is None:
        source_filepath = pdf_path

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(
            "Could not read this PDF. It may be corrupted, empty, or "
            f"password-protected. ({exc})"
        ) from exc

    try:
        raw_pages: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if not text.strip():
                text = "[NO TEXT FOUND]"
            raw_pages.append(_clean_text(text))

        repeating = detect_repeating_lines(raw_pages)

        author = (doc.metadata.get("author") or "").strip()

        book = Book(
            title=doc.metadata.get("title") or os.path.basename(pdf_path),
            filepath=pdf_path,
            source_filepath=source_filepath,
            total_pages=len(doc),
            author=author,
        )

        for page_number, raw_text in enumerate(raw_pages, start=1):
            cleaned = strip_headers_footers(raw_text, repeating)
            book.pages.append(
                Page(
                    number=page_number,
                    text=cleaned,
                    raw_text=raw_text,
                )
            )
    finally:
        doc.close()

    book.chapters = detect_chapters(book, pdf_path)
    return book
