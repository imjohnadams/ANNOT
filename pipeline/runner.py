import json
import os

from ai.annotator import annotate_chapter, load_system_prompt
from ai.client import get_client
from ai.run_settings import AnnotationSettings
from ai.type_classifier import apply_types
from config import INPUT_COST_ESTIMATE, LUNA_MODEL, MAX_API_RETRIES, OUTPUT_COST_REGULAR
from models.book import Book, Chapter
from output.json_io import (
    export_chapter_csv,
    export_master_csv,
    save_chapter_json,
    save_failed_response,
    save_master_json,
)
from utils.paths import failed_response_path
from validate.verifier import (
    has_blocking_errors,
    normalize_annotations_to_qpp,
    validate_structure,
    validate_structure_hard,
    verify_and_fix_annotations,
)


def _page_text_map(book: Book, chapter: Chapter) -> dict[int, str]:
    return {
        page.number: page.text
        for page in book.pages
        if chapter.start_page <= page.number <= chapter.end_page
    }


def _estimate_cost_usd(usage: dict) -> float:
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    return (prompt * INPUT_COST_ESTIMATE) + (completion * OUTPUT_COST_REGULAR)


def annotate_chapter_with_retries(
    book: Book,
    chapter: Chapter,
    settings: AnnotationSettings,
) -> dict:
    client = get_client()
    system_prompt = load_system_prompt(settings)
    page_texts = _page_text_map(book, chapter)
    output_root = book.output_root

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    validation_errors: list[str] | None = None
    last_raw = ""

    for attempt in range(1, MAX_API_RETRIES + 1):
        print(f"  API call attempt {attempt}/{MAX_API_RETRIES}...")

        try:
            data, usage, _user_message = annotate_chapter(
                book,
                chapter,
                system_prompt=system_prompt,
                client=client,
                validation_errors=validation_errors,
                settings=settings,
            )
            last_raw = json.dumps(data, indent=2)
        except Exception as exc:
            last_raw = str(exc)
            save_failed_response(
                failed_response_path(
                    book.source_filepath,
                    chapter.number,
                    attempt,
                    output_root,
                ),
                last_raw,
            )
            validation_errors = [f"API/parse error: {exc}"]
            if attempt == MAX_API_RETRIES:
                raise
            continue

        for key in total_usage:
            total_usage[key] += usage.get(key, 0)

        # Hard structural issues only — count mismatches are soft-repaired
        hard_errors = validate_structure_hard(
            data,
            chapter.start_page,
            chapter.end_page,
        )
        if has_blocking_errors(hard_errors):
            save_failed_response(
                failed_response_path(
                    book.source_filepath,
                    chapter.number,
                    attempt,
                    output_root,
                ),
                last_raw,
            )
            validation_errors = hard_errors
            if attempt == MAX_API_RETRIES:
                raise ValueError(
                    f"Chapter {chapter.number} failed structural validation after "
                    f"{MAX_API_RETRIES} attempts:\n"
                    + "\n".join(hard_errors)
                )
            continue

        data, repair_report = normalize_annotations_to_qpp(
            data,
            chapter.start_page,
            chapter.end_page,
            settings.quotes_per_page,
            apply_limit=False,
        )

        corrected, verify_errors = verify_and_fix_annotations(
            data,
            page_texts,
            chapter.start_page,
            chapter.end_page,
        )
        corrected, second_report = normalize_annotations_to_qpp(
            corrected,
            chapter.start_page,
            chapter.end_page,
            settings.quotes_per_page,
        )
        for key in ("trimmed", "dropped_oor", "dropped_duplicate", "dropped_invalid"):
            repair_report[key] += second_report[key]

        post_errors = validate_structure(
            corrected,
            chapter.start_page,
            chapter.end_page,
            quotes_per_page=settings.quotes_per_page,
        )
        if post_errors:
            raise RuntimeError(
                f"Section {chapter.number}: density cap left structure errors:\n"
                + "\n".join(post_errors)
            )

        if (
            repair_report["trimmed"]
            or repair_report["dropped_oor"]
            or repair_report["dropped_duplicate"]
        ):
            print(
                f"  Density cap: trimmed {repair_report['trimmed']}, "
                f"dropped out of range {repair_report['dropped_oor']}, "
                f"dropped duplicates {repair_report['dropped_duplicate']}"
            )

        corrected = apply_types(corrected)
        corrected["source_filename"] = os.path.basename(book.source_filepath)
        corrected["quality"] = settings.quality
        corrected["density"] = settings.quotes_per_page

        json_path = save_chapter_json(
            book.source_filepath,
            chapter.number,
            corrected,
            output_root,
        )
        csv_path = export_chapter_csv(
            book.source_filepath,
            chapter.number,
            corrected,
            output_root,
        )

        flagged = sum(
            1
            for row in corrected.get("annotations", [])
            if row.get("validation_flags")
        )

        print(f"  Saved JSON: {json_path}")
        print(f"  Saved CSV:  {csv_path}")
        if flagged:
            print(f"  Flagged rows: {flagged}")
        if verify_errors:
            print(f"  Validation notes: {len(verify_errors)}")

        return {
            "chapter_data": corrected,
            "usage": total_usage,
            "cost_usd": _estimate_cost_usd(total_usage),
            "flagged_rows": flagged,
            "json_path": json_path,
            "csv_path": csv_path,
            "qpp_trimmed": repair_report["trimmed"],
            "qpp_dropped_oor": repair_report["dropped_oor"],
            "qpp_dropped_duplicate": repair_report["dropped_duplicate"],
        }

    raise RuntimeError(f"Chapter {chapter.number} annotation failed unexpectedly.")


def run_annotation_pipeline(
    book: Book,
    chapter_numbers: list[int],
    settings: AnnotationSettings | None = None,
) -> dict:
    if settings is None:
        settings = AnnotationSettings()

    chapters_by_number = {chapter.number: chapter for chapter in book.chapters}
    completed: list[dict] = []
    run_metadata = {
        "chapters_requested": chapter_numbers,
        "chapters_completed": [],
        "total_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "total_cost_usd": 0.0,
        "total_flagged_rows": 0,
        "qpp_trimmed_total": 0,
        "qpp_dropped_oor_total": 0,
        "qpp_dropped_duplicate_total": 0,
        "model": LUNA_MODEL,
        "source_filename": os.path.basename(book.source_filepath),
        "author": book.author or "",
        "title": book.title,
        **settings.to_metadata(),
    }

    print(
        f"\nRun settings: density cap={settings.quotes_per_page}/page, "
        f"quality={settings.quality_label}"
        + (" (auto Medium)" if settings.quality_was_skipped else "")
    )

    try:
        for index, number in enumerate(chapter_numbers, start=1):
            chapter = chapters_by_number.get(number)
            if chapter is None:
                print(
                    f"\n[{index}/{len(chapter_numbers)}] "
                    f"Chapter {number} — skipped (not found)"
                )
                continue

            page_count = book.get_chapter_page_count(chapter)
            maximum = settings.expected_annotation_count(page_count)
            print(
                f"\n[{index}/{len(chapter_numbers)}] Section {chapter.number}: "
                f"{chapter.title} (pages {chapter.start_page}-{chapter.end_page}, "
                f"{page_count} pages, up to {maximum} annotations)"
            )

            result = annotate_chapter_with_retries(book, chapter, settings)
            completed.append(result["chapter_data"])

            usage = result["usage"]
            for key in run_metadata["total_usage"]:
                run_metadata["total_usage"][key] += usage.get(key, 0)

            run_metadata["total_cost_usd"] += result["cost_usd"]
            run_metadata["total_flagged_rows"] += result["flagged_rows"]
            run_metadata["qpp_trimmed_total"] += result.get("qpp_trimmed", 0)
            run_metadata["qpp_dropped_oor_total"] += result.get("qpp_dropped_oor", 0)
            run_metadata["qpp_dropped_duplicate_total"] += result.get(
                "qpp_dropped_duplicate", 0
            )
            run_metadata["chapters_completed"].append(chapter.number)

            print(
                f"  Tokens: {usage.get('total_tokens', 0):,} | "
                f"Est. cost: ${result['cost_usd']:.4f}"
            )
    except Exception:
        if run_metadata["chapters_completed"]:
            master_path = save_master_json(
                book.source_filepath,
                book.title,
                run_metadata,
                book.output_root,
            )
            master_csv = export_master_csv(
                book.source_filepath,
                book.output_root,
                master_path,
            )
            print(
                "\nMaster JSON and CSV include only the sections that finished "
                "in this attempt."
            )
            print(f"Master JSON: {master_path}")
            print(f"Master CSV:  {master_csv}")
        raise

    master_path = save_master_json(
        book.source_filepath,
        book.title,
        run_metadata,
        book.output_root,
    )
    master_csv = export_master_csv(
        book.source_filepath,
        book.output_root,
        master_path,
    )

    print("\n" + "=" * 62)
    print("ANNOTATION COMPLETE")
    print("=" * 62)
    print(f"Master JSON: {master_path}")
    print(f"Master CSV:  {master_csv}")
    print(f"Density cap: {settings.quotes_per_page} per page")
    print(f"Quality: {settings.quality_label}")
    print(f"Total tokens: {run_metadata['total_usage']['total_tokens']:,}")
    print(f"Total est. cost: ${run_metadata['total_cost_usd']:.4f}")
    print(f"Flagged rows: {run_metadata['total_flagged_rows']}")
    print(
        f"Density cap: trimmed {run_metadata['qpp_trimmed_total']}, "
        f"dropped out of range {run_metadata['qpp_dropped_oor_total']}, "
        f"dropped duplicates {run_metadata['qpp_dropped_duplicate_total']}"
    )
    print(
        "\nSection files kept until you decline more sections; "
        "the annotated PDF is written then."
    )

    return {
        "master_path": master_path,
        "master_csv_path": master_csv,
        "run_metadata": run_metadata,
        "chapters": completed,
    }
