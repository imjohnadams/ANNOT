from config import ANNOTATION_CATEGORIES, GROUNDING_STATUSES

CHAPTER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "chapter_number": {"type": "integer"},
        "chapter_title": {"type": "string"},
        "start_page": {"type": "integer"},
        "end_page": {"type": "integer"},
        "annotations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "book_text": {"type": "string"},
                    "annotation": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": list(ANNOTATION_CATEGORIES),
                    },
                    "grounding": {
                        "type": "string",
                        "enum": list(GROUNDING_STATUSES),
                    },
                },
                "required": [
                    "page",
                    "book_text",
                    "annotation",
                    "category",
                    "grounding",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "chapter_number",
        "chapter_title",
        "start_page",
        "end_page",
        "annotations",
    ],
    "additionalProperties": False,
}
