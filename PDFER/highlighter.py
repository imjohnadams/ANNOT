"""Search PDF text and apply page-content highlights + right-margin notes."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass

import fitz

from finder import UNKNOWN, QuoteTarget

# Soft yellow highlight (RGB 0–1)
DEFAULT_COLOR = (1.0, 0.92, 0.23)
HIGHLIGHT_FILL_OPACITY = 0.35
NOTE_FILL_COLOR = (1.0, 1.0, 1.0)
NOTE_FILL_OPACITY = 1.0
NOTE_TEXT_COLOR = (0.0, 0.0, 0.0)
NOTE_BORDER_COLOR = (0.15, 0.15, 0.15)
NOTE_BORDER_WIDTH = 0.5
NOTE_FONTNAME = "helv"
NOTE_FONTSIZE_MAX = 8.0
NOTE_FONTSIZE_MIN = 6.0
NOTE_PAD = 3.0
MARGIN_PREFERRED = 120.0
MARGIN_MIN_WIDTH = 72.0
HEADER_FOOTER_FRAC = 0.08
_LINE_Y_TOLERANCE = 2.0
_GAP_X_TOLERANCE = 3.0


@dataclass
class HighlightHit:
    page: int
    book_text: str
    rect_count: int
    method: str
    chapter_number: int | None = None
    note_added: bool = False


@dataclass
class HighlightMiss:
    page: int
    book_text: str
    reason: str
    chapter_number: int | None = None


@dataclass
class HighlightReport:
    hits: list[HighlightHit]
    misses: list[HighlightMiss]
    highlighted_count: int
    notes_count: int = 0
    skipped_unknown: int = 0

    @property
    def miss_count(self) -> int:
        return len(self.misses)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _quote_variants(quote: str) -> list[str]:
    """Generate deterministic search strings without inventing content."""
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        if value and value not in seen:
            seen.add(value)
            variants.append(value)

    add(quote)
    add(quote.strip())
    add(normalize_whitespace(quote))

    # Common PDF/typography substitutions
    for src, dst in (
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u00a0", " "),
        ("\ufb01", "fi"),
        ("\ufb02", "fl"),
    ):
        if src in quote:
            add(quote.replace(src, dst))
            add(normalize_whitespace(quote.replace(src, dst)))

    return variants


def _rects_from_search(page: fitz.Page, quote: str) -> list[fitz.Rect]:
    for variant in _quote_variants(quote):
        rects = page.search_for(variant)
        if rects:
            return list(rects)
    return []


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\S+", normalize_whitespace(text))


def _rects_from_word_sequence(page: fitz.Page, quote: str) -> list[fitz.Rect]:
    """Match quote as a contiguous word sequence (handles line-break whitespace)."""
    needle = _tokenize(quote)
    if not needle:
        return []

    words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, word_no
    if not words:
        return []

    haystack = [normalize_whitespace(w[4]) for w in words]
    n = len(needle)
    if n > len(haystack):
        return []

    for start in range(len(haystack) - n + 1):
        window = haystack[start : start + n]
        if window == needle:
            return [fitz.Rect(words[i][:4]) for i in range(start, start + n)]

        # Allow hyphenated line-break joins: "some-" + "thing" vs "something"
        joined_ok = True
        hi = start
        for token in needle:
            if hi >= len(haystack):
                joined_ok = False
                break
            piece = haystack[hi]
            if piece == token:
                hi += 1
                continue
            if piece.endswith("-") and hi + 1 < len(haystack):
                merged = piece[:-1] + haystack[hi + 1]
                if merged == token:
                    hi += 2
                    continue
            joined_ok = False
            break

        if joined_ok and hi > start:
            return [fitz.Rect(words[i][:4]) for i in range(start, hi)]

    return []


def find_quote_rects(page: fitz.Page, quote: str) -> tuple[list[fitz.Rect], str]:
    rects = _rects_from_search(page, quote)
    if rects:
        return rects, "search_for"

    rects = _rects_from_word_sequence(page, quote)
    if rects:
        return rects, "word_sequence"

    return [], "not_found"


def _usable_note(text: str) -> str | None:
    note = (text or "").strip()
    if not note or note == UNKNOWN:
        return None
    return note


def _merge_line_rects(rects: list[fitz.Rect]) -> list[fitz.Rect]:
    """Union rects that sit on the same line and overlap or nearly touch horizontally."""
    if not rects:
        return []
    ordered = sorted(rects, key=lambda r: ((r.y0 + r.y1) / 2, r.x0))
    merged: list[fitz.Rect] = [fitz.Rect(ordered[0])]
    for rect in ordered[1:]:
        current = merged[-1]
        same_line = abs((rect.y0 + rect.y1) / 2 - (current.y0 + current.y1) / 2) <= _LINE_Y_TOLERANCE
        nearly_touch = rect.x0 <= current.x1 + _GAP_X_TOLERANCE
        if same_line and nearly_touch:
            merged[-1] = current | rect
        else:
            merged.append(fitz.Rect(rect))
    return merged


def _apply_highlight(
    page: fitz.Page,
    rects: list[fitz.Rect],
    color: tuple[float, float, float],
) -> bool:
    """Paint yellow fills into the page content stream (visible in all viewers)."""
    if not rects:
        return False
    for rect in _merge_line_rects(rects):
        page.draw_rect(
            rect,
            color=None,
            fill=color,
            width=0,
            overlay=True,
            fill_opacity=HIGHLIGHT_FILL_OPACITY,
        )
    return True


def free_margin_width(page: fitz.Page) -> float:
    """Points of unused space to the right of the body text."""
    page_rect = page.rect
    top = page_rect.y0 + page_rect.height * HEADER_FOOTER_FRAC
    bottom = page_rect.y1 - page_rect.height * HEADER_FOOTER_FRAC
    body_max_x = page_rect.x0
    for word in page.get_text("words"):
        x1, y0, y1 = word[2], word[1], word[3]
        if y1 < top or y0 > bottom:
            continue
        body_max_x = max(body_max_x, x1)
    x1 = page_rect.x1 - 6
    return max(0.0, x1 - (body_max_x + 8))


def _right_margin_band(page: fitz.Page) -> tuple[float, float]:
    """Return (x0, x1) for a right-edge note column.

    Uses unused margin when it is at least MARGIN_MIN_WIDTH. On tight pages,
    still uses a MARGIN_MIN_WIDTH column that may overlap body text.
    """
    page_rect = page.rect
    x1 = page_rect.x1 - 6
    free = free_margin_width(page)
    if free >= MARGIN_MIN_WIDTH:
        width = min(free, MARGIN_PREFERRED)
    else:
        width = MARGIN_MIN_WIDTH
    width = min(width, max(12.0, page_rect.width - 12))
    x0 = x1 - width
    return x0, x1


def _y_overlap(a: fitz.Rect, b: fitz.Rect, pad: float = 2.0) -> bool:
    return not (a.y1 + pad <= b.y0 or b.y1 + pad <= a.y0)


def _estimate_note_height(note: str, width: float, fontsize: float) -> float:
    inner = max(width - 2 * NOTE_PAD, 12.0)
    space = fitz.get_text_length(" ", fontname=NOTE_FONTNAME, fontsize=fontsize)
    lines = 1
    current = 0.0
    for word in note.split() or [note]:
        word_w = fitz.get_text_length(word, fontname=NOTE_FONTNAME, fontsize=fontsize)
        if current == 0:
            current = word_w
            continue
        if current + space + word_w <= inner:
            current += space + word_w
        else:
            lines += 1
            current = word_w
            extra = max(0, math.ceil(word_w / inner) - 1)
            lines += extra
    return max(lines, 1) * (fontsize + 4) + 2 * NOTE_PAD + 2


def _place_note_rect(
    preferred: fitz.Rect,
    occupied: list[fitz.Rect],
    page_rect: fitz.Rect,
) -> fitz.Rect:
    height = preferred.height
    min_y = page_rect.y0 + 4
    max_bottom = page_rect.y1 - 4
    if height > max_bottom - min_y:
        height = max_bottom - min_y
    x0, x1 = preferred.x0, preferred.x1

    def make(y0: float) -> fitz.Rect:
        y0 = min(max(y0, min_y), max(min_y, max_bottom - height))
        return fitz.Rect(x0, y0, x1, y0 + height)

    rect = make(preferred.y0)
    for _ in range(24):
        hit = next((other for other in occupied if _y_overlap(rect, other)), None)
        if hit is None:
            return rect
        rect = make(hit.y1 + 3)

    rect = make(preferred.y0)
    for _ in range(24):
        hit = next((other for other in occupied if _y_overlap(rect, other)), None)
        if hit is None:
            return rect
        rect = make(hit.y0 - height - 3)
    return rect


def _apply_margin_note(
    page: fitz.Page,
    rects: list[fitz.Rect],
    note: str,
    occupied: list[fitz.Rect],
) -> bool:
    """Draw the note as page-content text in a white right-edge box."""
    if not rects or not note:
        return False

    x0, x1 = _right_margin_band(page)
    width = x1 - x0
    fontsize = NOTE_FONTSIZE_MAX
    height = _estimate_note_height(note, width, fontsize) + 4
    max_height = page.rect.height * 0.35
    while height > max_height and fontsize > NOTE_FONTSIZE_MIN:
        fontsize -= 0.5
        height = _estimate_note_height(note, width, fontsize) + 4

    preferred = fitz.Rect(x0, rects[0].y0, x1, rects[0].y0 + height)
    box = _place_note_rect(preferred, occupied, page.rect)
    page.draw_rect(
        box,
        color=NOTE_BORDER_COLOR,
        fill=NOTE_FILL_COLOR,
        width=NOTE_BORDER_WIDTH,
        overlay=True,
        fill_opacity=NOTE_FILL_OPACITY,
    )
    text_box = fitz.Rect(
        box.x0 + NOTE_PAD,
        box.y0 + NOTE_PAD,
        box.x1 - NOTE_PAD,
        box.y1 - NOTE_PAD,
    )
    page.insert_textbox(
        text_box,
        note,
        fontsize=fontsize,
        fontname=NOTE_FONTNAME,
        color=NOTE_TEXT_COLOR,
        align=fitz.TEXT_ALIGN_LEFT,
    )
    occupied.append(box)
    return True


def highlight_pdf(
    pdf_path: str,
    targets: list[QuoteTarget],
    output_path: str,
    *,
    color: tuple[float, float, float] = DEFAULT_COLOR,
    neighbor_pages: bool = False,
    add_notes: bool = True,
) -> HighlightReport:
    doc = fitz.open(pdf_path)
    hits: list[HighlightHit] = []
    misses: list[HighlightMiss] = []
    notes_count = 0
    occupied_by_page: dict[int, list[fitz.Rect]] = {}
    wrapped_pages: set[int] = set()

    try:
        for target in targets:
            page_index = target.page - 1
            if page_index < 0 or page_index >= len(doc):
                misses.append(
                    HighlightMiss(
                        page=target.page,
                        book_text=target.book_text,
                        reason="page_out_of_range",
                        chapter_number=target.chapter_number,
                    )
                )
                continue

            page = doc[page_index]
            rects, method = find_quote_rects(page, target.book_text)

            if not rects and neighbor_pages:
                for offset in (-1, 1):
                    alt = page_index + offset
                    if 0 <= alt < len(doc):
                        rects, method = find_quote_rects(doc[alt], target.book_text)
                        if rects:
                            page = doc[alt]
                            page_index = alt
                            method = f"{method}_neighbor_p{alt + 1}"
                            break

            if not rects:
                misses.append(
                    HighlightMiss(
                        page=target.page,
                        book_text=target.book_text,
                        reason="quote_not_found",
                        chapter_number=target.chapter_number,
                    )
                )
                continue

            note = _usable_note(target.annotation) if add_notes else None
            note_added = False

            if page_index not in wrapped_pages:
                page.wrap_contents()
                wrapped_pages.add(page_index)

            highlighted = _apply_highlight(page, rects, color)
            if not highlighted:
                misses.append(
                    HighlightMiss(
                        page=target.page,
                        book_text=target.book_text,
                        reason="highlight_failed",
                        chapter_number=target.chapter_number,
                    )
                )
                continue

            if note is not None:
                occupied = occupied_by_page.setdefault(page_index, [])
                note_added = _apply_margin_note(page, rects, note, occupied)

            if note_added:
                notes_count += 1

            hits.append(
                HighlightHit(
                    page=target.page,
                    book_text=target.book_text,
                    rect_count=len(rects),
                    method=method,
                    chapter_number=target.chapter_number,
                    note_added=note_added,
                )
            )

        if hits:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    return HighlightReport(
        hits=hits,
        misses=misses,
        highlighted_count=len(hits),
        notes_count=notes_count,
    )


def save_report(report: HighlightReport, path: str) -> None:
    payload = {
        "highlighted_count": report.highlighted_count,
        "notes_count": report.notes_count,
        "miss_count": report.miss_count,
        "hits": [asdict(hit) for hit in report.hits],
        "misses": [asdict(miss) for miss in report.misses],
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
