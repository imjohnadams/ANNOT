#!/usr/bin/env python3
"""Compare source-text selections between two annotation CSV runs."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

UNKNOWN = "[UNKNOWN]"
WHITESPACE_RE = re.compile(r"\s+")
PREVIEW_LEN = 72


def normalize_quote(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text.strip()).casefold()


def _field_key(name: str) -> str:
    return name.casefold().replace(" ", "").replace("_", "")


def load_quotes_by_page(path: Path) -> dict[int, list[str]]:
    """Load page + source text from chapter or master CSV. Skip empty/[UNKNOWN]."""
    by_page: dict[int, list[str]] = defaultdict(list)

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"No header row in {path}")

        field_map = {_field_key(name): name for name in reader.fieldnames}
        page_key = field_map.get("page")
        text_key = field_map.get("sourcetext") or field_map.get("booktext")

        if not page_key or not text_key:
            raise ValueError(
                f"{path} must have page and source_text (or Book Text) columns "
                f"(found: {', '.join(reader.fieldnames)})"
            )

        for row in reader:
            raw_page = (row.get(page_key) or "").strip()
            raw_text = row.get(text_key) or ""
            if not raw_page:
                continue

            try:
                page = int(raw_page)
            except ValueError as exc:
                raise ValueError(f"Invalid page value {raw_page!r} in {path}") from exc

            normalized = normalize_quote(raw_text)
            if not normalized or normalized == UNKNOWN.casefold():
                continue

            by_page[page].append(normalized)

    return dict(by_page)


def match_score(a: str, b: str, threshold: float) -> float | None:
    """Return similarity score if quotes match, else None."""
    if a in b or b in a:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        return len(shorter) / len(longer) if longer else 1.0

    ratio = SequenceMatcher(None, a, b).ratio()
    if ratio >= threshold:
        return ratio
    return None


def pair_quotes(
    quotes_a: list[str],
    quotes_b: list[str],
    threshold: float,
) -> tuple[int, list[str], list[str]]:
    """Greedy 1:1 pairing. Returns (matched_count, leftover_a, leftover_b)."""
    candidates: list[tuple[float, int, int]] = []
    for i, a in enumerate(quotes_a):
        for j, b in enumerate(quotes_b):
            score = match_score(a, b, threshold)
            if score is not None:
                candidates.append((score, i, j))

    candidates.sort(key=lambda item: item[0], reverse=True)

    used_a: set[int] = set()
    used_b: set[int] = set()
    matched = 0

    for _score, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        matched += 1

    leftover_a = [q for i, q in enumerate(quotes_a) if i not in used_a]
    leftover_b = [q for j, q in enumerate(quotes_b) if j not in used_b]
    return matched, leftover_a, leftover_b


def page_status(matched: int, total_a: int, total_b: int) -> str:
    total = max(total_a, total_b)
    if total_a == 0 and total_b == 0:
        return "EMPTY"
    if matched == 0:
        return "NO_MATCH"
    if matched == total_a and matched == total_b:
        return "MATCH"
    return "PARTIAL"


def preview(text: str) -> str:
    if len(text) <= PREVIEW_LEN:
        return text
    return text[: PREVIEW_LEN - 3] + "..."


def dice_percent(matched_pairs: int, count_a: int, count_b: int) -> float:
    if count_a == 0 and count_b == 0:
        return 100.0
    if count_a == 0 or count_b == 0:
        return 0.0
    return 200.0 * matched_pairs / (count_a + count_b)


def compare(
    path_a: Path,
    path_b: Path,
    threshold: float,
) -> None:
    by_page_a = load_quotes_by_page(path_a)
    by_page_b = load_quotes_by_page(path_b)

    pages = sorted(set(by_page_a) | set(by_page_b))
    total_matched = 0
    total_a = 0
    total_b = 0

    for page in pages:
        quotes_a = by_page_a.get(page, [])
        quotes_b = by_page_b.get(page, [])
        matched, leftover_a, leftover_b = pair_quotes(quotes_a, quotes_b, threshold)

        total_matched += matched
        total_a += len(quotes_a)
        total_b += len(quotes_b)

        status = page_status(matched, len(quotes_a), len(quotes_b))
        denom = max(len(quotes_a), len(quotes_b))
        line = f"Page {page}: {status:<8} ({matched}/{denom} matched)"

        if status in {"PARTIAL", "NO_MATCH"}:
            line += f"  | only in A: {len(leftover_a)} | only in B: {len(leftover_b)}"

        print(line)

        if status in {"PARTIAL", "NO_MATCH"}:
            for quote in leftover_a:
                print(f"    A only: {preview(quote)}")
            for quote in leftover_b:
                print(f"    B only: {preview(quote)}")

    percent = dice_percent(total_matched, total_a, total_b)
    print("---")
    if total_a == 0 and total_b == 0:
        print(
            f"Overall: {percent:.1f}% similar "
            "(no usable quotes in either file)"
        )
    else:
        print(
            f"Overall: {percent:.1f}% similar "
            f"({total_matched} matched pairs; "
            f"{total_a} quotes in A, {total_b} quotes in B)"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Book Text selections between two annotation CSV runs. "
            "Quotes on the same page match if one contains the other or "
            "their similarity ratio meets --threshold."
        )
    )
    parser.add_argument("csv_a", type=Path, help="First run CSV (A)")
    parser.add_argument("csv_b", type=Path, help="Second run CSV (B)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum SequenceMatcher ratio for non-substring matches (default: 0.85)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not 0.0 <= args.threshold <= 1.0:
        print("error: --threshold must be between 0 and 1", file=sys.stderr)
        return 2

    for label, path in (("A", args.csv_a), ("B", args.csv_b)):
        if not path.is_file():
            print(f"error: CSV {label} not found: {path}", file=sys.stderr)
            return 2

    try:
        compare(args.csv_a, args.csv_b, args.threshold)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
