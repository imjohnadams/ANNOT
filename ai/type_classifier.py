"""Validate research categories and grounding labels from the model."""

from config import (
    ANNOTATION_CATEGORIES,
    FALLBACK_CATEGORY,
    FALLBACK_GROUNDING,
    GROUNDING_STATUSES,
    UNKNOWN,
)


def _flags(row: dict) -> list[str]:
    flags = list(row.get("validation_flags") or [])
    row["validation_flags"] = flags
    return flags


def _add_flag(row: dict, flag: str) -> None:
    flags = _flags(row)
    if flag not in flags:
        flags.append(flag)


def normalize_row(row: dict) -> dict:
    """Coerce category and grounding onto the allowed sets."""
    category = row.get("category")
    if not isinstance(category, str) or category not in ANNOTATION_CATEGORIES:
        row["category"] = FALLBACK_CATEGORY
        _add_flag(row, "category_invalid")

    grounding = row.get("grounding")
    if not isinstance(grounding, str) or grounding not in GROUNDING_STATUSES:
        row["grounding"] = FALLBACK_GROUNDING
        _add_flag(row, "grounding_invalid")

    if row.get("book_text") == UNKNOWN or row.get("annotation") == UNKNOWN:
        row["grounding"] = FALLBACK_GROUNDING
        if row.get("category") not in ANNOTATION_CATEGORIES:
            row["category"] = FALLBACK_CATEGORY

    return row


def apply_types(data: dict) -> dict:
    for row in data.get("annotations", []):
        if isinstance(row, dict):
            normalize_row(row)
    return data
