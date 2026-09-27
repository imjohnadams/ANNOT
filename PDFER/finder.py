"""Load quote targets from ANNOT JSON (or CSV) for highlighting."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass

UNKNOWN = "[UNKNOWN]"


@dataclass(frozen=True)
class QuoteTarget:
    page: int
    book_text: str
    annotation: str = ""
    annotation_type: str | None = None
    chapter_number: int | None = None
    chapter_title: str = ""
    source: str = ""


def _is_skip_quote(quote: str) -> bool:
    text = (quote or "").strip()
    return not text or text == UNKNOWN


def _row_to_target(
    row: dict,
    *,
    chapter_number: int | None = None,
    chapter_title: str = "",
    source: str = "",
) -> QuoteTarget | None:
    page = row.get("page")
    book_text = row.get("book_text", "")

    if isinstance(page, str) and page.strip().isdigit():
        page = int(page.strip())

    if not isinstance(page, int) or page < 1:
        return None
    if _is_skip_quote(book_text):
        return None

    annotation_type = row.get("annotation_type")
    if annotation_type == "":
        annotation_type = None

    return QuoteTarget(
        page=page,
        book_text=str(book_text),
        annotation=str(row.get("annotation", "") or ""),
        annotation_type=annotation_type,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        source=source,
    )


def load_targets_from_json(path: str) -> list[QuoteTarget]:
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    targets: list[QuoteTarget] = []
    source = os.path.basename(path)

    # Master JSON: { chapters: [ { annotations: [...] }, ... ] }
    if isinstance(payload, dict) and "chapters" in payload:
        for chapter in payload.get("chapters", []):
            chapter_number = chapter.get("chapter_number")
            chapter_title = str(chapter.get("chapter_title", "") or "")
            for row in chapter.get("annotations", []):
                target = _row_to_target(
                    row,
                    chapter_number=chapter_number if isinstance(chapter_number, int) else None,
                    chapter_title=chapter_title,
                    source=source,
                )
                if target is not None:
                    targets.append(target)
        return targets

    # Chapter JSON: { annotations: [...] }
    if isinstance(payload, dict) and "annotations" in payload:
        chapter_number = payload.get("chapter_number")
        chapter_title = str(payload.get("chapter_title", "") or "")
        for row in payload.get("annotations", []):
            target = _row_to_target(
                row,
                chapter_number=chapter_number if isinstance(chapter_number, int) else None,
                chapter_title=chapter_title,
                source=source,
            )
            if target is not None:
                targets.append(target)
        return targets

    # Bare list of annotation objects
    if isinstance(payload, list):
        for row in payload:
            if not isinstance(row, dict):
                continue
            target = _row_to_target(row, source=source)
            if target is not None:
                targets.append(target)
        return targets

    raise ValueError(
        f"Unrecognized JSON shape in {path}. "
        "Expected master JSON, chapter JSON, or a list of annotations."
    )


def load_targets_from_csv(path: str) -> list[QuoteTarget]:
    """Fallback loader. Prefer JSON — CSV can mangle quotes with commas/newlines."""
    targets: list[QuoteTarget] = []
    source = os.path.basename(path)

    with open(path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            normalized = {
                "page": row.get("page") or row.get("Page"),
                "book_text": (
                    row.get("source_text")
                    or row.get("Source Text")
                    or row.get("book_text")
                    or row.get("Book Text")
                    or ""
                ),
                "annotation": row.get("annotation") or row.get("Annotation") or "",
                "annotation_type": (
                    row.get("category")
                    or row.get("Category")
                    or row.get("annotation_type")
                    or row.get("Annotation Type")
                ),
            }
            chapter_raw = row.get("chapter") or row.get("Chapter")
            chapter_number = None
            if chapter_raw is not None and str(chapter_raw).strip().isdigit():
                chapter_number = int(str(chapter_raw).strip())

            target = _row_to_target(
                normalized,
                chapter_number=chapter_number,
                chapter_title=str(
                    row.get("chapter_title") or row.get("Chapter Title") or ""
                ),
                source=source,
            )
            if target is not None:
                targets.append(target)

    return targets


def load_targets(path: str) -> list[QuoteTarget]:
    lower = path.lower()
    if lower.endswith(".json"):
        return load_targets_from_json(path)
    if lower.endswith(".csv"):
        return load_targets_from_csv(path)
    raise ValueError(f"Unsupported input file type: {path} (use .json or .csv)")
