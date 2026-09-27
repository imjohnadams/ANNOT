import re


def detect_chapter_from_layout(page) -> str | None:
    blocks = page.get_text("dict")["blocks"]
    page_height = page.rect.height
    candidates = []

    for block in blocks:
        if "lines" not in block:
            continue

        text = ""
        largest_font = 0

        for line in block["lines"]:
            for span in line["spans"]:
                text += span["text"].strip() + " "
                largest_font = max(largest_font, span["size"])

        text = text.strip()
        if not text:
            continue

        y_position = block["bbox"][1]
        words = len(text.split())

        if (
            y_position < page_height * 0.35
            and words <= 8
            and largest_font >= 13
            and not re.search(r"[.!?,;:]", text)
        ):
            candidates.append(text)

    return candidates[0] if candidates else None


CHAPTER_REGEX = re.compile(
    r"^(?:"
    r"(?:Chapter|CHAPTER|Part|PART)\s+(?:\d+|[IVXLCDM]+|\w+)"
    r"|"
    r"(?:\d+\.\s*)?(?:Chapter|CHAPTER)\s+\d+"
    r")",
    re.IGNORECASE,
)

_KNOWN_SECTION_NAMES = (
    "abstract",
    "introduction",
    "background",
    "related work",
    "literature review",
    "methods",
    "methodology",
    "materials and methods",
    "experimental setup",
    "results",
    "results and discussion",
    "discussion",
    "conclusion",
    "conclusions",
    "limitations",
    "references",
    "acknowledgments",
    "acknowledgements",
)

_KNOWN_SECTION_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+)?("
    + "|".join(re.escape(name) for name in _KNOWN_SECTION_NAMES)
    + r")$",
    re.IGNORECASE,
)

_NUMBERED_SECTION_RE = re.compile(
    r"^\d+(?:\.\d+){0,3}\.?\s+[A-Z][A-Za-z0-9](?:[A-Za-z0-9,'’\-]| ){1,70}$"
)


def detect_article_heading(page_text: str) -> str | None:
    """Return a research-article heading from the top lines of a page."""
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    for line in lines[:6]:
        if len(line) > 80:
            continue
        if _KNOWN_SECTION_RE.match(line):
            return line
        if (
            _NUMBERED_SECTION_RE.match(line)
            and len(line) >= 8
            and len(line.split()) <= 8
        ):
            return line
    return None


def detect_chapter_from_regex(page_text: str) -> str | None:
    for line in page_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue
        if CHAPTER_REGEX.match(stripped):
            return stripped
    return None
