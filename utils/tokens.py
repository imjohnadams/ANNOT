import tiktoken

from config import (
    INPUT_COST_ESTIMATE,
    OUTPUT_ANNOTATION_TOKENS_HIGH,
    OUTPUT_ANNOTATION_TOKENS_LOW,
    OUTPUT_COST_REGULAR,
    OUTPUT_JSON_OVERHEAD_PER_ANNOT,
    OUTPUT_QUOTE_TOKENS_HIGH,
    OUTPUT_QUOTE_TOKENS_LOW,
    QUALITY_OUTPUT_TOKEN_MULTIPLIER,
    TIKTOKEN_ENCODING,
)


_encoding = None


def get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING)
    return _encoding


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(get_encoding().encode(text))


def estimate_chapter_output_tokens(
    page_count: int,
    quotes_per_page: int = 1,
    quality: str = "medium",
) -> tuple[int, int]:
    annot_count = max(1, page_count) * max(1, quotes_per_page)
    quality_mult = QUALITY_OUTPUT_TOKEN_MULTIPLIER.get(quality, 1.0)

    per_annot_low = (
        OUTPUT_QUOTE_TOKENS_LOW
        + OUTPUT_ANNOTATION_TOKENS_LOW
        + OUTPUT_JSON_OVERHEAD_PER_ANNOT
    )
    per_annot_high = (
        OUTPUT_QUOTE_TOKENS_HIGH
        + OUTPUT_ANNOTATION_TOKENS_HIGH
        + OUTPUT_JSON_OVERHEAD_PER_ANNOT
    )

    low = int(annot_count * per_annot_low * quality_mult)
    high = int(annot_count * per_annot_high * quality_mult)
    return low, high


def estimate_run_cost_usd(
    input_tokens: int,
    output_tokens_low: int,
    output_tokens_high: int,
) -> tuple[float, float]:
    input_cost = input_tokens * INPUT_COST_ESTIMATE
    low = input_cost + output_tokens_low * OUTPUT_COST_REGULAR
    high = input_cost + output_tokens_high * OUTPUT_COST_REGULAR
    return low, high
