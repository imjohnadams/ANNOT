import os
import sys

_ANNOT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ANNOT_ROOT not in sys.path:
    sys.path.insert(0, _ANNOT_ROOT)

from ai.run_settings import (
    AnnotationSettings,
    should_skip_quality_prompt,
)
from cli.display import (
    get_selection_cost_summary,
    print_book_summary,
    print_chapter_index,
    print_selection_summary,
)
from cli.selection import filter_valid_chapters, parse_chapter_selection
from config import (
    DEFAULT_QUALITY,
    DEFAULT_QUOTES_PER_PAGE,
    LUNA_API_KEY,
    LUNA_BASE_URL,
    LUNA_MODEL,
    MAX_QUOTES_PER_PAGE,
    MIN_QUOTES_PER_PAGE,
    QUALITY_CHOICES,
    QUALITY_DESCRIPTIONS,
)
from ingest.converter import normalize_to_pdf
from output.json_io import finalize_chapter_outputs
from pdf.parser import parse_pdf
from pipeline.highlight import run_highlight
from pipeline.runner import run_annotation_pipeline
from utils.paths import (
    annot_output_dir,
    highlighted_pdf_path,
    logs_output_dir,
    master_csv_path,
    master_json_path,
)


def prompt_path() -> str:
    path = input(
        "\nDocument path (PDF, EPUB, MOBI, TXT, AZW, AZW3):\n"
    ).strip()
    return path.strip('"')


def prompt_output_root() -> str | None:
    if not prompt_confirm("Use a custom output folder?"):
        return None

    while True:
        path = input("\nOutput folder path:\n").strip().strip('"')
        if not path:
            print("Please enter a folder path, or restart and choose N.")
            continue
        if not os.path.isdir(path):
            create = prompt_confirm(
                f"Folder does not exist:\n  {path}\nCreate it?"
            )
            if create:
                os.makedirs(path, exist_ok=True)
                return path
            continue
        return path


def prompt_chapter_selection() -> list[int]:
    user_input = input(
        "\nSection(s) to analyze "
        "(examples: 5 | 4-7 | 5, 7, 9 | 2-4, 6-12):\n"
    ).strip()
    return parse_chapter_selection(user_input)


def prompt_confirm(message: str) -> bool:
    answer = input(f"\n{message} (Y/N): ").strip().lower()
    return answer == "y"


def prompt_quotes_per_page() -> int:
    while True:
        raw = input(
            f"\nAnnotation density — maximum notes per page "
            f"({MIN_QUOTES_PER_PAGE}-{MAX_QUOTES_PER_PAGE}) "
            f"[{DEFAULT_QUOTES_PER_PAGE}]: "
        ).strip()
        if not raw:
            return DEFAULT_QUOTES_PER_PAGE
        if raw.isdigit():
            value = int(raw)
            if MIN_QUOTES_PER_PAGE <= value <= MAX_QUOTES_PER_PAGE:
                return value
        print(
            f"Enter a whole number from "
            f"{MIN_QUOTES_PER_PAGE} to {MAX_QUOTES_PER_PAGE}."
        )


def prompt_quality() -> str:
    print("\nQuality:")
    for num, name in sorted(QUALITY_CHOICES.items()):
        print(f"  {num} = {name.capitalize()} — {QUALITY_DESCRIPTIONS[name]}")
    default_num = next(
        num for num, name in QUALITY_CHOICES.items() if name == DEFAULT_QUALITY
    )
    while True:
        raw = input(f"Choose 1, 2, or 3 [{default_num}]: ").strip()
        if not raw:
            return DEFAULT_QUALITY
        if raw.isdigit():
            value = int(raw)
            if value in QUALITY_CHOICES:
                return QUALITY_CHOICES[value]
        print("Enter 1, 2, or 3.")


def prompt_annotation_settings(selected_page_count: int) -> AnnotationSettings:
    quotes_per_page = prompt_quotes_per_page()

    if should_skip_quality_prompt(selected_page_count):
        print(
            f"\nLong selection ({selected_page_count} pages) — "
            f"using Medium quality. Quality prompt skipped."
        )
        settings = AnnotationSettings(
            quotes_per_page=quotes_per_page,
            quality=DEFAULT_QUALITY,
            quality_was_skipped=True,
        )
    else:
        quality = prompt_quality()
        settings = AnnotationSettings(
            quotes_per_page=quotes_per_page,
            quality=quality,
            quality_was_skipped=False,
        )

    if settings.should_warn_dense_high():
        print(
            "\nWARNING: A high density cap with High quality can crowd "
            "the page and weaken the notes."
        )
        if not prompt_confirm("Continue with these settings anyway?"):
            print("Settings cancelled — choose again.")
            return prompt_annotation_settings(selected_page_count)

    return settings


def load_book(source_path: str, output_root: str | None = None):
    print("\nLoading document...")
    pdf_path, was_converted = normalize_to_pdf(source_path, output_root)
    book = parse_pdf(pdf_path, source_filepath=source_path)
    book.output_root = output_root
    return book, pdf_path, was_converted


def run_selection_loop(book) -> tuple[list[int], AnnotationSettings] | None:
    available = {c.number for c in book.chapters}

    while True:
        try:
            selected = prompt_chapter_selection()
        except ValueError as exc:
            print(f"\nInvalid input: {exc}")
            continue

        valid, invalid = filter_valid_chapters(selected, available)

        if invalid:
            print("\nSkipped section numbers that are not in this document:")
            for number in invalid:
                print(f"  - {number}")

        if not valid:
            print("\nNo valid sections selected. Try again.")
            continue

        summary = get_selection_cost_summary(book, valid)
        page_count = summary["total_pages"] if summary else 0
        settings = prompt_annotation_settings(page_count)

        print_selection_summary(book, valid, settings)

        if not prompt_confirm("Proceed with analysis?"):
            print("Analysis cancelled.")
            return None

        return valid, settings


def check_api_config() -> None:
    if not LUNA_API_KEY:
        raise RuntimeError(
            "LUNA_API_KEY is not configured. Set it in ANNOT/.env"
        )
    print(f"\nAPI: {LUNA_BASE_URL}")
    print(f"Model: {LUNA_MODEL}")


def finalize_and_highlight(book, pdf_path: str, was_converted: bool) -> None:
    """Delete chapter files, run PDFER, print final output paths."""
    source = book.source_filepath
    output_root = book.output_root
    master_json = master_json_path(source, output_root)
    master_csv = master_csv_path(source, output_root)

    if not os.path.isfile(master_json):
        print("\nNo master annotations found — skipping highlight.")
        return

    removed = finalize_chapter_outputs(source, output_root)
    if removed:
        print(f"\nRemoved {removed} individual chapter file(s).")

    out_pdf = highlighted_pdf_path(source, output_root)
    print("\n" + "=" * 62)
    print("HIGHLIGHTING PDF")
    print("=" * 62)
    print(f"PDF:    {pdf_path}")
    print(f"Data:   {master_json}")
    print(f"Output: {out_pdf}")

    try:
        report = run_highlight(pdf_path, master_json, out_pdf)
    except Exception as exc:
        print(f"\nERROR during highlighting: {exc}")
        print("Master JSON/CSV were kept. You can re-run PDFER manually.")
        return

    if report is None or report.highlighted_count == 0:
        print("\nNo notes could be placed on the PDF — highlighted PDF not created.")
        return

    print(f"\nHighlighted: {report.highlighted_count}")
    print(f"Notes:       {report.notes_count}")
    print(f"Misses:      {report.miss_count}")

    if report.misses:
        print("Missed quotes (first 10):")
        for miss in report.misses[:10]:
            preview = miss.book_text.replace("\n", " ")
            if len(preview) > 80:
                preview = preview[:77] + "..."
            print(f"  p{miss.page}: [{miss.reason}] {preview}")

    if was_converted and os.path.isfile(pdf_path):
        output_dir = os.path.normcase(os.path.abspath(annot_output_dir(source, output_root)))
        converted = os.path.normcase(os.path.abspath(pdf_path))
        prefix = output_dir if output_dir.endswith(os.sep) else output_dir + os.sep
        if converted.startswith(prefix) and os.path.basename(converted).endswith("_converted.pdf"):
            try:
                os.remove(converted)
                print(f"\nRemoved temporary converted PDF.")
            except OSError as exc:
                print(f"\nCould not remove temporary converted PDF: {exc}")

    print("\n" + "=" * 62)
    print("ALL DONE")
    print("=" * 62)
    print(f"Highlighted PDF: {out_pdf}")
    print(f"Master JSON:     {master_json}")
    print(f"Master CSV:      {master_csv}")
    print(f"Logs folder:     {logs_output_dir(source, output_root)}")
    print(f"Output folder:   {annot_output_dir(source, output_root)}")


def main() -> None:
    print("=" * 62)
    print("ANNOT — Research document analysis")
    print("=" * 62)
    print("Reads one document you already have. It does not search other papers.")

    try:
        check_api_config()
    except RuntimeError as exc:
        print(f"\nERROR: {exc}")
        return

    source_path = prompt_path()
    output_root = prompt_output_root()

    try:
        book, pdf_path, was_converted = load_book(source_path, output_root)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"\nERROR: {exc}")
        return

    print_book_summary(book, pdf_path, was_converted)
    print_chapter_index(book)

    annotated_ok = False

    while True:
        result = run_selection_loop(book)
        if result:
            selected, settings = result
            try:
                run_annotation_pipeline(book, selected, settings)
                annotated_ok = True
            except Exception as exc:
                print(f"\nERROR during analysis: {exc}")
                print(
                    "Notes already saved for earlier sections were kept. "
                    "If any section in this attempt finished, the master JSON and CSV "
                    "include only those sections. No highlighted PDF was written."
                )

        if not prompt_confirm("Analyze more sections?"):
            break

    if annotated_ok:
        finalize_and_highlight(book, pdf_path, was_converted)
    else:
        print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
    input("\nPress Enter to exit...")
