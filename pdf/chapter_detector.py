import re

import fitz

from config import FRONT_MATTER_MAX_SCAN_PAGES, FRONT_MATTER_MIN_CONTENT_WORDS
from models.book import Book, Chapter
from pdf.layout_detector import (
    detect_article_heading,
    detect_chapter_from_layout,
    detect_chapter_from_regex,
)


def _build_chapters_from_starts(
    starts: list[tuple[int, str]],
    total_pages: int,
    method: str,
) -> list[Chapter]:
    if not starts:
        return []

    starts.sort(key=lambda item: item[0])

    deduped: list[tuple[int, str]] = []
    seen_pages: set[int] = set()
    for page_num, title in starts:
        if page_num in seen_pages:
            continue
        seen_pages.add(page_num)
        deduped.append((page_num, title))

    chapters: list[Chapter] = []
    for index, (start_page, title) in enumerate(deduped):
        end_page = (
            deduped[index + 1][0] - 1
            if index + 1 < len(deduped)
            else total_pages
        )
        chapters.append(
            Chapter(
                number=index + 1,
                title=title,
                start_page=start_page,
                end_page=end_page,
                detection_method=method,
            )
        )

    return chapters


def detect_from_toc(doc: fitz.Document) -> list[Chapter]:
    toc = doc.get_toc(simple=True)
    if not toc:
        return []

    starts: list[tuple[int, str]] = []
    for _level, title, page in toc:
        title = title.strip()
        if not title or page < 1:
            continue
        starts.append((page, title))

    return _build_chapters_from_starts(starts, len(doc), "toc")


def detect_from_layout(doc: fitz.Document) -> list[Chapter]:
    starts: list[tuple[int, str]] = []
    for page_number, page in enumerate(doc, start=1):
        heading = detect_chapter_from_layout(page)
        if heading:
            starts.append((page_number, heading))
    return _build_chapters_from_starts(starts, len(doc), "layout")


def detect_from_regex(book: Book) -> list[Chapter]:
    starts: list[tuple[int, str]] = []
    for page in book.pages:
        heading = detect_chapter_from_regex(page.text)
        if heading:
            starts.append((page.number, heading))
    return _build_chapters_from_starts(starts, book.total_pages, "regex")


def detect_from_article_headings(book: Book) -> list[Chapter]:
    starts: list[tuple[int, str]] = []
    for page in book.pages:
        heading = detect_article_heading(page.text)
        if heading:
            starts.append((page.number, heading))
    return _build_chapters_from_starts(starts, book.total_pages, "article_headings")


def _is_front_matter_page(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    word_count = len(stripped.split())
    lower = stripped.lower()

    front_patterns = [
        r"all rights reserved",
        r"copyright",
        r"published by",
        r"isbn",
        r"library of congress",
        r"first edition",
        r"table of contents",
        r"contents",
    ]

    if word_count < 40:
        return True

    for pattern in front_patterns:
        if re.search(pattern, lower):
            return True

    return word_count < FRONT_MATTER_MIN_CONTENT_WORDS


def find_content_start_page(book: Book) -> int:
    scan_limit = min(FRONT_MATTER_MAX_SCAN_PAGES, book.total_pages)
    for page in book.pages[:scan_limit]:
        if not _is_front_matter_page(page.text):
            return page.number
    return 1


def exclude_front_matter(book: Book, chapters: list[Chapter]) -> list[Chapter]:
    if not chapters:
        return chapters

    content_start = find_content_start_page(book)
    kept: list[Chapter] = []
    for chapter in chapters:
        start = max(chapter.start_page, content_start)
        end = chapter.end_page
        if start > end:
            continue
        chapter.start_page = start
        chapter.end_page = end
        kept.append(chapter)

    for index in range(len(kept) - 1):
        next_start = kept[index + 1].start_page
        if kept[index].end_page >= next_start:
            kept[index].end_page = next_start - 1

    kept = [chapter for chapter in kept if chapter.start_page <= chapter.end_page]
    if not kept:
        return fallback_whole_book(book)
    return kept


def fallback_whole_book(book: Book) -> list[Chapter]:
    content_start = find_content_start_page(book)
    return [
        Chapter(
            number=1,
            title="Full document",
            start_page=content_start,
            end_page=book.total_pages,
            detection_method="fallback",
        )
    ]


def detect_chapters(book: Book, pdf_path: str) -> list[Chapter]:
    doc = fitz.open(pdf_path)
    warnings: list[str] = []

    try:
        chapters = detect_from_toc(doc)
        if len(chapters) >= 2:
            method = "toc"
        else:
            chapters = detect_from_layout(doc)
            if len(chapters) >= 2:
                method = "layout"
            else:
                chapters = detect_from_regex(book)
                if len(chapters) >= 2:
                    method = "regex"
                else:
                    chapters = detect_from_article_headings(book)
                    if len(chapters) >= 2:
                        method = "article_headings"
                    else:
                        chapters = fallback_whole_book(book)
                        method = "fallback"
                        warnings.append(
                            "No chapter or section headings detected. "
                            "The whole document is treated as one section."
                        )

        # A short abstract is real content. Do not shift article sections
        # forward the way front matter is skipped in a book.
        if method not in ("fallback", "article_headings"):
            chapters = exclude_front_matter(book, chapters)

        for index, chapter in enumerate(chapters, start=1):
            chapter.number = index

        book.warnings.extend(warnings)
        return chapters

    finally:
        doc.close()
