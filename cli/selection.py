import re


def parse_chapter_selection(user_input: str) -> list[int]:
    """
    Parse chapter selection strings such as:
      5
      4-7
      5, 7, 9, 16
      2-4, 6-12
      1, 3, 5-10
    """
    cleaned = user_input.strip()
    if not cleaned:
        raise ValueError("No chapters entered.")

    selected: set[int] = set()

    for piece in cleaned.split(","):
        part = piece.strip()
        if not part:
            continue

        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                raise ValueError(f"Invalid range (start > end): '{part}'")
            selected.update(range(start, end + 1))
            continue

        for token in part.split():
            if not token.isdigit():
                raise ValueError(f"Invalid chapter number: '{token}'")
            selected.add(int(token))

    if not selected:
        raise ValueError("No chapters entered.")

    return sorted(selected)


def filter_valid_chapters(
    selected: list[int],
    available: set[int],
) -> tuple[list[int], list[int]]:
    valid = [n for n in selected if n in available]
    invalid = [n for n in selected if n not in available]
    return valid, invalid
