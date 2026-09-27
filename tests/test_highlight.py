import os
import sys

import fitz

_PDFER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PDFER")
if _PDFER not in sys.path:
    sys.path.insert(0, _PDFER)

from finder import QuoteTarget
from highlighter import DEFAULT_COLOR, NOTE_FILL_COLOR, free_margin_width, highlight_pdf

NOTE_SNIPPET = "Random assignment is meant to balance groups"


def _has_fill(page, color, tol=0.02) -> bool:
    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        if not fill:
            continue
        if all(abs(a - b) <= tol for a, b in zip(fill, color)):
            return True
    return False


def _assert_imbued_note(page, note_snippet: str) -> None:
    assert list(page.annots() or []) == []
    assert _has_fill(page, DEFAULT_COLOR)
    assert _has_fill(page, NOTE_FILL_COLOR)
    page_text = " ".join(page.get_text().split())
    assert note_snippet in page_text


def test_wide_margin_is_detected():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Participants completed a randomized trial of sleep.")
    assert free_margin_width(page) >= 72
    doc.close()


def test_full_width_text_is_a_narrow_margin():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(36, 36, page.rect.width - 20, 400),
        "word " * 400,
    )
    assert free_margin_width(page) < 72
    doc.close()


def test_narrow_page_gets_an_imbued_note(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    sentence = "Participants completed a randomized controlled experiment."
    rect = fitz.Rect(36, 72, page.rect.width - 20, 140)
    page.insert_textbox(rect, sentence + (" filler" * 40))
    source = tmp_path / "paper.pdf"
    doc.save(source)
    doc.close()

    output = tmp_path / "paper_highlighted.pdf"
    report = highlight_pdf(
        str(source),
        [
            QuoteTarget(
                page=1,
                book_text=sentence,
                annotation=(
                    "Random assignment is meant to balance groups so later "
                    "differences are easier to attribute to the treatment."
                ),
            )
        ],
        str(output),
    )
    assert report is not None
    assert report.highlighted_count == 1
    assert report.notes_count == 1
    saved = fitz.open(output)
    _assert_imbued_note(saved[0], NOTE_SNIPPET)
    saved.close()


def test_wide_margin_gets_an_imbued_note(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    sentence = "Participants completed a randomized controlled experiment."
    page.insert_text((72, 72), sentence)
    source = tmp_path / "wide.pdf"
    doc.save(source)
    doc.close()

    output = tmp_path / "wide_highlighted.pdf"
    report = highlight_pdf(
        str(source),
        [
            QuoteTarget(
                page=1,
                book_text=sentence,
                annotation=(
                    "Random assignment is meant to balance groups so later "
                    "differences are easier to attribute to the treatment."
                ),
            )
        ],
        str(output),
    )
    assert report is not None
    assert report.highlighted_count == 1
    assert report.notes_count == 1
    saved = fitz.open(output)
    _assert_imbued_note(saved[0], NOTE_SNIPPET)
    saved.close()
