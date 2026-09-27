import pytest

from cli.selection import filter_valid_chapters, parse_chapter_selection


def test_single_number():
    assert parse_chapter_selection("5") == [5]


def test_range_and_list():
    assert parse_chapter_selection("2-4, 6-7") == [2, 3, 4, 6, 7]
    assert parse_chapter_selection("5, 7, 9") == [5, 7, 9]
    assert parse_chapter_selection("4 - 7") == [4, 5, 6, 7]


def test_invalid_range():
    with pytest.raises(ValueError):
        parse_chapter_selection("8-3")
    with pytest.raises(ValueError):
        parse_chapter_selection("abc")
    with pytest.raises(ValueError):
        parse_chapter_selection("   ")


def test_filter_keeps_order():
    valid, invalid = filter_valid_chapters([1, 4, 2], {1, 2})
    assert valid == [1, 2]
    assert invalid == [4]
