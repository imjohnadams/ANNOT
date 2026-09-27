from ai.run_settings import AnnotationSettings
from config import BUDGET_WARN_USD, QUALITY_DESCRIPTIONS
from models.book import Book, Chapter
from utils.paths import annot_output_dir
from utils.tokens import (
    count_tokens,
    estimate_chapter_output_tokens,
    estimate_run_cost_usd,
)


def _format_int(value: int) -> str:
    return f"{value:,}"


def print_book_summary(book: Book, pdf_path: str, was_converted: bool) -> None:
    print("\n" + "=" * 62)
    print("ANNOT — Document loaded")
    print("=" * 62)
    print(f"Title:        {book.title}")
    print(f"Author:       {book.author or 'unavailable'}")
    print(f"Source:       {book.source_filepath}")
    print(f"Working PDF:  {pdf_path}")
    if was_converted:
        print("Converted:    Yes (temporary PDF in the output folder)")
    else:
        print("Converted:    No (already PDF)")
    print(f"Total pages:  {book.total_pages}")
    print(f"Output dir:   {annot_output_dir(book.source_filepath, book.output_root)}")

    if book.warnings:
        print("\nWarnings:")
        for warning in book.warnings:
            print(f"  ! {warning}")


def print_chapter_index(book: Book) -> None:
    print("\n" + "-" * 62)
    print("Sections")
    print("-" * 62)
    print(
        f"{'#':>3}  {'Title':<28} {'Pages':>11}  "
        f"{'Chars':>9}  {'In tok':>8}  {'Out tok (est.)':>16}"
    )
    print("-" * 62)

    for chapter in book.chapters:
        page_count = book.get_chapter_page_count(chapter)
        char_count = book.get_chapter_char_count(chapter)
        chapter_text = book.get_chapter_text(chapter)
        input_tokens = count_tokens(chapter_text)
        out_low, out_high = estimate_chapter_output_tokens(page_count)
        page_range = f"{chapter.start_page}-{chapter.end_page}"

        title = chapter.title
        if len(title) > 28:
            title = title[:25] + "..."

        print(
            f"{chapter.number:>3}  {title:<28} {page_range:>11}  "
            f"{_format_int(char_count):>9}  {_format_int(input_tokens):>8}  "
            f"{_format_int(out_low)}-{_format_int(out_high)}"
        )

        if chapter.detection_method:
            print(f"      (detected via {chapter.detection_method})")


def get_selection_cost_summary(
    book: Book,
    selected_numbers: list[int],
    settings: AnnotationSettings | None = None,
) -> dict | None:
    if settings is None:
        settings = AnnotationSettings()

    chapters_by_number = {c.number: c for c in book.chapters}
    selected_chapters: list[Chapter] = []

    for number in selected_numbers:
        chapter = chapters_by_number.get(number)
        if chapter is not None:
            selected_chapters.append(chapter)

    if not selected_chapters:
        return None

    total_input = sum(
        count_tokens(book.get_chapter_text(c)) for c in selected_chapters
    )
    total_pages = sum(book.get_chapter_page_count(c) for c in selected_chapters)
    out_low, out_high = estimate_chapter_output_tokens(
        total_pages,
        quotes_per_page=settings.quotes_per_page,
        quality=settings.quality,
    )
    cost_low, cost_high = estimate_run_cost_usd(total_input, out_low, out_high)

    return {
        "selected_chapters": selected_chapters,
        "total_input": total_input,
        "total_pages": total_pages,
        "expected_annotations": settings.expected_annotation_count(total_pages),
        "out_low": out_low,
        "out_high": out_high,
        "cost_low": cost_low,
        "cost_high": cost_high,
        "over_budget": cost_high > BUDGET_WARN_USD,
        "settings": settings,
    }


def print_selection_summary(
    book: Book,
    selected_numbers: list[int],
    settings: AnnotationSettings | None = None,
) -> None:
    if settings is None:
        settings = AnnotationSettings()

    chapters_by_number = {c.number: c for c in book.chapters}

    print("\n" + "-" * 62)
    print("Selected sections")
    print("-" * 62)

    for number in selected_numbers:
        chapter = chapters_by_number.get(number)
        if chapter is None:
            print(f"  {number}. [SKIPPED — not found]")
            continue

        page_count = book.get_chapter_page_count(chapter)
        print(
            f"  {chapter.number}. {chapter.title} "
            f"(pages {chapter.start_page}-{chapter.end_page}, "
            f"{page_count} pages)"
        )

    summary = get_selection_cost_summary(book, selected_numbers, settings)
    if summary is None:
        print("  (none)")
        return

    print("\nRun settings:")
    print(f"  Density cap:    {settings.quotes_per_page} note(s) per page maximum")
    print(
        f"  Quality:        {settings.quality_label}"
        f" — {QUALITY_DESCRIPTIONS.get(settings.quality, '')}"
        + (" (auto Medium — long selection)" if settings.quality_was_skipped else "")
    )
    print(f"  Annotations:    up to {_format_int(summary['expected_annotations'])}")

    print("\nEstimated API usage for selection:")
    print(f"  Input tokens:   {_format_int(summary['total_input'])}")
    print(
        f"  Output tokens:  "
        f"{_format_int(summary['out_low'])} – {_format_int(summary['out_high'])}"
    )
    print(
        f"  Est. cost:      "
        f"${summary['cost_low']:.3f} – ${summary['cost_high']:.3f}"
    )

    if summary["over_budget"]:
        print(
            f"\n  ! Estimated cost may exceed ${BUDGET_WARN_USD:.2f} budget target."
        )

    if settings.should_warn_dense_high():
        print(
            "\n  ! High density with High quality can crowd the page and "
            "weaken the notes.\n"
            "    Prefer a cap of 1–2 for High, or Medium for denser coverage."
        )
