from validate.verifier import (
    cap_annotations_to_density,
    quote_in_text,
    validate_structure,
    verify_and_fix_annotations,
)


def test_quote_matches_collapsed_whitespace():
    page = "Participants completed\na randomized trial."
    assert quote_in_text("Participants completed a randomized trial.", page)


def test_density_cap_does_not_pad():
    data = {
        "chapter_number": 1,
        "chapter_title": "Methods",
        "start_page": 1,
        "end_page": 2,
        "annotations": [
            {
                "page": 1,
                "book_text": "first quote",
                "annotation": "Explains the first design choice in the study.",
                "category": "METHOD",
                "grounding": "source_fact",
            },
            {
                "page": 1,
                "book_text": "second quote",
                "annotation": "Explains a second design choice in the study.",
                "category": "METHOD",
                "grounding": "source_fact",
            },
            {
                "page": 1,
                "book_text": "first quote",
                "annotation": "Repeats the first design choice without a new point.",
                "category": "METHOD",
                "grounding": "source_fact",
            },
        ],
    }
    capped, report = cap_annotations_to_density(data, 1, 2, quotes_per_page=1)
    pages = [row["page"] for row in capped["annotations"]]
    assert pages == [1]
    assert report["trimmed"] == 1
    assert report["dropped_duplicate"] == 1
    assert report.get("padded", 0) == 0
    errors = validate_structure(capped, 1, 2, quotes_per_page=1)
    assert errors == []


def test_unknown_quote_does_not_displace_a_real_one():
    data = {
        "chapter_number": 1,
        "chapter_title": "Methods",
        "start_page": 1,
        "end_page": 1,
        "annotations": [
            {
                "page": 1,
                "book_text": "not on the page",
                "annotation": "This would be an unsupported note.",
                "category": "RESULT",
                "grounding": "source_fact",
            },
            {
                "page": 1,
                "book_text": "randomized trial",
                "annotation": "Names the study design used in the experiment.",
                "category": "METHOD",
                "grounding": "source_fact",
            },
        ],
    }
    prepared, _ = cap_annotations_to_density(
        data, 1, 1, quotes_per_page=1, apply_limit=False
    )
    corrected, _ = verify_and_fix_annotations(
        prepared,
        {1: "Participants completed a randomized trial of sleep."},
        1,
        1,
    )
    capped, report = cap_annotations_to_density(corrected, 1, 1, quotes_per_page=1)
    assert [row["book_text"] for row in capped["annotations"]] == ["randomized trial"]
    assert report["trimmed"] == 1


def test_quote_not_found_clears_annotation():
    data = {
        "annotations": [
            {
                "page": 1,
                "book_text": "not on the page",
                "annotation": "This would be an unsupported note.",
                "category": "RESULT",
                "grounding": "source_fact",
            }
        ]
    }
    corrected, errors = verify_and_fix_annotations(
        data,
        {1: "The authors report a correlation only."},
        1,
        1,
    )
    row = corrected["annotations"][0]
    assert row["book_text"] == "[UNKNOWN]"
    assert row["annotation"] == "[UNKNOWN]"
    assert errors


def test_page_corrected_when_quote_is_on_another_page():
    data = {
        "annotations": [
            {
                "page": 1,
                "book_text": "effect size was large",
                "annotation": "The authors describe the effect as large.",
                "category": "RESULT",
                "grounding": "source_fact",
            }
        ]
    }
    corrected, _errors = verify_and_fix_annotations(
        data,
        {
            1: "Methods are described here.",
            2: "In the sample, the effect size was large.",
        },
        1,
        2,
    )
    assert corrected["annotations"][0]["page"] == 2
