import json
import re
from collections import defaultdict

from config import UNKNOWN

GENERIC_PREFIXES = (
    "this passage discusses",
    "this passage shows",
    "this shows that",
    "this is important because",
    "this is significant because",
)
MIN_NOTE_WORDS = 3
MAX_NOTE_WORDS = 140


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def quote_in_text(quote: str, page_text: str) -> bool:
    if not quote or quote == UNKNOWN:
        return quote == UNKNOWN

    if quote in page_text:
        return True

    normalized_quote = normalize_whitespace(quote)
    normalized_page = normalize_whitespace(page_text)

    return normalized_quote in normalized_page


def find_quote_page(quote: str, page_texts: dict[int, str]) -> int | None:
    if not quote or quote == UNKNOWN:
        return None

    for page_num, text in page_texts.items():
        if quote_in_text(quote, text):
            return page_num

    return None


def _add_flag(row: dict, flag: str) -> None:
    flags = list(row.get("validation_flags") or [])
    if flag not in flags:
        flags.append(flag)
    row["validation_flags"] = flags


def _verified_quote(row: dict) -> bool:
    text = str(row.get("book_text", "")).strip()
    return bool(text) and text != UNKNOWN


def cap_annotations_to_density(
    data: dict,
    start_page: int,
    end_page: int,
    quotes_per_page: int,
    *,
    apply_limit: bool = True,
) -> tuple[dict, dict]:
    """
    Drop out-of-range pages and duplicate quotes.
    When apply_limit is set, keep at most quotes_per_page rows per page,
    preferring a quote that is still in the document over [UNKNOWN].
    Do not pad.
    """
    repaired = json.loads(json.dumps(data))
    expected_pages = list(range(start_page, end_page + 1))
    expected_set = set(expected_pages)

    report = {
        "trimmed": 0,
        "dropped_oor": 0,
        "dropped_invalid": 0,
        "dropped_duplicate": 0,
    }

    annotations = repaired.get("annotations")
    if not isinstance(annotations, list):
        annotations = []

    by_page: dict[int, list[dict]] = defaultdict(list)

    for row in annotations:
        if not isinstance(row, dict):
            report["dropped_invalid"] += 1
            continue

        page = row.get("page")
        if isinstance(page, str) and page.strip().isdigit():
            page = int(page.strip())
            row["page"] = page

        if not isinstance(page, int):
            report["dropped_invalid"] += 1
            continue

        if page not in expected_set:
            report["dropped_oor"] += 1
            continue

        quote_key = normalize_whitespace(str(row.get("book_text", "")))
        existing = {
            normalize_whitespace(str(item.get("book_text", "")))
            for item in by_page[page]
            if str(item.get("book_text", "")).strip() not in ("", UNKNOWN)
        }
        if quote_key and quote_key != UNKNOWN and quote_key in existing:
            report["dropped_duplicate"] += 1
            continue

        by_page[page].append(row)

    normalized: list[dict] = []
    for page in expected_pages:
        rows = by_page.get(page, [])
        if apply_limit and len(rows) > quotes_per_page:
            indexed = list(enumerate(rows))
            indexed.sort(key=lambda item: (0 if _verified_quote(item[1]) else 1, item[0]))
            rows = [row for _, row in indexed]
            report["trimmed"] += len(rows) - quotes_per_page
            rows = rows[:quotes_per_page]
        normalized.extend(rows)

    repaired["annotations"] = normalized
    repaired["start_page"] = start_page
    repaired["end_page"] = end_page
    return repaired, report


def normalize_annotations_to_qpp(
    data: dict,
    start_page: int,
    end_page: int,
    quotes_per_page: int,
    *,
    apply_limit: bool = True,
) -> tuple[dict, dict]:
    """Backward-compatible name. Caps density and does not pad."""
    return cap_annotations_to_density(
        data,
        start_page,
        end_page,
        quotes_per_page,
        apply_limit=apply_limit,
    )


def validate_structure_hard(
    data: dict,
    expected_start: int,
    expected_end: int,
) -> list[str]:
    """Unrecoverable structural issues (soft repair cannot fix these)."""
    del expected_start, expected_end
    errors: list[str] = []

    required_top = [
        "chapter_number",
        "chapter_title",
        "start_page",
        "end_page",
        "annotations",
    ]
    for field in required_top:
        if field not in data:
            errors.append(f"Missing field: {field}")

    if errors:
        return errors

    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        errors.append("annotations must be an array")
        return errors

    for index, row in enumerate(annotations):
        prefix = f"annotations[{index}]"

        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for field in ("page", "book_text", "annotation", "category", "grounding"):
            if field not in row:
                errors.append(f"{prefix} missing field: {field}")

    return errors


def validate_structure(
    data: dict,
    expected_start: int,
    expected_end: int,
    quotes_per_page: int = 1,
) -> list[str]:
    """Structure check after the density cap. Counts may be below the cap."""
    errors = validate_structure_hard(data, expected_start, expected_end)
    if errors and any(
        e.startswith("Missing field") or e == "annotations must be an array"
        for e in errors
    ):
        return errors

    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        return errors

    expected_pages = set(range(expected_start, expected_end + 1))
    page_count = len(expected_pages)
    max_count = page_count * quotes_per_page

    if len(annotations) > max_count:
        errors.append(
            f"Expected at most {max_count} annotations "
            f"({page_count} pages × {quotes_per_page} per page), "
            f"got {len(annotations)}"
        )

    page_counts: dict[int, int] = defaultdict(int)
    for row in annotations:
        if not isinstance(row, dict):
            continue
        page = row.get("page")
        if isinstance(page, int):
            if page not in expected_pages:
                errors.append(
                    f"Page {page} outside range {expected_start}-{expected_end}"
                )
            else:
                page_counts[page] += 1

    for page, got in sorted(page_counts.items()):
        if got > quotes_per_page:
            errors.append(
                f"Page {page}: expected at most {quotes_per_page} annotations, got {got}"
            )

    return errors


def verify_and_fix_annotations(
    data: dict,
    page_texts: dict[int, str],
    start_page: int,
    end_page: int,
) -> tuple[dict, list[str]]:
    """
    Verify quotes, fix page numbers where possible, flag failures.
    Returns (corrected_data, validation_errors).
    """
    errors: list[str] = []
    corrected = json.loads(json.dumps(data))

    for index, row in enumerate(corrected.get("annotations", [])):
        prefix = f"annotations[{index}]"
        page = row.get("page")
        quote = row.get("book_text", "")
        annotation = row.get("annotation", "")

        if quote == UNKNOWN:
            _add_flag(row, "quote_unknown")
        elif isinstance(page, int) and page in page_texts:
            if not quote_in_text(quote, page_texts[page]):
                found_page = find_quote_page(quote, page_texts)
                if found_page is not None:
                    row["page"] = found_page
                    _add_flag(row, "page_corrected")
                else:
                    row["book_text"] = UNKNOWN
                    _add_flag(row, "quote_not_found")
        else:
            found_page = find_quote_page(quote, page_texts)
            if found_page is not None:
                row["page"] = found_page
                _add_flag(row, "page_corrected")
            else:
                row["book_text"] = UNKNOWN
                _add_flag(row, "quote_not_found")

        note = (row.get("annotation") or "").strip()
        if not note:
            row["annotation"] = UNKNOWN
            _add_flag(row, "empty_annotation")
        elif note != UNKNOWN:
            word_count = len(note.split())
            lowered = note.casefold()
            if word_count < MIN_NOTE_WORDS:
                _add_flag(row, "short_annotation")
            if word_count > MAX_NOTE_WORDS:
                _add_flag(row, "long_annotation")
            if any(lowered.startswith(prefix_text) for prefix_text in GENERIC_PREFIXES):
                _add_flag(row, "generic_phrasing")

        if annotation != UNKNOWN and row.get("book_text") == UNKNOWN:
            row["annotation"] = UNKNOWN
            _add_flag(row, "annotation_unknown")

        page_value = row.get("page")
        if not isinstance(page_value, int) or page_value < start_page or page_value > end_page:
            _add_flag(row, "invalid_page")

        flags = row.get("validation_flags") or []
        if flags:
            errors.append(f"{prefix} flagged: {', '.join(flags)}")

    corrected["start_page"] = start_page
    corrected["end_page"] = end_page

    return corrected, errors


def has_blocking_errors(errors: list[str]) -> bool:
    """True for hard structural errors that soft repair cannot fix."""
    blocking_prefixes = (
        "Missing field",
        "must be an array",
        "must be an object",
        "missing field:",
    )
    for error in errors:
        if any(prefix in error for prefix in blocking_prefixes):
            return True
        if error.startswith("annotations[") and "missing field" in error:
            return True
    return False
