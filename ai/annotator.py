import json
import os

from openai import OpenAI

from ai.client import get_client
from ai.run_settings import AnnotationSettings, build_settings_overlay
from ai.schema import CHAPTER_RESPONSE_SCHEMA
from config import (
    CHUNK_OUTPUT_TOKEN_BUDGET,
    DOCUMENT_FRAME_MAX_TOKENS,
    LUNA_MODEL,
    MAX_CONTEXT_TOKENS,
    MAX_OUTPUT_TOKENS,
    PROMPT_FILE,
)
from models.book import Book, Chapter
from utils.tokens import count_tokens


def load_system_prompt(settings: AnnotationSettings | None = None) -> str:
    if not os.path.isfile(PROMPT_FILE):
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    with open(PROMPT_FILE, "r", encoding="utf-8") as file:
        base = file.read()
    if settings is None:
        return base
    return base + "\n\n" + build_settings_overlay(settings)


def build_document_frame(book: Book) -> str:
    """Short context from metadata, section titles, and the opening pages."""
    title = (book.title or "").strip()
    author = (book.author or "").strip()
    lines = [
        "DOCUMENT FRAME (context only; do not quote it unless the same words "
        "appear in CURRENT PAGES):",
        f"Title: {title or 'unavailable'}",
        f"Author: {author or 'unavailable'}",
        "Sections:",
    ]
    if book.chapters:
        for chapter in book.chapters:
            lines.append(
                f"- {chapter.number}. {chapter.title} "
                f"(PDF pages {chapter.start_page}-{chapter.end_page})"
            )
    else:
        lines.append("- unavailable")

    lines.append("")
    lines.append("Opening text:")
    used = count_tokens("\n".join(lines))
    opening: list[str] = []
    for page in book.pages[:8]:
        text = (page.text or "").strip()
        if not text or text == "[NO TEXT FOUND]":
            continue
        piece = f"=== PAGE {page.number} ===\n{page.text}\n"
        piece_tokens = count_tokens(piece)
        if used + piece_tokens > DOCUMENT_FRAME_MAX_TOKENS:
            break
        opening.append(piece)
        used += piece_tokens
    if opening:
        lines.extend(opening)
    else:
        lines.append("unavailable")
    return "\n".join(lines)


def build_user_message(
    book: Book,
    chapter: Chapter,
    settings: AnnotationSettings | None = None,
    document_frame: str = "",
    overlap_page: int | None = None,
) -> str:
    header = ""
    if document_frame:
        header += document_frame + "\n\n"

    if overlap_page is not None:
        overlap_text = book.get_page_text(overlap_page)
        if overlap_text:
            header += (
                "ADJACENT CONTEXT (do not quote this page; "
                "it is only for terms and methods already introduced):\n\n"
                f"=== PAGE {overlap_page} ===\n\n"
                f"{overlap_text}\n\n"
            )

    header += (
        "CURRENT PAGES (every book_text quote must be copied from one of these "
        "pages):\n\n"
        f"Chapter {chapter.number}: {chapter.title}\n\n"
        f"Pages {chapter.start_page}-{chapter.end_page}\n\n"
    )
    if settings is not None:
        page_count = chapter.end_page - chapter.start_page + 1
        maximum = settings.expected_annotation_count(page_count)
        header += (
            f"RUNTIME SETTINGS: max_annotations_per_page="
            f"{settings.quotes_per_page}, quality={settings.quality}. "
            f"Return at most {maximum} annotations for this page range. "
            f"Fewer is correct when a page has little worth noting.\n\n"
        )
    return header + book.get_chapter_text(chapter)


def build_retry_message(
    book: Book,
    chapter: Chapter,
    validation_errors: list[str],
    settings: AnnotationSettings | None = None,
    document_frame: str = "",
    overlap_page: int | None = None,
) -> str:
    error_block = "\n".join(f"- {error}" for error in validation_errors[:20])
    return (
        build_user_message(
            book, chapter, settings, document_frame, overlap_page
        )
        + "\n\nYour previous response failed validation. Fix every issue and "
        "return valid JSON only.\n\nValidation errors:\n"
        + error_block
    )


def _call_api(
    client: OpenAI,
    system_prompt: str,
    user_message: str,
) -> tuple[dict, dict]:
    response = client.chat.completions.create(
        model=LUNA_MODEL,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "chapter_annotations",
                "strict": True,
                "schema": CHAPTER_RESPONSE_SCHEMA,
            },
        },
    )

    raw = response.choices[0].message.content or ""
    usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
    }
    return json.loads(raw), usage


def annotate_page_range(
    book: Book,
    chapter: Chapter,
    start_page: int,
    end_page: int,
    system_prompt: str,
    client: OpenAI | None = None,
    validation_errors: list[str] | None = None,
    settings: AnnotationSettings | None = None,
    document_frame: str = "",
    overlap_page: int | None = None,
) -> tuple[dict, dict, str]:
    if client is None:
        client = get_client()

    chunk_chapter = Chapter(
        number=chapter.number,
        title=chapter.title,
        start_page=start_page,
        end_page=end_page,
        detection_method=chapter.detection_method,
    )

    if validation_errors:
        user_message = build_retry_message(
            book,
            chunk_chapter,
            validation_errors,
            settings,
            document_frame,
            overlap_page,
        )
    else:
        user_message = build_user_message(
            book,
            chunk_chapter,
            settings,
            document_frame,
            overlap_page,
        )

    data, usage = _call_api(client, system_prompt, user_message)

    data["chapter_number"] = chapter.number
    data["chapter_title"] = chapter.title
    data["start_page"] = start_page
    data["end_page"] = end_page

    return data, usage, user_message


def merge_chunk_results(chunks: list[dict], chapter: Chapter) -> dict:
    annotations = []
    for chunk in chunks:
        annotations.extend(chunk.get("annotations", []))

    annotations.sort(key=lambda row: row.get("page", 0))

    return {
        "chapter_number": chapter.number,
        "chapter_title": chapter.title,
        "start_page": chapter.start_page,
        "end_page": chapter.end_page,
        "annotations": annotations,
    }


def get_page_chunks(start_page: int, end_page: int, chunk_size: int) -> list[tuple[int, int]]:
    chunks = []
    current = start_page
    while current <= end_page:
        chunk_end = min(current + chunk_size - 1, end_page)
        chunks.append((current, chunk_end))
        current = chunk_end + 1
    return chunks


def estimate_chunk_size(
    book: Book,
    chapter: Chapter,
    page_count: int,
    quotes_per_page: int = 1,
) -> int:
    if page_count <= 1:
        return 1

    total_tokens = count_tokens(book.get_chapter_text(chapter))
    tokens_per_page = max(1, total_tokens // page_count)

    tokens_per_annot = 220
    max_annots_by_output = max(1, CHUNK_OUTPUT_TOKEN_BUDGET // tokens_per_annot)
    max_pages_by_output = max(1, max_annots_by_output // max(1, quotes_per_page))
    if quotes_per_page > 1:
        max_pages_by_output = min(max_pages_by_output, 20)
    max_pages_by_input = max(1, (MAX_CONTEXT_TOKENS // tokens_per_page))
    return max(1, min(max_pages_by_output, max_pages_by_input, page_count))


def annotate_chapter(
    book: Book,
    chapter: Chapter,
    system_prompt: str | None = None,
    client: OpenAI | None = None,
    validation_errors: list[str] | None = None,
    settings: AnnotationSettings | None = None,
) -> tuple[dict, dict, str]:
    if settings is None:
        settings = AnnotationSettings()
    if system_prompt is None:
        system_prompt = load_system_prompt(settings)
    if client is None:
        client = get_client()

    document_frame = build_document_frame(book)
    page_count = book.get_chapter_page_count(chapter)
    chunk_size = estimate_chunk_size(
        book, chapter, page_count, settings.quotes_per_page
    )

    if page_count <= chunk_size:
        return annotate_page_range(
            book,
            chapter,
            chapter.start_page,
            chapter.end_page,
            system_prompt,
            client,
            validation_errors,
            settings,
            document_frame,
            None,
        )

    chunks: list[dict] = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    last_message = ""

    page_chunks = get_page_chunks(chapter.start_page, chapter.end_page, chunk_size)
    for start_page, end_page in page_chunks:
        overlap_page = start_page - 1 if start_page > chapter.start_page else None
        chunk_data, usage, last_message = annotate_page_range(
            book,
            chapter,
            start_page,
            end_page,
            system_prompt,
            client,
            None,
            settings,
            document_frame,
            overlap_page,
        )
        chunks.append(chunk_data)
        for key in total_usage:
            total_usage[key] += usage.get(key, 0)

    merged = merge_chunk_results(chunks, chapter)
    return merged, total_usage, last_message
