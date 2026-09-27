"""Runtime annotation density and quality settings."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    DEFAULT_QUALITY,
    DEFAULT_QUOTES_PER_PAGE,
    MAX_QUOTES_PER_PAGE,
    MIN_QUOTES_PER_PAGE,
    QUALITY_CHOICES,
    QUALITY_SKIP_PAGE_THRESHOLD,
    QPP_HIGH_QUALITY_WARN_THRESHOLD,
)


@dataclass(frozen=True)
class AnnotationSettings:
    quotes_per_page: int = DEFAULT_QUOTES_PER_PAGE
    quality: str = DEFAULT_QUALITY
    quality_was_skipped: bool = False

    def __post_init__(self) -> None:
        if not (MIN_QUOTES_PER_PAGE <= self.quotes_per_page <= MAX_QUOTES_PER_PAGE):
            raise ValueError(
                f"quotes_per_page must be {MIN_QUOTES_PER_PAGE}-{MAX_QUOTES_PER_PAGE}"
            )
        if self.quality not in QUALITY_CHOICES.values():
            raise ValueError(f"quality must be one of {sorted(QUALITY_CHOICES.values())}")

    @property
    def quality_label(self) -> str:
        return self.quality.capitalize()

    def expected_annotation_count(self, page_count: int) -> int:
        return page_count * self.quotes_per_page

    def should_warn_dense_high(self) -> bool:
        return (
            self.quotes_per_page >= QPP_HIGH_QUALITY_WARN_THRESHOLD
            and self.quality == "high"
        )

    def to_metadata(self) -> dict:
        return {
            "quotes_per_page": self.quotes_per_page,
            "quality": self.quality,
            "quality_was_skipped": self.quality_was_skipped,
        }


def should_skip_quality_prompt(selected_page_count: int) -> bool:
    return selected_page_count >= QUALITY_SKIP_PAGE_THRESHOLD


def build_settings_overlay(settings: AnnotationSettings) -> str:
    qpp = settings.quotes_per_page
    quality = settings.quality

    density = f"""
# RUNTIME DENSITY

Maximum annotations per page: {qpp}.

This is a coverage cap, not a quota.

- Return at most {qpp} annotation(s) on any single page.
- Total annotations must be less than or equal to (number of pages in range) × {qpp}.
- Return fewer, including zero on a page, when the page has nothing worth a research note.
- Do not write filler to approach the cap.
- Prefer distinct quotes on the same page.
- Within a page, order notes by quote order. Across the range, keep pages in ascending order.
- At this density, cover {"only the major claims, methods, and results" if qpp <= 2 else "major points plus supporting terms, assumptions, evidence, and connections" if qpp <= 5 else "a detailed reading, still skipping repetition and boilerplate"}.
""".strip()

    if quality == "low":
        quality_block = """
# RUNTIME QUALITY — LOW

Explain what the passage means.

- About 15-40 words.
- Focus on the claim, term, or result in the quote.
- Skip minor sentences.
- Stay on what the text says. Use grounding `interpretation` or `uncertain` when you go beyond it.
""".strip()
    elif quality == "high":
        quality_block = """
# RUNTIME QUALITY — HIGH

Explain the concept, the evidence, the method, the assumptions, and what the passage does not establish, when those are actually present.

- About 40-90 words. Shorter if the point is simple.
- Say what the author is doing, not only what the words repeat.
- Explain a named method or test in the context of this document.
- Do not add statistics, citations, or design details that are not in the supplied text.
- Label interpretations as interpretations.
""".strip()
    else:
        quality_block = """
# RUNTIME QUALITY — MEDIUM

Explain the passage and why it matters in this document.

- About 25-60 words.
- Cover the claim plus the supporting reason, method, or result when the quote contains one.
- Define a specialized term when the note depends on it.
- Do not turn the note into a summary of the whole section.
""".strip()

    return density + "\n\n" + quality_block
