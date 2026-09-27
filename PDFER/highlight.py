#!/usr/bin/env python3
"""Highlight ANNOT quotes onto a PDF. No AI — JSON/CSV + PDF only.

Examples:
  python highlight.py
  python highlight.py --pdf book.pdf --json book_master.json
  python highlight.py --pdf book.pdf --json book_master.json --out out/book_hl.pdf
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow `python PDFER/highlight.py` from repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from finder import load_targets
from highlighter import DEFAULT_COLOR, highlight_pdf, save_report


def prompt_confirm(message: str) -> bool:
    answer = input(f"\n{message} (Y/N): ").strip().lower()
    return answer == "y"


def prompt_existing_file(message: str) -> str:
    while True:
        path = input(f"\n{message}\n").strip().strip('"')
        if not path:
            print("Please enter a file path.")
            continue
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            print(f"File not found: {path}")
            continue
        return path


def prompt_output_path(default_path: str) -> str:
    if not prompt_confirm("Use a custom output path?"):
        return default_path

    while True:
        path = input("\nOutput PDF path:\n").strip().strip('"')
        if not path:
            print("Please enter a file path, or restart and choose N.")
            continue

        path = os.path.abspath(path)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            create = prompt_confirm(
                f"Folder does not exist:\n  {parent}\nCreate it?"
            )
            if create:
                os.makedirs(parent, exist_ok=True)
                return path
            continue
        return path


def _parse_color(value: str) -> tuple[float, float, float]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Color must be R,G,B with values 0–1 or 0–255")
    nums = [float(p) for p in parts]
    if any(n > 1.0 for n in nums):
        nums = [n / 255.0 for n in nums]
    if any(n < 0.0 or n > 1.0 for n in nums):
        raise argparse.ArgumentTypeError("Color channels must be in 0–1 (or 0–255)")
    return (nums[0], nums[1], nums[2])


def _default_output_path(pdf_path: str) -> str:
    stem, _ = os.path.splitext(pdf_path)
    return f"{stem}_highlighted.pdf"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Physically highlight book_text quotes from ANNOT JSON/CSV onto a PDF.",
    )
    parser.add_argument("--pdf", default=None, help="Source PDF path")
    parser.add_argument(
        "--json",
        dest="data",
        default=None,
        help="ANNOT master/chapter JSON (or CSV fallback)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output highlighted PDF (skips the Y/N custom-path prompt)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional JSON report of hits/misses",
    )
    parser.add_argument(
        "--color",
        type=_parse_color,
        default=DEFAULT_COLOR,
        help="Highlight RGB as r,g,b (0–1 or 0–255). Default: soft yellow",
    )
    parser.add_argument(
        "--neighbor-pages",
        action="store_true",
        help="If quote missing on listed page, also try adjacent pages",
    )
    parser.add_argument(
        "--no-notes",
        action="store_true",
        help="Skip margin notes (highlights only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print("=" * 62)
    print("PDFER — Quote Highlighter")
    print("=" * 62)

    if args.pdf:
        pdf_path = os.path.abspath(args.pdf)
        if not os.path.isfile(pdf_path):
            print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
            return 1
    else:
        pdf_path = prompt_existing_file("PDF file path:")

    if args.data:
        data_path = os.path.abspath(args.data)
        if not os.path.isfile(data_path):
            print(f"Error: data file not found: {data_path}", file=sys.stderr)
            return 1
    else:
        data_path = prompt_existing_file(
            "ANNOT JSON path (or CSV):\n"
            "(master or chapter file)"
        )

    default_out = _default_output_path(pdf_path)
    if args.out:
        output_path = os.path.abspath(args.out)
    else:
        output_path = prompt_output_path(default_out)

    targets = load_targets(data_path)
    if not targets:
        print("\nNo highlightable quotes found (empty or all [UNKNOWN]).")
        return 1

    print(f"\nPDF:      {pdf_path}")
    print(f"Data:     {data_path}")
    print(f"Quotes:   {len(targets)}")
    print(f"Output:   {output_path}")

    report = highlight_pdf(
        pdf_path,
        targets,
        output_path,
        color=args.color,
        neighbor_pages=args.neighbor_pages,
        add_notes=not args.no_notes,
    )

    print(f"\nHighlighted: {report.highlighted_count}")
    print(f"Notes:       {report.notes_count}")
    print(f"Misses:      {report.miss_count}")
    if report.highlighted_count == 0:
        print("Highlighted PDF not created.")

    if args.report:
        report_path = os.path.abspath(args.report)
        save_report(report, report_path)
        print(f"Report:      {report_path}")
    elif report.misses:
        print("Missed quotes (first 10):")
        for miss in report.misses[:10]:
            preview = miss.book_text.replace("\n", " ")
            if len(preview) > 80:
                preview = preview[:77] + "..."
            print(f"  p{miss.page}: [{miss.reason}] {preview}")

    print("\nDone.")
    return 0 if report.highlighted_count else 1


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        code = 1
    input("\nPress Enter to exit...")
    raise SystemExit(code)
