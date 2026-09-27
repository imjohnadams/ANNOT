"""Thin adapter: run PDFER highlight from the ANNOT pipeline."""

from __future__ import annotations

import os
import sys

_PDFER_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "PDFER",
)
if _PDFER_ROOT not in sys.path:
    sys.path.insert(0, _PDFER_ROOT)

from finder import load_targets  # noqa: E402
from highlighter import highlight_pdf  # noqa: E402


def run_highlight(
    pdf_path: str,
    master_json_path: str,
    output_path: str,
    *,
    add_notes: bool = True,
    neighbor_pages: bool = False,
):
    """Highlight quotes from master JSON onto the PDF. Returns HighlightReport."""
    targets = load_targets(master_json_path)
    if not targets:
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    return highlight_pdf(
        pdf_path,
        targets,
        output_path,
        neighbor_pages=neighbor_pages,
        add_notes=add_notes,
    )
