import re
from collections import Counter

from config import HEADER_FOOTER_MIN_PAGE_RATIO, HEADER_FOOTER_SCAN_LINES


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _page_lines(text: str) -> list[str]:
    return text.splitlines()


def detect_repeating_lines(
    pages: list[str],
    scan_lines: int = HEADER_FOOTER_SCAN_LINES,
) -> set[str]:
    if len(pages) < 2:
        return set()

    threshold = max(2, int(len(pages) * HEADER_FOOTER_MIN_PAGE_RATIO))
    header_counts: Counter[str] = Counter()
    footer_counts: Counter[str] = Counter()

    for text in pages:
        lines = [_normalize_line(l) for l in _page_lines(text) if _normalize_line(l)]
        if not lines:
            continue

        for line in lines[:scan_lines]:
            header_counts[line] += 1
        for line in lines[-scan_lines:]:
            footer_counts[line] += 1

    repeating = set()
    for line, count in header_counts.items():
        if count >= threshold and len(line) >= 3:
            repeating.add(line)
    for line, count in footer_counts.items():
        if count >= threshold and len(line) >= 3:
            repeating.add(line)

    return repeating


def strip_headers_footers(text: str, repeating: set[str]) -> str:
    if not repeating:
        return text.strip()

    lines = _page_lines(text)
    cleaned = []

    for line in lines:
        normalized = _normalize_line(line)
        if normalized and normalized in repeating:
            continue
        cleaned.append(line)

    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
