from dataclasses import dataclass, field


@dataclass
class Page:
    number: int
    text: str
    raw_text: str = ""


@dataclass
class Chapter:
    number: int
    title: str
    start_page: int
    end_page: int
    detection_method: str = ""


@dataclass
class Book:
    title: str
    filepath: str
    source_filepath: str
    total_pages: int
    author: str = ""
    output_root: str | None = None
    pages: list[Page] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def get_chapter_text(self, chapter: Chapter) -> str:
        parts = []
        for page in self.pages:
            if chapter.start_page <= page.number <= chapter.end_page:
                parts.append(f"=== PAGE {page.number} ===\n\n")
                parts.append(page.text)
                parts.append("\n\n")
        return "".join(parts)

    def get_chapter_char_count(self, chapter: Chapter) -> int:
        return sum(
            len(page.text)
            for page in self.pages
            if chapter.start_page <= page.number <= chapter.end_page
        )

    def get_chapter_page_count(self, chapter: Chapter) -> int:
        return chapter.end_page - chapter.start_page + 1

    def get_page_text(self, page_number: int) -> str:
        for page in self.pages:
            if page.number == page_number:
                return page.text
        return ""
