from ai.type_classifier import normalize_row


def test_invalid_category_falls_back():
    row = normalize_row(
        {
            "category": "PLOT",
            "grounding": "source_fact",
            "annotation": "A note.",
            "book_text": "quote",
        }
    )
    assert row["category"] == "CONTEXT"
    assert "category_invalid" in row["validation_flags"]


def test_invalid_grounding_falls_back():
    row = normalize_row(
        {
            "category": "METHOD",
            "grounding": "certain",
            "annotation": "A note.",
            "book_text": "quote",
        }
    )
    assert row["grounding"] == "uncertain"
    assert "grounding_invalid" in row["validation_flags"]
