from pdf.layout_detector import detect_article_heading


def test_known_section_heading():
    text = "3. Methods\n\nParticipants completed a survey."
    assert detect_article_heading(text) == "3. Methods"


def test_numbered_heading():
    text = "2.1 Participants\n\nThe sample included students."
    assert detect_article_heading(text) == "2.1 Participants"


def test_sentence_is_not_a_heading():
    text = "The introduction of the method was slow and careful."
    assert detect_article_heading(text) is None
